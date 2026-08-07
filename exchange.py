"""
Waynis AI — real exchange client (Spot, LONG-only).

Supports Binance (primary) and OKX (fallback). Keys are read ONLY from
environment variables (never from code/repo/chat):

    BINANCE_API_KEY / BINANCE_API_SECRET        (Binance)
    OKX_API_KEY / OKX_API_SECRET / OKX_PASSPHRASE  (OKX)

SAFETY:
  * Spot only, LONG only (buy low, sell high — no shorting, no leverage).
  * TP/SL are attached to the exchange itself (bracket orders), so even
    if the bot/server goes offline, the position is protected.
  * We never call withdraw endpoints.
"""
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request

FEE_RATE = 0.001          # 0.1% per side (taker), used in paper mode too
MIN_NOTIONAL = 5.0        # min order size in USDT
MAX_NOTIONAL_PCT = 0.15   # max 15% of balance per trade
MAX_POSITIONS = 2         # max concurrent real positions (tiny accounts)


def _http_json(url, headers=None, data=None, timeout=12):
    req = urllib.request.Request(url, headers=headers or {}, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Binance
# ---------------------------------------------------------------------------
class BinanceClient:
    name = "Binance"
    base = "https://api.binance.com"

    def __init__(self):
        self.api_key = os.environ.get("BINANCE_API_KEY", "").strip()
        self.secret = os.environ.get("BINANCE_API_SECRET", "").strip()
        self._filters = {}

    @property
    def configured(self):
        return bool(self.api_key and self.secret)

    def _sign(self, params: dict) -> str:
        """Binance: signature over the query string (params in given order)."""
        qs = urllib.parse.urlencode(params)
        sig = hmac.new(self.secret.encode(), qs.encode(), hashlib.sha256).hexdigest()
        return qs + "&signature=" + sig

    def _get(self, path, params=None):
        params = dict(params or {})
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = 10000
        qs = self._sign(params)
        url = f"{self.base}{path}?{qs}"
        return _http_json(url, headers={"X-MBX-APIKEY": self.api_key})

    def _post(self, path, params=None):
        params = dict(params or {})
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = 10000
        qs = self._sign(params)
        url = f"{self.base}{path}"
        return _http_json(url, headers={"X-MBX-APIKEY": self.api_key},
                          data=qs.encode())

    def _delete(self, path, params=None):
        params = dict(params or {})
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = 10000
        qs = self._sign(params)
        url = f"{self.base}{path}?{qs}"
        req = urllib.request.Request(url, headers={"X-MBX-APIKEY": self.api_key},
                                     method="DELETE")
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read().decode("utf-8"))

    # -- filters -----------------------------------------------------------
    def _lot(self, symbol):
        if symbol not in self._filters:
            info = _http_json(f"{self.base}/api/v3/exchangeInfo")
            for s in info.get("symbols", []):
                if s["symbol"] == symbol:
                    f = {x["filterType"]: x for x in s.get("filters", [])}
                    self._filters[symbol] = f
                    break
        return self._filters.get(symbol, {})

    def qty_precision(self, symbol):
        lot = self._lot(symbol).get("LOT_SIZE", {})
        step = float(lot.get("stepSize", "0.000001"))
        if step >= 1:
            return 0
        return len(str(step).rstrip("0").split(".")[1])

    def min_qty(self, symbol):
        lot = self._lot(symbol).get("LOT_SIZE", {})
        return float(lot.get("minQty", "0"))

    # -- account -----------------------------------------------------------
    def balance_usdt(self):
        acc = self._get("/api/v3/account")
        for b in acc.get("balances", []):
            if b["asset"] == "USDT":
                return float(b["free"])
        return 0.0

    def price(self, symbol):
        t = _http_json(f"{self.base}/api/v3/ticker/price?symbol={symbol}")
        return float(t["price"])

    # -- orders ------------------------------------------------------------
    def market_buy(self, symbol, qty):
        """Buy and attach TP/SL bracket (two sell stop-limit orders)."""
        price = self.price(symbol)
        tp = round(price * 1.0045, self.qty_precision(symbol) + 2)
        sl = round(price * 0.9965, self.qty_precision(symbol) + 2)
        fill = self._post("/api/v3/order", {
            "symbol": symbol, "side": "BUY", "type": "MARKET",
            "quantity": f"{qty:.{self.qty_precision(symbol)}f}",
        })
        bracket = []
        # take-profit sell (stop above market)
        tp_lim = tp * 0.999
        o = self._post("/api/v3/order", {
            "symbol": symbol, "side": "SELL", "type": "TAKE_PROFIT_LIMIT",
            "quantity": f"{qty:.{self.qty_precision(symbol)}f}",
            "price": f"{tp_lim:.{self.qty_precision(symbol)+2}f}",
            "stopPrice": f"{tp:.{self.qty_precision(symbol)+2}f}",
            "timeInForce": "GTC",
        })
        bracket.append(o.get("orderId"))
        # stop-loss sell (stop below market)
        sl_lim = sl * 0.999
        o2 = self._post("/api/v3/order", {
            "symbol": symbol, "side": "SELL", "type": "STOP_LOSS_LIMIT",
            "quantity": f"{qty:.{self.qty_precision(symbol)}f}",
            "price": f"{sl_lim:.{self.qty_precision(symbol)+2}f}",
            "stopPrice": f"{sl:.{self.qty_precision(symbol)+2}f}",
            "timeInForce": "GTC",
        })
        bracket.append(o2.get("orderId"))
        return {"fill": fill, "bracket": bracket, "tp": tp, "sl": sl,
                "price": price}

    def market_sell_all(self, symbol, qty, bracket_ids=()):
        for oid in bracket_ids:
            try:
                self._delete("/api/v3/order",
                             {"symbol": symbol, "orderId": oid})
            except Exception:
                pass
        return self._post("/api/v3/order", {
            "symbol": symbol, "side": "SELL", "type": "MARKET",
            "quantity": f"{qty:.{self.qty_precision(symbol)}f}",
        })

    def status(self):
        return {
            "exchange": self.name,
            "configured": self.configured,
            "symbol_format": "BTCUSDT",
        }


# ---------------------------------------------------------------------------
# OKX (fallback)
# ---------------------------------------------------------------------------
class OKXClient:
    name = "OKX"
    base = "https://www.okx.com"

    def __init__(self):
        self.key = os.environ.get("OKX_API_KEY", "").strip()
        self.secret = os.environ.get("OKX_API_SECRET", "").strip()
        self.passphrase = os.environ.get("OKX_PASSPHRASE", "").strip()

    @property
    def configured(self):
        return bool(self.key and self.secret and self.passphrase)

    def _headers(self, method, path, body=""):
        ts = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        prehash = ts + method + path + body
        sig = base64.b64encode(
            hmac.new(self.secret.encode(), prehash.encode(),
                     hashlib.sha256).digest()).decode()
        return {
            "OK-ACCESS-KEY": self.key,
            "OK-ACCESS-SIGN": sig,
            "OK-ACCESS-TIMESTAMP": ts,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }

    def _get(self, path):
        url = f"{self.base}{path}"
        return _http_json(url, headers=self._headers("GET", path))

    def _post(self, path, body: dict):
        data = json.dumps(body).encode()
        url = f"{self.base}{path}"
        return _http_json(url, headers=self._headers("POST", path, data.decode()),
                          data=data)

    def balance_usdt(self):
        d = self._get("/api/v5/account/balance")
        for det in d.get("data", []):
            for bal in det.get("details", []):
                if bal["ccy"] == "USDT":
                    return float(bal.get("availBal", bal.get("cashBal", 0)))
        return 0.0

    def price(self, symbol):
        t = _http_json(f"{self.base}/api/v5/market/ticker?instId={symbol}")
        return float(t["data"][0]["last"])

    def market_buy(self, symbol, qty):
        """OKX spot market buy with TP/SL attached to the same order.
        sz is in quote currency (USDT) for market buys."""
        price = self.price(symbol)
        notional = round(price * qty, 2)
        tp = round(price * 1.0045, 4)
        sl = round(price * 0.9965, 4)
        body = {
            "instId": symbol, "tdMode": "cash", "side": "buy",
            "ordType": "market", "sz": str(notional),
            "tpTriggerPx": str(tp), "tpOrdPx": "-1",
            "slTriggerPx": str(sl), "slOrdPx": "-1",
        }
        d = self._post("/api/v5/trade/order", body)
        return {"fill": d, "bracket": [], "tp": tp, "sl": sl, "price": price}

    def market_sell_all(self, symbol, qty, bracket_ids=()):
        body = {"instId": symbol, "tdMode": "cash", "side": "sell",
                "ordType": "market", "sz": f"{qty:.8f}"}
        return self._post("/api/v5/trade/order", body)

    def status(self):
        return {
            "exchange": self.name,
            "configured": self.configured,
            "symbol_format": "BTC-USDT",
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def get_exchange(name=None):
    name = (name or os.environ.get("REAL_EXCHANGE", "binance")).lower()
    if name == "okx":
        return OKXClient()
    return BinanceClient()


def to_exchange_symbol(okx_symbol, exchange):
    if exchange.name == "Binance":
        return okx_symbol.replace("-", "")
    return okx_symbol
