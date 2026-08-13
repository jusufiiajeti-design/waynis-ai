"""
Price data providers for the Waynis AI paper-trading bot.

Primary:  OKX  (https://www.okx.com)   - free public market data
Fallback: Coinbase Exchange, Kraken    - used if OKX is unreachable
"""
import asyncio
import time
import urllib.request
import urllib.error
import json

USER_AGENT = {"User-Agent": "Mozilla/5.0 (WaynisAI/1.0)"}

# ---------------------------------------------------------------------------
# Watchlist: OKX instId -> (Coinbase product, Kraken pair)
# ---------------------------------------------------------------------------
WATCHLIST = [
    ("BTC-USDT", "BTC-USD", "XBTUSD"),
    ("ETH-USDT", "ETH-USD", "ETHUSD"),
    ("SOL-USDT", "SOL-USD", "SOLUSD"),
    ("BNB-USDT", "BNB-USD", None),
    ("XRP-USDT", "XRP-USD", "XRPUSD"),
    ("DOGE-USDT", "DOGE-USD", "XDGUSD"),
    ("ADA-USDT", "ADA-USD", "ADAUSD"),
    ("AVAX-USDT", "AVAX-USD", "AVAXUSD"),
    ("LINK-USDT", "LINK-USD", "LINKUSD"),
    ("SUI-USDT", None, None),
    ("DOT-USDT", None, "DOTUSD"),
    ("PEPE-USDT", None, None),
    # extra scanning coverage (all verified live on OKX)
    ("NEAR-USDT", None, None),
    ("APT-USDT", None, None),
    ("ARB-USDT", None, None),
    ("OP-USDT", None, None),
    ("INJ-USDT", None, None),
    ("LTC-USDT", None, None),
    ("TRX-USDT", None, None),
    ("UNI-USDT", None, None),
    # 🚀 më shumë monedha likuide (OKX) — më shumë mundësi/ditë
    ("TON-USDT", None, None),
    ("HBAR-USDT", None, None),
    ("AAVE-USDT", None, None),
    ("FIL-USDT", None, None),
    ("STX-USDT", None, None),
    ("ETC-USDT", None, None),
    ("SEI-USDT", None, None),
    ("TIA-USDT", None, None),
    ("WIF-USDT", None, None),
    ("JUP-USDT", None, None),
    ("ENA-USDT", None, None),
    ("ONDO-USDT", None, None),
    ("PENDLE-USDT", None, None),
    ("ALT-USDT", None, None),
    ("1000PEPE-USDT", None, None),
    ("CRV-USDT", None, None),
    ("MKR-USDT", None, None),
    ("LDO-USDT", None, None),
    ("RUNE-USDT", None, None),
    # 🚀 më shumë monedha likuide → më shumë mundësi Mean Reversion
    ("ATOM-USDT", None, None),
    ("FET-USDT", None, None),
    ("GRT-USDT", None, None),
    ("SAND-USDT", None, None),
    ("MANA-USDT", None, None),
    ("THETA-USDT", None, None),
    ("ALGO-USDT", None, None),
    ("KAS-USDT", None, None),
    ("IMX-USDT", None, None),
    ("CELO-USDT", None, None),
    ("RENDER-USDT", None, None),
    ("AR-USDT", None, None),
    ("PYTH-USDT", None, None),
    # 🚀 më shumë monedha likuide → më shumë pozicione MR njëkohësisht
    ("XLM-USDT", None, None),
    ("BCH-USDT", None, None),
    ("EOS-USDT", None, None),
    ("ZEC-USDT", None, None),
    ("DASH-USDT", None, None),
    ("VET-USDT", None, None),
    ("ICP-USDT", None, None),
    ("APE-USDT", None, None),
    ("GALA-USDT", None, None),
    ("CHZ-USDT", None, None),
    ("1INCH-USDT", None, None),
    ("SNX-USDT", None, None),
    ("COMP-USDT", None, None),
    ("ENS-USDT", None, None),
    ("FLOW-USDT", None, None),
]

OKX_BAR = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1H", "4h": "4H", "1d": "1D"}


def _http_json(url: str, timeout: float = 8.0):
    req = urllib.request.Request(url, headers=USER_AGENT)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


async def _http_json_async(url: str, timeout: float = 8.0):
    """Run a blocking http fetch in a thread so the event loop stays free."""
    return await asyncio.to_thread(_http_json, url, timeout)


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


class MarketData:
    """Cached, resilient market data accessor with OKX primary."""

    def __init__(self):
        self._cache = {}          # key -> (ts, payload)
        self._ticker_cache = {}   # okx_symbol -> dict, updated each fetch
        self._tickers_ok = False

    # ------------------------------------------------------------------
    # Tickers (all watchlist prices in one OKX call)
    # ------------------------------------------------------------------
    async def scan_universe(self, min_vol_usdt=50000):
        """🌐 UNIVERSI DINAMIK: TË GJITHA çiftet USDT në OKX me vëllim 24h
        ≥ min_vol_usdt (likuiditet real). WATCHLIST-i mbetet bërthama (me
        simbole fallback), por kthehen edhe të gjitha monedhat e tjera.
        Cache 10 min — një kërkesë për të gjithë tregun."""
        now = time.time()
        cached = self._cache.get("universe")
        if cached and now - cached[0] < 600:
            return cached[1]
        out = [(w[0], w[1], w[2]) for w in WATCHLIST]
        seen = {w[0] for w in out}
        try:
            data = await _http_json_async(
                "https://www.okx.com/api/v5/market/tickers?instType=SPOT")
            if data.get("code") == "0":
                for t in data["data"]:
                    sym = t.get("instId", "")
                    if not sym.endswith("-USDT") or sym in seen:
                        continue
                    vol_usdt = _safe_float(t.get("volCcy24h"))
                    if vol_usdt < min_vol_usdt:
                        continue
                    out.append((sym, None, None))
                    seen.add(sym)
        except Exception:
            pass
        self._cache["universe"] = (now, out)
        return out

    async def fetch_all_tickers(self) -> dict:
        """Returns {okx_symbol: {price, open24, high24, low24, vol24, chg24, ts}}"""
        now = time.time()
        cached = self._cache.get("tickers")
        if cached and now - cached[0] < 2.0:
            return cached[1]

        out = dict(self._ticker_cache)
        try:
            data = await _http_json_async(
                "https://www.okx.com/api/v5/market/tickers?instType=SPOT"
            )
            if data.get("code") == "0":
                fresh = {}
                for t in data["data"]:
                    sym = t["instId"]
                    if not sym.endswith("-USDT"):
                        continue
                    last = _safe_float(t.get("last"))
                    open24 = _safe_float(t.get("open24h"))
                    high = _safe_float(t.get("high24h"))
                    low = _safe_float(t.get("low24h"))
                    vol = _safe_float(t.get("vol24h"))
                    chg = ((last / open24) - 1.0) * 100 if open24 else 0.0
                    fresh[sym] = {
                        "symbol": sym,
                        "price": last,
                        "open24": open24,
                        "high24": high,
                        "low24": low,
                        "vol24": vol,
                        "chg24": round(chg, 2),
                        "ts": int(_safe_float(t.get("ts"), now * 1000)),
                    }
                if fresh:
                    out = fresh
                    self._ticker_cache = fresh
                    self._tickers_ok = True
        except Exception:
            pass

        # Fallback: fill missing symbols from Coinbase (BTC/ETH/SOL/...)
        missing = [w for w in WATCHLIST if w[0] not in out]
        if missing:
            await self._fallback_coinbase(missing, out)
        self._cache["tickers"] = (now, out)
        return out

    async def _fallback_coinbase(self, missing, out):
        tasks = []
        for okx_sym, cb_sym, _ in missing:
            if cb_sym:
                tasks.append(self._cb_ticker(okx_sym, cb_sym, out))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _cb_ticker(self, okx_sym, cb_sym, out):
        try:
            d = await _http_json_async(
                f"https://api.exchange.coinbase.com/products/{cb_sym}/ticker"
            )
            price = _safe_float(d.get("price"))
            if price <= 0:
                return
            out[okx_sym] = {
                "symbol": okx_sym,
                "price": price,
                "open24": 0.0,
                "high24": 0.0,
                "low24": 0.0,
                "vol24": _safe_float(d.get("volume_24h")),
                "chg24": 0.0,
                "ts": int(time.time() * 1000),
                "source": "coinbase",
            }
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Klines / candles
    # ------------------------------------------------------------------
    async def fetch_klines(self, okx_symbol: str, interval: str = "1m",
                           limit: int = 150) -> list:
        """Returns list of {t,o,h,l,c,v} oldest -> newest.
        ⚡ CACHE 12s: kthehen të dhënat e ruajtura pa kërkesë HTTP të re —
        kjo e përshpejton qarkullimin 5-10× (Scanner skanon 100 monedha)."""
        ckey = (okx_symbol, interval, limit)
        now = time.time()
        cached = self._cache.get(ckey)
        if cached and now - cached[0] < 30.0:
            return cached[1]
        bar = OKX_BAR.get(interval, "1m")
        url = (f"https://www.okx.com/api/v5/market/candles"
               f"?instId={okx_symbol}&bar={bar}&limit={limit}")
        try:
            data = await _http_json_async(url)
            if data.get("code") == "0":
                rows = list(reversed(data["data"]))  # OKX returns newest first
                candles = [
                    {
                        "t": int(_safe_float(r[0])),
                        "o": _safe_float(r[1]),
                        "h": _safe_float(r[2]),
                        "l": _safe_float(r[3]),
                        "c": _safe_float(r[4]),
                        "v": _safe_float(r[5]),
                    }
                    for r in rows
                    if _safe_float(r[4]) > 0
                ]
                if candles:
                    self._cache[ckey] = (time.time(), candles)
                    return candles
        except Exception:
            pass

        # Fallback via Coinbase
        cb = self._cb_symbol(okx_symbol)
        if cb:
            try:
                granularity = {"1m": 60, "5m": 300, "15m": 900,
                               "1h": 3600, "4h": 14400, "1d": 86400}[interval]
                end = int(time.time())
                start = end - granularity * (limit + 1)
                url = (f"https://api.exchange.coinbase.com/products/{cb}/candles"
                       f"?granularity={granularity}&start={start}&end={end}")
                data = await _http_json_async(url)
                if isinstance(data, list):
                    rows = sorted(data, key=lambda r: r[0])[-limit:]
                    out = [
                        {"t": int(r[0]) * 1000, "o": _safe_float(r[3]),
                         "h": _safe_float(r[2]), "l": _safe_float(r[1]),
                         "c": _safe_float(r[4]), "v": _safe_float(r[5])}
                        for r in rows
                    ]
                    self._cache[ckey] = (time.time(), out)
                    return out
            except Exception:
                pass
        return []

    async def fetch_klines_history(self, okx_symbol: str, interval: str = "1h",
                                   limit: int = 900) -> list:
        """Historical klines via OKX pagination (oldest -> newest).
        Used by the backtest engine."""
        bar = OKX_BAR.get(interval, "1H")
        out = []
        seen = set()
        after = None
        page = 100                         # OKX history-candles caps at 100
        try:
            while len(out) < limit:
                url = (f"https://www.okx.com/api/v5/market/history-candles"
                       f"?instId={okx_symbol}&bar={bar}&limit={page}")
                if after:
                    url += f"&after={after}"
                data = await _http_json_async(url)
                if not data.get("code") == "0":
                    break
                rows = data.get("data") or []
                if not rows:
                    break
                batch = []
                for r in rows:
                    t = int(_safe_float(r[0]))
                    c = _safe_float(r[4])
                    if t in seen or c <= 0:
                        continue
                    seen.add(t)
                    batch.append({
                        "t": t, "o": _safe_float(r[1]),
                        "h": _safe_float(r[2]), "l": _safe_float(r[3]),
                        "c": c, "v": _safe_float(r[5]),
                    })
                if not batch:
                    break
                out.extend(batch)
                after = batch[-1]["t"]      # oldest of this batch -> next page
                if len(batch) < page:
                    break
        except Exception:
            pass
        out.sort(key=lambda x: x["t"])
        return out[:limit]

    @staticmethod
    def _cb_symbol(okx_sym):
        for okx, cb, _ in WATCHLIST:
            if okx == okx_sym:
                return cb
        return None

    # ------------------------------------------------------------------
    # Resolution of a symbol to OKX id (used by engine / api)
    # ------------------------------------------------------------------
    @staticmethod
    def okx_of(symbol: str):
        s = symbol.upper().replace("/", "-")
        for okx, _, _ in WATCHLIST:
            if okx == s:
                return okx
        return s if s.endswith("-USDT") else f"{s}-USDT"
