# ============ config.py ============
"""Waynis AI — central configuration (shared by engine and agents)."""

STARTING_BALANCE = 10_000.0     # USDT, paper account
CYCLE_SECONDS = 3               # coordinator cycle period (cache = faster)
SCAN_BATCH = 32                 # symbols scanned per cycle (all watchlist)
TRADE_TF = "5m"                 # ⏱️ korniza 5-minutëshe — E FIKSUAR (kërkesa e përdoruesit: mos e ndërro)
KLINES_TTL = 20.0               # cache klines (5m qirinj) — cikle më të shpejta
TRADE_RISK = 0.0075             # fraction of (base) equity risked per trade
TAKE_PROFIT = 0.35              # TP 35% = vetëm rrjet sigurie MBI shkallën $5 — kurrë nuk ndërhyn me centa
STOP_LOSS = 0.0035              # -0.35 %
BREAKEVEN_AT = 0.0020           # move SL to breakeven after +0.20 %
MIN_CONFIDENCE = 58.0           # % required to fire a trade
MAX_OPEN = 30                   # 30 pozicione njëkohësisht → më shumë tregti/ditë (30×$15=$450 rrezik, OK për $10k)
COOLDOWN_SEC = 10               # cooldown 10s — rihap më shpejt pas mbylljes → më shumë tregti/ditë
MAX_HOLD_MIN = 30               # time-stop: mbyll pozicionin pas 30 min — me shkallën e kyçur nëse ka fitim, me humbje të vogël nëse jo (liron vendet → më shumë tregti)
TIME_STOP_SL = 0.0015           # time-stop closes at -0.15% (small, frees the slot fast)

# ---- real money (spot, LONG-only) ----
FEE_RATE = 0.001                # 0.1% per side (taker) — also simulated in paper
REAL_MIN_NOTIONAL = 5.0         # min order size USDT
REAL_MAX_NOTIONAL_PCT = 0.15    # max % of real balance per trade
REAL_MAX_POSITIONS = 2          # max concurrent real positions
REAL_TP = 0.0045                # +0.45%
REAL_SL = 0.0035                # -0.35%

# ---- asymmetric payoff: wins > losses ("arbitrage-like" edge) ----
# NOTE: disabled by request — the bot uses classic symmetric TP/SL.
ENABLE_PARTIAL_TP = False       # partial take-profit + trailing runner (paper)
TP1_PARTIAL = 0.005             # take half of the position at +0.5%
PARTIAL_FRACTION = 0.5          # fraction sold at TP1
TRAIL_PCT = 0.004               # runner trails 0.4% below its peak
RUNNER_BE = 0.0005              # runner SL floor = entry + 0.05% (never loses)
REL_STRENGTH_BOOST = False      # cross-symbol relative-strength filter
COMPOUND_MULT_MAX = 5.0         # max compound multiplier (×1..×5 user)

# ---- 🛡️ adaptive risk (protects against ×2 losses) ----
RISK_ADAPTIVE_ENABLED = True    # risk manager watches recent performance
RISK_LOOKBACK = 10              # last N closed trades evaluated
RISK_BAD_WR = 0.45              # if win rate below this → de-risk
RISK_BAD_NET = 0.0              # if net pnl over lookback below this → de-risk
RISK_DELEVERAGE_TO = 1.0        # auto-reduce multiplier to ×1 when losing
RISK_PAUSE_MIN = 15             # pause new trades for N minutes when losing
RISK_RESUME_MIN = 3             # re-evaluate after N minutes

# ---- 🪜 SPOT PYRAMIDING (sistemi universal EMA+RSI+volume) ----
SPOT_ENTRY_USD = 5.0         # hyrja për çdo shtesë në spot pyramiding:
                             # $5 (përdoruesi: $3–$5). $45/aset → deri në 9 shtesa.

# ---- 🪜 PYRAMIDING (i gjithë boti si spot pyramiding) ----
# Boti shton pozicione në TË NJËJTIN simbol kur është në fitim (higher-high
# për LONG / lower-low për SHORT), max 3 gjithsej, me madhësinë normale
# ($15 ose ×komponim). KURRË averaging-down: shtohet vetëm në fitim.
MAX_PYRAMID = 3                 # max pozicione për simbol (hyrja + 2 shtesa)
PYRAMID_CONFIRM_PCT = 0.004     # kërkohet higher-high/lower-low 0.4% për shtesë
PYRAMID_MIN_PROFIT_USD = 0.50   # shtohet VETËM kur grupi është në fitim ≥ $0.50
PYRAMID_RSI_MAX = 78            # s'ngjyhet me RSI ekstrem (LONG <78 / SHORT >22)

# ---- 💵 fixed dollar risk (entry e fiksuar, humbje maksimale e fiksuar) ----
# Hyrja $10–15 (sipas përdoruesit) · fitime të arsyeshme $1–$3+ të kapura
# nga agjentët me shkallë fitimi. Përdoruesi i ndryshon nga Cilësimet.
FIXED_RISK_ENABLED = True         # ON by default: entry fixed, loss capped
FIXED_ENTRY_USD = 50.0           # hyrja për tregti në USDT — $50 (zgjedhja e
                                 # përdoruesit): $1 kapet me ~2.2% lëvizje → fitime
                                 # të shpeshta; humbja/tregti ~$0.18 (SL 0.35%).
FIXED_MAX_LOSS_USD = 2.0         # kufiri i humbjes për tregti (i arsyeshëm)

# ---- 💵 profit ladder (shkallët e fitimit që agjenti i kap) ----
# VETËM dollarë të plotë: $1, $2, $3, $4, $5 — kurrë centa (p.sh. JO $1.04).
# Fitimi neto (pas tarifave) matet kundrejt shkallës dhe kapet si dollar i plotë.
PROFIT_LADDER = [5.0, 4.0, 3.0, 2.0, 1.0]

# ---- 🧩 ensemble (hundreds of strategy variants) ----
ENSEMBLE_ENABLED = True          # strategy variants vote with the core
AGENT_TARGET = 100_000          # 100,000 agjentë (variante strategjike) që bashkëpunojnë me vota.
                                 # Çdo cikël voton një mostër rrotulluese (shpejtësia mbetet e njëjtë);
                                 # çdo familje (EMA, RSI, MACD…) ka një zë të barabartë.



# ---- 🔒 equity profit lock (protect account gains) ----
# Once the account grows to a peak, never let it give back more than
# EQUITY_LOCK_PCT from that peak — when triggered, ALL positions close
# and new entries pause for EQUITY_LOCK_PAUSE_MIN minutes.
EQUITY_LOCK_ENABLED = True
EQUITY_LOCK_PCT = 0.02           # give back max 2% from peak (0.02 = 2%)
EQUITY_LOCK_PAUSE_MIN = 10       # pause new entries after a lock

# ---- 📈 DCA (dollar-cost averaging) mode ----
DCA_ENABLED = False              # off until user turns it on
DCA_AMOUNT = 5.0                 # USDT per buy
DCA_INTERVAL_MIN = 60            # buy every N minutes
DCA_SYMBOL = "BTC-USDT"

# ---- 🎯 Multi-timeframe confirmation ----
MTF_ENABLED = True               # confirm 1m signal with 15m trend
MTF_BAR = "15m"
MTF_FAST = 20                    # EMA fast period on MTF
MTF_SLOW = 50                    # EMA slow period on MTF
MTF_CACHE_TTL = 120              # seconds to cache MTF closes per symbol


# ============ turso.py ============
"""
Waynis AI — Turso (libsql) cloud persistence.

Ruajtja PËRGJITHMONË e tregtive/balancës në një databazë falas në internet.
Përdor vetëm urllib (asnjë varësi ekstra) dhe API-në HTTP të Turso-s
(/v2/pipeline). Nëse Turso nuk është i arritshëm, boti vazhdon lokalisht
(offline) dhe ri-sinkronizon në goditjen tjetër të suksesshme.
"""
import json
import os
import urllib.request


def _creds():
    url = (os.environ.get("TURSO_URL") or "").strip()
    token = (os.environ.get("TURSO_TOKEN") or "").strip()
    if not url or not token:
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(base, "turso.json"), "r", encoding="utf-8") as f:
                d = json.load(f)
            url = url or str(d.get("url", "")).strip()
            token = token or str(d.get("token", "")).strip()
        except Exception:
            pass
    return url, token


def enabled():
    u, t = _creds()
    return bool(u and t)


def _request(sql, args, want_rows):
    u, t = _creds()
    host = u.split("://", 1)[-1].rstrip("/")
    payload = {
        "requests": [{"type": "execute",
                      "stmt": {"sql": sql,
                               "args": [_cell(a) for a in (args or [])]}}],
        "mode": "rows" if want_rows else "write",
    }
    req = urllib.request.Request(
        "https://" + host + "/v2/pipeline",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + t, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def _val(cell):
    """Turso kthen qeliza si {'type':..,'value':..} ose vlera të thjeshta."""
    if isinstance(cell, dict):
        return cell.get("value")
    return cell


def _cell(v):
    """Kthen një vlerë Python në qelizën e etiketuar që kërkon API i Turso-s
    (p.sh. "text" → {'type':'text','value':...}). Pa këtë, API kthen 400."""
    if v is None:
        return {"type": "null"}
    if isinstance(v, bool):
        return {"type": "integer", "value": "1" if v else "0"}
    if isinstance(v, int):
        # Turso (libsql HTTP) i kodon int64-t si vargje ("5", jo 5) — pa këtë
        # kthen 400 "expected a borrowed string"
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        return {"type": "float", "value": v}
    if isinstance(v, (bytes, bytearray)):
        return {"type": "blob", "value": v.decode("utf-8", "replace")}
    return {"type": "text", "value": str(v)}


def query(sql, args=None):
    """Kthen lista rreshtash (tupla) ose [] nëse dështon/pa kredenciale."""
    if not enabled():
        return []
    try:
        out = _request(sql, args, True)
    except Exception:
        return []
    rows = []
    for res in out.get("results", []):
        if res.get("type") != "ok":
            continue
        rr = res.get("response", {}).get("result", {})
        for row in rr.get("rows", []):
            # Turso kthen rreshta si lista qelizash; në disa versione
            # si {'row': [...]} — i përballojmë të dyja
            if isinstance(row, dict) and "row" in row:
                row = row["row"]
            rows.append(tuple(_val(c) for c in row))
    return rows


def exec_sql(sql, args=None):
    """Ekzekuton një INSERT/UPDATE/DELETE/DDL. True nëse shkoi mirë."""
    if not enabled():
        return False
    try:
        _request(sql, args, False)
        return True
    except Exception:
        return False


def batch_exec(items):
    """Ekzekuton shumë deklarata në NJË kërkesë HTTP (pipeline)."""
    if not enabled() or not items:
        return False
    u, t = _creds()
    host = u.split("://", 1)[-1].rstrip("/")
    reqs = [{"type": "execute",
             "stmt": {"sql": s, "args": [_cell(x) for x in (a or [])]}}
            for s, a in items]
    payload = {"requests": reqs, "mode": "write"}
    try:
        req = urllib.request.Request(
            "https://" + host + "/v2/pipeline",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": "Bearer " + t,
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return True
    except Exception:
        return False
# ============ providers.py ============
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
    ("TIA-USDT", None, None),
    ("SEI-USDT", None, None),
    ("WIF-USDT", None, None),
    ("AAVE-USDT", None, None),
    ("LDO-USDT", None, None),
    ("FET-USDT", None, None),
    ("RENDER-USDT", None, None),
    ("HBAR-USDT", None, None),
    ("ALGO-USDT", None, None),
    ("ATOM-USDT", None, None),
    ("ETC-USDT", None, None),
    ("FIL-USDT", None, None),
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
                    if sym not in {w[0] for w in WATCHLIST}:
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
        """Returns list of {t,o,h,l,c,v} oldest -> newest."""
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
                    return [
                        {"t": int(r[0]) * 1000, "o": _safe_float(r[3]),
                         "h": _safe_float(r[2]), "l": _safe_float(r[1]),
                         "c": _safe_float(r[4]), "v": _safe_float(r[5])}
                        for r in rows
                    ]
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
# ============ brain.py ============
"""
Waynis AI — AI BRAIN (reasoning layer for the agents).

The brain runs ASYNCHRONOUSLY in the background: agents enqueue analysis
jobs with a market snapshot and never block the 4-second trading cycle.
When a verdict is ready it is cached per symbol and consulted by the
Predictor / Validator agents, and streamed to the UI as "AI reasoning".

Providers (in order of fallback):
  1. ollama         — local LLM (default, free, offline) e.g. qwen2.5:0.5b
  2. pollinations   — free anonymous cloud LLM (text.pollinations.ai)
  3. openai         — any OpenAI-compatible endpoint with user API key
  4. symbolic       — built-in reasoning engine (always available, offline)

Every provider returns a structured verdict:
    {verdict: LONG|SHORT|HOLD, confidence: 0-100, reason: "..."}
"""
import asyncio
import json
import os
import subprocess
import time
import urllib.request
import urllib.parse
import urllib.error

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CONFIG_PATH = os.path.join(DATA_DIR, "ai_config.json")

SYSTEM_PROMPT = (
    "You are Waynis AI, a disciplined crypto trading analyst. "
    "Analyze the given market snapshot. Reply with ONLY valid JSON: "
    '{"verdict":"LONG|SHORT|HOLD","confidence":0-100,'
    '"reason":"one short sentence in Albanian"}'
)

DEFAULT_CONFIG = {
    "enabled": True,
    "provider": "auto",            # auto | ollama | pollinations | openai
    "model": "qwen2.5:0.5b",       # for ollama / openai
    "openai_model": "gpt-4o-mini",
    "base_url": "https://api.openai.com/v1",
    "api_key": "",
    "max_concurrent": 1,
    "verdict_ttl": 300,            # seconds a verdict stays fresh
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


# ---------------------------------------------------------------------------
# Symbolic reasoning engine — the offline fallback "AI"
# ---------------------------------------------------------------------------
def symbolic_reason(snapshot):
    """Structured, explainable reasoning from indicators (in Albanian)."""
    s = snapshot
    e9, e21 = s.get("ema9"), s.get("ema21")
    rsi = s.get("rsi", 50)
    vr = s.get("vol_ratio", 1.0)
    mom = s.get("momentum", 0.0)
    chg = s.get("chg24", 0.0)
    last3 = s.get("last3", [])

    steps, verdict, conf = [], "HOLD", 50

    # 1) Trend (EMA alignment)
    if e9 is not None and e21 is not None:
        spread = (e9 - e21) / e21 * 100 if e21 else 0
        if e9 > e21:
            steps.append(f"EMA9 mbi EMA21 (spread +{spread:.2f}%) → trend rritës")
            trend = "LONG"
        else:
            steps.append(f"EMA9 nën EMA21 (spread {spread:.2f}%) → trend zbritës")
            trend = "SHORT"
        conf += min(abs(spread) * 12, 18)
    else:
        trend, steps_ = "HOLD", ["Të dhëna të pamjaftueshme për trend"]

    # 2) Momentum
    if abs(mom) > 0.15:
        steps.append(f"Momentum {'+' if mom>0 else ''}{mom:.2f}% konfirmon drejtimin")
        conf += 8
    elif abs(mom) < 0.05:
        steps.append(f"Momentum {mom:+.2f}% — lëvizje e dobët, pa konfirmim")
        conf -= 8

    # 3) RSI zone
    if 45 <= rsi <= 70:
        steps.append(f"RSI {rsi:.0f} në zonë të shëndetshme (jo e mbingarkuar)")
        conf += 8
    elif rsi > 76:
        steps.append(f"RSI {rsi:.0f} → i mbingarkuar, rrezik korrigjimi")
        conf -= 12
    elif rsi < 30:
        steps.append(f"RSI {rsi:.0f} → i mbishitur, mundësi rikthimi")
        conf += 4

    # 4) Volume confirmation
    if vr >= 1.3:
        steps.append(f"Volumi {vr:.1f}x mesatare → konfirmim i fortë")
        conf += 10
    elif vr < 1.0:
        steps.append(f"Volumi {vr:.1f}x → i dobët, sinjal jo i besueshëm")
        conf -= 10
    else:
        steps.append(f"Volumi {vr:.1f}x → konfirmim i moderuar")

    # 5) 24h context
    if chg:
        steps.append(f"24h: {chg:+.2f}%")

    # 6) Last candles pattern
    if isinstance(last3, str):
        last3 = last3.split()
    if len(last3) >= 3:
        up3 = sum(1 for c in last3 if (c == "+" or (isinstance(c, (int, float)) and c > 0)))
        if up3 >= 2:
            steps.append(f"3 qirinjtë e fundit: {up3} jeshile → presion blerës")
            conf += 5 if trend == "LONG" else -5
        else:
            steps.append("3 qirinjtë e fundit: kryesisht të kuq → presion shitës")
            conf += 5 if trend == "SHORT" else -5

    conf = max(35, min(92, int(conf)))
    if conf >= 62 and trend != "HOLD":
        verdict = trend
    else:
        verdict = "HOLD"
        steps.append(f"Konfidencë vetëm {conf}% → asnjë tregti e sigurt")

    return {
        "verdict": verdict,
        "confidence": conf,
        "reason": "; ".join(steps),
        "model": "motor simbolik",
    }


# ---------------------------------------------------------------------------
# LLM providers
# ---------------------------------------------------------------------------
def _llm_ollama(snapshot, model):
    prompt = _prompt(snapshot)
    body = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "format": "json",
        "options": {"temperature": 0.2, "num_predict": 180},
    }).encode()
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate",
                                 data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=150) as r:
        d = json.loads(r.read().decode())
    return d.get("response", ""), model


def _llm_pollinations(snapshot, model="openai"):
    prompt = _prompt(snapshot, compact=True)
    body = json.dumps({"messages": [{"role": "user", "content": prompt}],
                       "model": model}).encode()
    req = urllib.request.Request("https://text.pollinations.ai/", data=body,
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "Mozilla/5.0 (WaynisAI)"})
    with urllib.request.urlopen(req, timeout=45) as r:
        out = r.read().decode()
    return out, "pollinations(" + model + ")"


def _llm_openai(snapshot, cfg):
    prompt = _prompt(snapshot)
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    body = json.dumps({
        "model": cfg.get("openai_model") or cfg.get("model"),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }).encode()
    headers = {"Content-Type": "application/json",
               "Authorization": "Bearer " + cfg.get("api_key", "")}
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=45) as r:
        d = json.loads(r.read().decode())
    return d["choices"][0]["message"]["content"], cfg.get("openai_model") or cfg.get("model")


def _prompt(snapshot, compact=False):
    s = snapshot
    if compact:
        return ("Market snapshot: " + s["symbol"] +
                f" trend={s.get('ema9',0)>s.get('ema21',0) and 'up' or 'down'}"
                f" rsi={s.get('rsi',50):.0f} vol={s.get('vol_ratio',1):.1f}x"
                f" mom={s.get('momentum',0):+.2f}% chg24={s.get('chg24',0):+.1f}%"
                f" last3={s.get('last3','')}. " + SYSTEM_PROMPT)
    return (f"Market snapshot for {s['symbol']}:\n"
            f"- EMA9 vs EMA21: {s.get('ema9')} vs {s.get('ema21')} (bullish crossover)\n"
            f"- RSI(14): {s.get('rsi')}\n"
            f"- Volume ratio vs 20-bar avg: {s.get('vol_ratio')}x\n"
            f"- Momentum (last bar): {s.get('momentum')}%\n"
            f"- 24h change: {s.get('chg24')}%\n"
            f"- Last 3 candle directions: {s.get('last3')}\n\n"
            + SYSTEM_PROMPT)


def _parse_verdict(text):
    """Extract a verdict dict from possibly-noisy LLM output."""
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            d = json.loads(text[start:end])
            verdict = str(d.get("verdict", "HOLD")).upper()
            if verdict not in ("LONG", "SHORT", "HOLD"):
                verdict = "HOLD"
            conf = int(float(d.get("confidence", 50)))
            return {"verdict": verdict, "confidence": max(0, min(100, conf)),
                    "reason": str(d.get("reason", ""))[:240]}
    except Exception:
        pass
    # fallback: scan text for keywords
    verdict = "HOLD"
    for w in ("LONG", "SHORT", "HOLD"):
        if f'"{w}"' in text or w in text.upper().split():
            verdict = w
            break
    return {"verdict": verdict, "confidence": 55, "reason": text[:240]}


# ---------------------------------------------------------------------------
# The Brain
# ---------------------------------------------------------------------------
class AIBrain:
    def __init__(self, engine):
        self.engine = engine
        self.cfg = load_config()
        self.queue = asyncio.Queue(maxsize=8)
        self.verdicts = {}          # symbol -> verdict dict
        self.last_enqueue = {}      # symbol -> ts (throttle)
        self.running = True
        self.task = None
        self.stats = {"jobs": 0, "ok": 0, "fail": 0, "last_latency_ms": 0,
                      "last_model": "", "last_error": ""}
        self._worker_lock = asyncio.Lock()

    # --------------------------------------------------------------
    # public API used by agents
    # --------------------------------------------------------------
    def snapshot_for(self, signal, klines=None, ticker=None):
        """Build a market snapshot dict from a signal + candles."""
        closes = [k["c"] for k in klines] if klines else []
        last3 = []
        if len(closes) >= 3:
            last3 = ["+" if closes[-i] > closes[-i-1] else "-"
                     for i in (1, 2, 3)]
        return {
            "symbol": signal["symbol"],
            "direction": signal["direction"],
            "ema9": signal.get("ema9"),
            "ema21": signal.get("ema21"),
            "rsi": signal.get("rsi"),
            "vol_ratio": signal.get("vol_ratio"),
            "momentum": round((signal.get("momentum") or 0) * 100, 3),
            "chg24": ticker.get("chg24") if ticker else None,
            "last3": " ".join(last3) if last3 else "n/a",
            "entry": signal.get("entry"),
        }

    def enqueue(self, snapshot):
        """Fire-and-forget: agents never wait on the brain.
        Throttled per symbol (90s) so the queue never floods."""
        if not self.cfg.get("enabled"):
            return
        sym = snapshot.get("symbol")
        now = time.time()
        if sym in self.last_enqueue and now - self.last_enqueue[sym] < 90:
            return
        self.last_enqueue[sym] = now
        try:
            self.queue.put_nowait(snapshot)
        except asyncio.QueueFull:
            try:
                self.queue.get_nowait()     # drop oldest
                self.queue.put_nowait(snapshot)
            except Exception:
                pass

    def get_verdict(self, symbol):
        """Fresh cached verdict for a symbol, else None."""
        v = self.verdicts.get(symbol)
        if not v:
            return None
        if time.time() - v["ts"] > self.cfg.get("verdict_ttl", 300):
            return None
        return v

    def status(self):
        return {
            "enabled": bool(self.cfg.get("enabled")),
            "provider": self.cfg.get("provider"),
            "model": self.stats["last_model"] or self.cfg.get("model"),
            "queue": self.queue.qsize(),
            "jobs": self.stats["jobs"],
            "ok": self.stats["ok"],
            "fail": self.stats["fail"],
            "last_latency_ms": self.stats["last_latency_ms"],
            "last_error": self.stats["last_error"],
            "verdicts": {k: v["verdict"] for k, v in self.verdicts.items()},
        }

    def update_config(self, patch):
        self.cfg.update({k: v for k, v in patch.items() if k in self.cfg})
        save_config(self.cfg)
        return self.cfg

    # --------------------------------------------------------------
    # background worker
    # --------------------------------------------------------------
    async def start(self):
        self.running = True
        self.task = asyncio.create_task(self._loop())

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()

    async def _loop(self):
        while self.running:
            try:
                snap = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break
            async with self._worker_lock:
                try:
                    verdict = await asyncio.to_thread(self._reason_blocking, snap)
                    self._store(snap["symbol"], verdict)
                except Exception as e:
                    self.stats["fail"] += 1
                    self.stats["last_error"] = str(e)[:120]

    def _reason_blocking(self, snap):
        """Run one reasoning job (blocking, in a thread)."""
        self.stats["jobs"] += 1
        t0 = time.time()
        cfg = self.cfg
        provider = cfg.get("provider", "ollama")
        errors = []

        providers_chain = []
        if provider in ("auto", "openai") and cfg.get("api_key"):
            providers_chain.append(("openai", lambda: _llm_openai(snap, cfg)))
        if provider in ("auto", "pollinations"):
            providers_chain.append(("pollinations", lambda: _llm_pollinations(snap)))
        if provider in ("auto", "ollama"):
            providers_chain.append(("ollama", lambda: _llm_ollama(snap, cfg.get("model", "qwen2.5:0.5b"))))
        # always end with the symbolic engine
        providers_chain.append(("symbolic", lambda: ("", "symbolic")))

        for name, fn in providers_chain:
            try:
                text, model = fn()
                if name == "symbolic":
                    verdict = symbolic_reason(snap)
                    verdict["model"] = "motor simbolik"
                else:
                    verdict = _parse_verdict(text)
                    verdict["model"] = model
                verdict["ts"] = time.time()
                self.stats["ok"] += 1
                self.stats["last_latency_ms"] = int((time.time() - t0) * 1000)
                self.stats["last_model"] = model
                return verdict
            except Exception as e:
                errors.append(f"{name}: {e}")
        # everything failed — pure symbolic
        verdict = symbolic_reason(snap)
        verdict["ts"] = time.time()
        self.stats["ok"] += 1
        self.stats["last_latency_ms"] = int((time.time() - t0) * 1000)
        self.stats["last_model"] = "motor simbolik"
        self.stats["last_error"] = " | ".join(errors)[:150]
        return verdict

    def _store(self, symbol, verdict):
        self.verdicts[symbol] = verdict
        self.engine.last_ai = {
            "symbol": symbol,
            "verdict": verdict["verdict"],
            "confidence": verdict["confidence"],
            "reason": verdict["reason"],
            "model": verdict["model"],
            "ts": verdict["ts"],
            "latency_ms": self.stats["last_latency_ms"],
        }
        self.engine._event(
            "ai",
            f"🧠 AI ({verdict['model']}): {verdict['verdict']} "
            f"{verdict['confidence']}% — {verdict['reason'][:110]}",
            symbol)

    # --------------------------------------------------------------
    # helpers
    # --------------------------------------------------------------
    @staticmethod
    def ensure_ollama():
        """Best-effort: start ollama serve if it is not running."""
        try:
            req = urllib.request.Request("http://127.0.0.1:11434/api/version")
            with urllib.request.urlopen(req, timeout=2):
                return True
        except Exception:
            pass
        try:
            subprocess.Popen(["ollama", "serve"],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False
# ============ strategies.py ============
"""
Waynis AI — 10 strategy agents (deterministic signal generators).

Each strategy analyzes the same market snapshot and returns a VOTE:
    {"direction": "LONG"/"SHORT", "confidence": 40-95, "name": ..., "icon": ...}

The Consensus agent combines the votes with LEARNING WEIGHTS (each
strategy's weight reflects its recent performance), so the bot adapts
over time: strategies that keep winning get more influence.
"""
import math

# ---------------------------------------------------------------------------
# Indicators (shared)
# ---------------------------------------------------------------------------
def ema(vals, period):
    if not vals:
        return []
    k = 2.0 / (period + 1)
    out = [vals[0]]
    for v in vals[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def sma(vals, period):
    if len(vals) < period:
        return []
    out = []
    s = sum(vals[:period])
    out.append(s / period)
    for i in range(period, len(vals)):
        s += vals[i] - vals[i - period]
        out.append(s / period)
    return out


def rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
    if avg_l == 0:
        # pa humbje: nëse ka edhe fitime → 100 (i mbingarkuar),
        # por nëse s'ka asnjë lëvizje → 50 (neutral, jo sinjal i rremë)
        return 100.0 if avg_g > 0 else 50.0
    return 100.0 - 100.0 / (1.0 + avg_g / avg_l)


def macd(closes, fast=12, slow=26, signal=9):
    ef = ema(closes, fast)
    es = ema(closes, slow)
    if len(ef) < 2 or len(es) < 2:
        return 0.0, 0.0
    line = [ef[i] - es[i] for i in range(len(es))]
    sig = ema(line, signal)
    return line[-1], sig[-1]


def bollinger(closes, period=20, k=2.0):
    if len(closes) < period:
        return None
    mid = sum(closes[-period:]) / period
    var = sum((c - mid) ** 2 for c in closes[-period:]) / period
    sd = math.sqrt(var)
    return mid + k * sd, mid - k * sd, mid


def stochastic(highs, lows, closes, kp=14):
    if len(closes) < kp:
        return 50.0
    hn = max(highs[-kp:])
    ln = min(lows[-kp:])
    if hn == ln:
        return 50.0
    return (closes[-1] - ln) / (hn - ln) * 100.0


def atr(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return 0.0
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i],
                 abs(highs[i] - closes[i - 1]),
                 abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    return sum(trs[-period:]) / period


def donchian(highs, lows, period=20):
    return max(highs[-period:]), min(lows[-period:])


def roc(closes, period=10):
    if len(closes) <= period or closes[-period - 1] == 0:
        return 0.0
    return (closes[-1] - closes[-period - 1]) / closes[-period - 1] * 100.0


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def vol_ratio(vols):
    """Volume ratio of the last COMPLETED candle vs the previous 20.
    (The final candle is still forming, so we skip it.)"""
    if len(vols) < 23:
        return 1.0
    avg = sum(vols[-23:-2]) / 20.0
    return vols[-2] / avg if avg > 0 else 1.0


# ---------------------------------------------------------------------------
# The 10 strategies
# ---------------------------------------------------------------------------
def ema_trend(symbol, k, ticker):
    """Trend ndjekës: EMA9 vs EMA21."""
    closes = [c["c"] for c in k]
    e9, e21 = ema(closes, 9)[-1], ema(closes, 21)[-1]
    if e9 > e21:
        spread = (e9 - e21) / e21 * 100
        return {"direction": "LONG", "confidence": clamp(50 + spread * 30, 45, 92)}
    if e9 < e21:
        spread = (e21 - e9) / e21 * 100
        return {"direction": "SHORT", "confidence": clamp(50 + spread * 30, 45, 92)}
    return None


def rsi_reversal(symbol, k, ticker):
    """Mean reversion: RSI i mbishitur / i mbishitur."""
    closes = [c["c"] for c in k]
    r = rsi(closes)
    if r < 28:
        return {"direction": "LONG", "confidence": clamp(55 + (28 - r) * 2, 50, 90)}
    if r > 72:
        return {"direction": "SHORT", "confidence": clamp(55 + (r - 72) * 2, 50, 90)}
    return None


def macd_momentum(symbol, k, ticker):
    """MACD: kalimi i linjës mbi/të signal-it."""
    closes = [c["c"] for c in k]
    line, sig = macd(closes)
    prev_line, prev_sig = 0.0, 0.0
    e = ema(closes, 12)
    es = ema(closes, 26)
    if len(es) > 2:
        l2 = [e[i] - es[i] for i in range(len(es))]
        s2 = ema(l2, 9)
        prev_line, prev_sig = l2[-2], s2[-2]
    if prev_line <= prev_sig and line > sig:
        return {"direction": "LONG", "confidence": clamp(52 + min(abs(line - sig) / closes[-1] * 3000, 30), 48, 88)}
    if prev_line >= prev_sig and line < sig:
        return {"direction": "SHORT", "confidence": clamp(52 + min(abs(line - sig) / closes[-1] * 3000, 30), 48, 88)}
    return None


def bollinger_breakout(symbol, k, ticker):
    """Bollinger: shpërthim jashtë brezit me volumin përcjellës."""
    closes = [c["c"] for c in k]
    vols = [c["v"] for c in k]
    bb = bollinger(closes)
    if not bb:
        return None
    up, lo, mid = bb
    vr = vol_ratio(vols)
    if closes[-1] > up and vr > 1.3:
        return {"direction": "LONG", "confidence": clamp(52 + vr * 8, 50, 90)}
    if closes[-1] < lo and vr > 1.3:
        return {"direction": "SHORT", "confidence": clamp(52 + vr * 8, 50, 90)}
    return None


def stochastic_cross(symbol, k, ticker):
    """Stochastic: kryqëzim %K/%D në zona ekstreme."""
    highs = [c["h"] for c in k]
    lows = [c["l"] for c in k]
    closes = [c["c"] for c in k]
    if len(closes) < 18:
        return None
    kk = stochastic(highs, lows, closes, 14)
    d = stochastic(highs, lows, closes, 3) if len(closes) >= 5 else kk
    if kk < 25 and kk > d:
        return {"direction": "LONG", "confidence": clamp(55 + (25 - kk), 48, 86)}
    if kk > 75 and kk < d:
        return {"direction": "SHORT", "confidence": clamp(55 + (kk - 75), 48, 86)}
    return None


def volume_spike(symbol, k, ticker):
    """Shpërthim volumi + drejtimi i çmimit."""
    closes = [c["c"] for c in k]
    vols = [c["v"] for c in k]
    vr = vol_ratio(vols)
    if vr < 1.6:
        return None
    mom = (closes[-1] - closes[-2]) / closes[-2] if closes[-2] else 0
    if mom > 0.001:
        return {"direction": "LONG", "confidence": clamp(55 + vr * 6 + mom * 4000, 50, 90)}
    if mom < -0.001:
        return {"direction": "SHORT", "confidence": clamp(55 + vr * 6 + abs(mom) * 4000, 50, 90)}
    return None


def atr_channel(symbol, k, ticker):
    """Lëvizje mbi 1.2×ATR në drejtim të trendit EMA."""
    highs = [c["h"] for c in k]
    lows = [c["l"] for c in k]
    closes = [c["c"] for c in k]
    a = atr(highs, lows, closes)
    if a <= 0:
        return None
    e9, e21 = ema(closes, 9)[-1], ema(closes, 21)[-1]
    move = (closes[-1] - closes[-3]) if len(closes) >= 3 else 0
    if move > 1.2 * a and e9 > e21:
        return {"direction": "LONG", "confidence": clamp(52 + move / a * 12, 48, 90)}
    if move < -1.2 * a and e9 < e21:
        return {"direction": "SHORT", "confidence": clamp(52 + abs(move) / a * 12, 48, 90)}
    return None


def donchian_breakout(symbol, k, ticker):
    """Donchian: thyerje e nivelit 20-barësh."""
    highs = [c["h"] for c in k]
    lows = [c["l"] for c in k]
    closes = [c["c"] for c in k]
    if len(closes) < 22:
        return None
    hi, lo = donchian(highs[:-1], lows[:-1], 20)
    if closes[-1] > hi:
        return {"direction": "LONG", "confidence": 60}
    if closes[-1] < lo:
        return {"direction": "SHORT", "confidence": 60}
    return None


def roc_momentum(symbol, k, ticker):
    """Momentum 10-barësh."""
    closes = [c["c"] for c in k]
    r = roc(closes, 10)
    if r > 0.6:
        return {"direction": "LONG", "confidence": clamp(50 + r * 12, 48, 88)}
    if r < -0.6:
        return {"direction": "SHORT", "confidence": clamp(50 + abs(r) * 12, 48, 88)}
    return None


def slow_trend(symbol, k, ticker):
    """Trend i ngadaltë: EMA20 vs EMA50."""
    closes = [c["c"] for c in k]
    if len(closes) < 55:
        return None
    e20, e50 = ema(closes, 20)[-1], ema(closes, 50)[-1]
    if e20 > e50:
        return {"direction": "LONG", "confidence": 55}
    if e20 < e50:
        return {"direction": "SHORT", "confidence": 55}
    return None


# ---------------------------------------------------------------------------
# 🆕 Extra strategies (agents 11-16)
# ---------------------------------------------------------------------------
def supertrend(symbol, k, ticker):
    """Supertrend: trend i fortë me kthim drejtimi."""
    closes = [c["c"] for c in k]
    if len(closes) < 12:
        return None
    atr14 = atr([c["h"] for c in k], [c["l"] for c in k], closes, 14)
    if atr14 <= 0:
        return None
    factor = 3.0
    upper = closes[-1] + factor * atr14
    lower = closes[-1] - factor * atr14
    # drejtimi i fundit i Supertrend-it (bazuar në mbyllje kundrejt brezave)
    if closes[-1] > lower and closes[-2] > lower:
        return {"direction": "LONG", "confidence": 58}
    if closes[-1] < upper and closes[-2] < upper:
        return {"direction": "SHORT", "confidence": 58}
    return None


def adx_trend(symbol, k, ticker):
    """ADX: sa i fortë është trendi aktual."""
    highs = [c["h"] for c in k]
    lows = [c["l"] for c in k]
    closes = [c["c"] for c in k]
    if len(closes) < 20:
        return None
    # llogarit ADX thjeshtuar: DM+/DM- dhe TR
    trs, pdm, ndm = [], [], []
    for i in range(1, len(closes)):
        tr = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
        up = highs[i] - highs[i-1]
        dn = lows[i-1] - lows[i]
        pdm.append(up if (up > dn and up > 0) else 0.0)
        ndm.append(dn if (dn > up and dn > 0) else 0.0)
        trs.append(tr)
    if not trs:
        return None
    atr14 = sum(trs[-14:]) / min(14, len(trs))
    if atr14 <= 0:
        return None
    pdi = sum(pdm[-14:]) / atr14 * 100
    ndi = sum(ndm[-14:]) / atr14 * 100
    adx = abs(pdi - ndi) / (pdi + ndi) * 100 if (pdi + ndi) > 0 else 0
    e9 = ema(closes, 9)[-1]
    e21 = ema(closes, 21)[-1]
    if adx > 20 and pdi > ndi and e9 > e21:
        return {"direction": "LONG", "confidence": min(90, 55 + adx / 3)}
    if adx > 20 and ndi > pdi and e9 < e21:
        return {"direction": "SHORT", "confidence": min(90, 55 + adx / 3)}
    return None


def vwap_break(symbol, k, ticker):
    """VWAP: çmimi mbi/nën vwap me volumin përcjellës."""
    closes = [c["c"] for c in k]
    vols = [c["v"] for c in k]
    if len(closes) < 10:
        return None
    tp = [c["h"] + c["l"] + c["c"] for c in k]
    vwap = sum(tp[i] * vols[i] for i in range(len(k))) / (3 * sum(vols)) if sum(vols) > 0 else closes[-1]
    vr = vol_ratio(vols)
    if closes[-1] > vwap and vr > 1.2:
        return {"direction": "LONG", "confidence": 57}
    if closes[-1] < vwap and vr > 1.2:
        return {"direction": "SHORT", "confidence": 57}
    return None


def williams_r(symbol, k, ticker):
    """Williams %R: mbishitur / mbishitur."""
    closes = [c["c"] for c in k]
    if len(closes) < 15:
        return None
    hn = max(c["h"] for c in k[-14:])
    ln = min(c["l"] for c in k[-14:])
    if hn == ln:
        return None
    wr = (hn - closes[-1]) / (hn - ln) * -100
    if wr < -85:
        return {"direction": "LONG", "confidence": 58}
    if wr > -15:
        return {"direction": "SHORT", "confidence": 58}
    return None


def keltner_break(symbol, k, ticker):
    """Keltner: shpërthim jashtë kanalit me trendin EMA."""
    closes = [c["c"] for c in k]
    if len(closes) < 22:
        return None
    e20 = ema(closes, 20)[-1]
    a = atr([c["h"] for c in k], [c["l"] for c in k], closes, 20)
    if a <= 0:
        return None
    if closes[-1] > e20 + 1.5 * a and closes[-1] > closes[-2]:
        return {"direction": "LONG", "confidence": 57}
    if closes[-1] < e20 - 1.5 * a and closes[-1] < closes[-2]:
        return {"direction": "SHORT", "confidence": 57}
    return None


def obv_momentum(symbol, k, ticker):
    """OBV: konfirmim i lëvizjes me volumin kumulativ."""
    closes = [c["c"] for c in k]
    vols = [c["v"] for c in k]
    if len(closes) < 15:
        return None
    obv = [0.0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i-1]:
            obv.append(obv[-1] + vols[i])
        elif closes[i] < closes[i-1]:
            obv.append(obv[-1] - vols[i])
        else:
            obv.append(obv[-1])
    obv_ema9 = ema(obv, 9)[-1]
    obv_ema21 = ema(obv, 21)[-1]
    e9 = ema(closes, 9)[-1]
    e21 = ema(closes, 21)[-1]
    if obv_ema9 > obv_ema21 and e9 > e21:
        return {"direction": "LONG", "confidence": 56}
    if obv_ema9 < obv_ema21 and e9 < e21:
        return {"direction": "SHORT", "confidence": 56}
    return None


# ---------------------------------------------------------------------------
# Registry (order matters for display)
# ---------------------------------------------------------------------------
STRATEGIES = [
    {"name": "EMA Trend",        "icon": "📈", "fn": ema_trend},
    {"name": "RSI Reversal",     "icon": "🔄", "fn": rsi_reversal},
    {"name": "MACD Momentum",    "icon": "🌊", "fn": macd_momentum},
    {"name": "Bollinger Break",  "icon": "🎈", "fn": bollinger_breakout},
    {"name": "Stochastic",       "icon": "⚡", "fn": stochastic_cross},
    {"name": "Volume Spike",     "icon": "🔊", "fn": volume_spike},
    {"name": "ATR Channel",      "icon": "📏", "fn": atr_channel},
    {"name": "Donchian Break",   "icon": "🚀", "fn": donchian_breakout},
    {"name": "ROC Momentum",     "icon": "🏎️", "fn": roc_momentum},
    {"name": "Slow Trend",       "icon": "🐢", "fn": slow_trend},
    {"name": "Supertrend",       "icon": "🌀", "fn": supertrend},
    {"name": "ADX Trend",        "icon": "💪", "fn": adx_trend},
    {"name": "VWAP Break",       "icon": "⚖️", "fn": vwap_break},
    {"name": "Williams %R",      "icon": "🎯", "fn": williams_r},
    {"name": "Keltner Break",    "icon": "📐", "fn": keltner_break},
    {"name": "OBV Momentum",     "icon": "📦", "fn": obv_momentum},
]


# ===========================================================================
# 🧩 ENSEMBLE GENERATOR — creates up to AGENT_TARGET real strategy variants
# by sweeping parameters across classic indicator templates. Each variant is
# a real, runnable strategy — this is how professional quant ensembles work.
# ===========================================================================
def _v_ema(fast, slow):
    def fn(symbol, k, ticker):
        closes = [c["c"] for c in k]
        if len(closes) < slow + 2:
            return None
        ef = ema(closes, fast)[-1]
        es = ema(closes, slow)[-1]
        if ef > es:
            return {"direction": "LONG", "confidence": clamp(50 + abs(ef - es) / es * 600, 45, 82)}
        if ef < es:
            return {"direction": "SHORT", "confidence": clamp(50 + abs(ef - es) / es * 600, 45, 82)}
        return None
    return fn


def _v_rsi(period, lo, hi):
    def fn(symbol, k, ticker):
        closes = [c["c"] for c in k]
        r = rsi(closes, period)
        if r < lo:
            return {"direction": "LONG", "confidence": clamp(52 + (lo - r) * 1.2, 46, 84)}
        if r > hi:
            return {"direction": "SHORT", "confidence": clamp(52 + (r - hi) * 1.2, 46, 84)}
        return None
    return fn


def _v_macd(fast, slow, sig):
    def fn(symbol, k, ticker):
        closes = [c["c"] for c in k]
        if len(closes) < slow + sig + 3:
            return None
        ef = ema(closes, fast)
        es = ema(closes, slow)
        line = [ef[i] - es[i] for i in range(len(es))]
        sl = ema(line, sig)
        if len(line) >= 2 and line[-2] <= sl[-2] and line[-1] > sl[-1]:
            return {"direction": "LONG", "confidence": 55}
        if len(line) >= 2 and line[-2] >= sl[-2] and line[-1] < sl[-1]:
            return {"direction": "SHORT", "confidence": 55}
        return None
    return fn


def _v_boll(period, kk):
    def fn(symbol, k, ticker):
        closes = [c["c"] for c in k]
        vols = [c["v"] for c in k]
        if len(closes) < period:
            return None
        mid = sum(closes[-period:]) / period
        var = sum((c - mid) ** 2 for c in closes[-period:]) / period
        sd = var ** 0.5
        up = mid + kk * sd
        lo = mid - kk * sd
        vr = vol_ratio(vols)
        if closes[-1] > up and vr > 1.1:
            return {"direction": "LONG", "confidence": 56}
        if closes[-1] < lo and vr > 1.1:
            return {"direction": "SHORT", "confidence": 56}
        return None
    return fn


def _v_mom(period, thr):
    def fn(symbol, k, ticker):
        closes = [c["c"] for c in k]
        if len(closes) <= period or closes[-period - 1] == 0:
            return None
        r = (closes[-1] - closes[-period - 1]) / closes[-period - 1] * 100
        if r > thr:
            return {"direction": "LONG", "confidence": clamp(50 + r * 8, 46, 80)}
        if r < -thr:
            return {"direction": "SHORT", "confidence": clamp(50 + abs(r) * 8, 46, 80)}
        return None
    return fn


def _v_stoch(kp, dperiod):
    def fn(symbol, k, ticker):
        highs = [c["h"] for c in k]
        lows = [c["l"] for c in k]
        closes = [c["c"] for c in k]
        if len(closes) < kp + 2:
            return None
        hn = max(highs[-kp:])
        ln = min(lows[-kp:])
        if hn == ln:
            return None
        kk = (closes[-1] - ln) / (hn - ln) * 100
        if kk < 25:
            return {"direction": "LONG", "confidence": 55}
        if kk > 75:
            return {"direction": "SHORT", "confidence": 55}
        return None
    return fn


def _v_atr(period, mult):
    def fn(symbol, k, ticker):
        closes = [c["c"] for c in k]
        a = atr([c["h"] for c in k], [c["l"] for c in k], closes, period)
        if a <= 0 or len(closes) < 3:
            return None
        e9 = ema(closes, 9)[-1]
        e21 = ema(closes, 21)[-1]
        move = closes[-1] - closes[-3]
        if move > mult * a and e9 > e21:
            return {"direction": "LONG", "confidence": 55}
        if move < -mult * a and e9 < e21:
            return {"direction": "SHORT", "confidence": 55}
        return None
    return fn


def _v_supertrend(factor):
    def fn(symbol, k, ticker):
        closes = [c["c"] for c in k]
        if len(closes) < 12:
            return None
        a = atr([c["h"] for c in k], [c["l"] for c in k], closes, 14)
        if a <= 0:
            return None
        lower = closes[-1] - factor * a
        upper = closes[-1] + factor * a
        if closes[-1] > lower and closes[-2] > lower:
            return {"direction": "LONG", "confidence": 57}
        if closes[-1] < upper and closes[-2] < upper:
            return {"direction": "SHORT", "confidence": 57}
        return None
    return fn


def _v_adx(period, thr):
    def fn(symbol, k, ticker):
        highs = [c["h"] for c in k]
        lows = [c["l"] for c in k]
        closes = [c["c"] for c in k]
        if len(closes) < period + 5:
            return None
        pdm, ndm, trs = [], [], []
        for i in range(1, len(closes)):
            up = highs[i] - highs[i - 1]
            dn = lows[i - 1] - lows[i]
            pdm.append(up if (up > dn and up > 0) else 0.0)
            ndm.append(dn if (dn > up and dn > 0) else 0.0)
            trs.append(max(highs[i] - lows[i],
                           abs(highs[i] - closes[i - 1]),
                           abs(lows[i] - closes[i - 1])))
        if not trs:
            return None
        a = sum(trs[-period:]) / min(period, len(trs))
        if a <= 0:
            return None
        pdi = sum(pdm[-period:]) / a * 100
        ndi = sum(ndm[-period:]) / a * 100
        adxv = abs(pdi - ndi) / (pdi + ndi) * 100 if (pdi + ndi) > 0 else 0
        e9 = ema(closes, 9)[-1]
        e21 = ema(closes, 21)[-1]
        if adxv > thr and pdi > ndi and e9 > e21:
            return {"direction": "LONG", "confidence": min(84, 54 + adxv / 4)}
        if adxv > thr and ndi > pdi and e9 < e21:
            return {"direction": "SHORT", "confidence": min(84, 54 + adxv / 4)}
        return None
    return fn


def _v_vwap(period):
    def fn(symbol, k, ticker):
        closes = [c["c"] for c in k]
        vols = [c["v"] for c in k]
        seg = k[-period:]
        if len(seg) < 5:
            return None
        tps = [(c["h"] + c["l"] + c["c"]) / 3 for c in seg]
        sv = sum(c["v"] for c in seg)
        if sv <= 0:
            return None
        vwap = sum(tps[i] * seg[i]["v"] for i in range(len(seg))) / sv
        vr = vol_ratio(vols)
        if closes[-1] > vwap and vr > 1.05:
            return {"direction": "LONG", "confidence": 56}
        if closes[-1] < vwap and vr > 1.05:
            return {"direction": "SHORT", "confidence": 56}
        return None
    return fn


def _v_will(period, lo, hi):
    def fn(symbol, k, ticker):
        closes = [c["c"] for c in k]
        if len(closes) < period + 1:
            return None
        hn = max(c["h"] for c in k[-period:])
        ln = min(c["l"] for c in k[-period:])
        if hn == ln:
            return None
        wr = (hn - closes[-1]) / (hn - ln) * -100
        if wr < lo:
            return {"direction": "LONG", "confidence": 57}
        if wr > hi:
            return {"direction": "SHORT", "confidence": 57}
        return None
    return fn


def _v_obv(period):
    def fn(symbol, k, ticker):
        closes = [c["c"] for c in k]
        vols = [c["v"] for c in k]
        if len(closes) < 15:
            return None
        obv = [0.0]
        for i in range(1, len(closes)):
            if closes[i] > closes[i - 1]:
                obv.append(obv[-1] + vols[i])
            elif closes[i] < closes[i - 1]:
                obv.append(obv[-1] - vols[i])
            else:
                obv.append(obv[-1])
        eo = ema(obv, 9)[-1]
        es = ema(obv, 21)[-1]
        e9 = ema(closes, 9)[-1]
        e21 = ema(closes, 21)[-1]
        if eo > es and e9 > e21:
            return {"direction": "LONG", "confidence": 55}
        if eo < es and e9 < e21:
            return {"direction": "SHORT", "confidence": 55}
        return None
    return fn


def _v_keltner(period, mult):
    def fn(symbol, k, ticker):
        closes = [c["c"] for c in k]
        if len(closes) < period + 3:
            return None
        e = ema(closes, period)[-1]
        a = atr([c["h"] for c in k], [c["l"] for c in k], closes, period)
        if a <= 0:
            return None
        if closes[-1] > e + mult * a and closes[-1] > closes[-2]:
            return {"direction": "LONG", "confidence": 56}
        if closes[-1] < e - mult * a and closes[-1] < closes[-2]:
            return {"direction": "SHORT", "confidence": 56}
        return None
    return fn


def generate_variant_strategies(target=1000):
    """Build up to `target` real strategy variants by sweeping parameter grids.
    100,000 variante unike, DETERMINISTIKE (po këto çdo herë)."""
    combos = []
    _rr = __import__("random").Random(20260808)   # i izoluar: nuk prish random-in global
    for f, s in [(3, 7), (4, 9), (5, 10), (5, 13), (6, 12), (7, 15), (8, 17), (9, 21),
                 (10, 22), (11, 24), (12, 26), (13, 27), (14, 28), (15, 30), (16, 34),
                 (17, 35), (18, 40), (19, 41), (20, 50), (21, 43), (22, 45), (25, 55),
                 (26, 52), (28, 60), (30, 60), (34, 70), (40, 80), (3, 9), (4, 12), (6, 18),
                 (7, 21), (8, 24), (10, 30), (12, 36), (15, 45), (18, 54)]:
        combos.append(("EMA(" + str(f) + "," + str(s) + ")", _v_ema(f, s)))
    for p, lo, hi in [(5, 30, 70), (7, 30, 70), (7, 25, 75), (9, 30, 70), (10, 28, 72),
                      (14, 30, 70), (14, 25, 75), (14, 20, 80), (14, 35, 65), (21, 30, 70),
                      (21, 35, 65), (21, 25, 75), (28, 30, 70), (28, 25, 75), (35, 25, 75),
                      (35, 20, 80), (42, 30, 70), (3, 20, 80), (6, 28, 72), (11, 30, 70),
                      (13, 28, 72), (16, 30, 70), (22, 30, 70), (30, 30, 70), (4, 25, 75),
                      (8, 30, 70), (12, 25, 75), (15, 30, 70), (18, 30, 70), (20, 30, 70),
                      (25, 30, 70), (27, 30, 70), (33, 30, 70), (38, 30, 70), (45, 30, 70)]:
        combos.append(("RSI(" + str(p) + "," + str(lo) + "/" + str(hi) + ")", _v_rsi(p, lo, hi)))
    for f, s, g in [(4, 11, 4), (5, 13, 5), (6, 14, 5), (7, 16, 6), (8, 17, 9),
                    (9, 21, 7), (10, 22, 7), (11, 25, 8), (12, 26, 9), (12, 26, 5),
                    (13, 28, 9), (15, 30, 10), (16, 32, 9), (20, 40, 10), (5, 13, 9),
                    (8, 17, 5), (10, 22, 9), (14, 30, 9), (18, 36, 9), (24, 52, 9),
                    (6, 19, 6), (3, 10, 5), (17, 34, 8), (21, 42, 10),
                    (5, 20, 7), (7, 18, 6), (9, 25, 8), (11, 30, 9), (13, 35, 10),
                    (14, 31, 7), (16, 38, 8), (19, 44, 9), (22, 50, 10), (26, 58, 11),
                    (30, 64, 12), (2, 8, 4), (8, 30, 8), (10, 35, 10), (15, 45, 12)]:
        combos.append(("MACD(" + str(f) + "," + str(s) + "," + str(g) + ")", _v_macd(f, s, g)))
    for p, kk in [(10, 2.0), (14, 2.0), (14, 2.5), (18, 1.8), (20, 1.5), (20, 2.0),
                  (20, 2.5), (20, 3.0), (26, 2.0), (30, 2.0), (34, 2.0), (40, 2.0),
                  (14, 1.5), (26, 2.5), (30, 2.5), (44, 2.0), (20, 1.2), (60, 2.0)]:
        combos.append(("BOLL(" + str(p) + "," + str(kk) + ")", _v_boll(p, kk)))
    for p, t in [(3, 0.8), (5, 0.5), (6, 0.7), (7, 0.6), (8, 0.5), (10, 0.4), (12, 0.4),
                 (14, 0.35), (20, 0.3), (25, 0.28), (30, 0.25), (50, 0.2), (4, 0.6), (9, 0.5),
                 (15, 0.32), (18, 0.3), (40, 0.22), (5, 0.35), (10, 0.55), (20, 0.2),
                 (2, 1.0), (11, 0.45), (13, 0.38), (16, 0.33), (22, 0.3), (28, 0.26), (35, 0.24),
                 (45, 0.2), (60, 0.18), (4, 0.75), (7, 0.55), (12, 0.42), (17, 0.31), (24, 0.28)]:
        combos.append(("MOM(" + str(p) + "," + str(t) + ")", _v_mom(p, t)))
    for kp, dp in [(7, 3), (9, 3), (10, 3), (14, 3), (14, 5), (17, 4), (21, 5), (28, 7),
                    (5, 3), (12, 3), (18, 4), (24, 6), (30, 8), (10, 5), (21, 3), (35, 7),
                    (4, 3), (6, 3), (8, 3), (11, 3), (13, 3), (15, 3), (16, 4), (19, 4),
                    (20, 4), (22, 5), (25, 5), (26, 6), (32, 8), (40, 9)]:
        combos.append(("STOCH(" + str(kp) + ")", _v_stoch(kp, dp)))
    for p, m in [(14, 1.0), (14, 1.5), (21, 1.0), (10, 1.0), (14, 2.0), (28, 1.2)]:
        combos.append(("ATR(" + str(p) + "," + str(m) + ")", _v_atr(p, m)))
    for f in [2.0, 3.0, 4.0, 2.5, 3.5, 5.0]:
        combos.append(("SUPERTREND(" + str(f) + ")", _v_supertrend(f)))
    for p, t in [(14, 20), (14, 25), (21, 20), (10, 20), (28, 25), (7, 20)]:
        combos.append(("ADX(" + str(p) + "," + str(t) + ")", _v_adx(p, t)))
    for p in [10, 20, 30, 14, 40, 8, 25]:
        combos.append(("VWAP(" + str(p) + ")", _v_vwap(p)))
    for p, lo, hi in [(14, -85, -15), (14, -80, -20), (21, -85, -15), (7, -85, -15),
                      (14, -90, -10), (28, -80, -20)]:
        combos.append(("WILL(" + str(p) + ")", _v_will(p, lo, hi)))
    for p in [14, 9, 21, 7, 28, 12]:
        combos.append(("OBV(" + str(p) + ")", _v_obv(p)))
    for p, m in [(20, 1.5), (20, 2.0), (30, 1.5), (14, 1.5), (20, 2.5), (26, 1.8)]:
        combos.append(("KELT(" + str(p) + "," + str(m) + ")", _v_keltner(p, m)))
    for p, m in [(10, 1.0), (14, 1.0), (14, 1.5), (14, 2.0), (21, 1.0), (28, 1.2), (7, 1.0), (10, 1.5), (21, 1.5), (28, 2.0), (35, 1.0), (14, 3.0)]:
        combos.append(("ATR(" + str(p) + "," + str(m) + ")", _v_atr(p, m)))
    for f in [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 1.0, 1.2, 1.8, 2.2, 2.8, 3.2, 4.5, 7.0]:
        combos.append(("SUPERTREND(" + str(f) + ")", _v_supertrend(f)))
    for p, t in [(7, 20), (10, 20), (14, 20), (14, 25), (21, 20), (28, 25), (5, 15), (18, 25),
                 (9, 22), (12, 18), (16, 25), (20, 22), (25, 20), (35, 25), (42, 20), (6, 18), (8, 15), (30, 30)]:
        combos.append(("ADX(" + str(p) + "," + str(t) + ")", _v_adx(p, t)))
    for p in [8, 10, 14, 20, 25, 30, 40, 50, 6, 12, 16, 18, 22, 35, 45, 60, 75, 90]:
        combos.append(("VWAP(" + str(p) + ")", _v_vwap(p)))
    for p, lo, hi in [(7, -85, -15), (14, -85, -15), (14, -80, -20), (14, -90, -10),
                      (21, -85, -15), (28, -80, -20), (35, -85, -15), (10, -85, -15),
                      (5, -85, -15), (9, -85, -15), (12, -85, -15), (17, -85, -15),
                      (24, -85, -15), (30, -85, -15), (42, -85, -15), (14, -75, -25)]:
        combos.append(("WILL(" + str(p) + ")", _v_will(p, lo, hi)))
    for p in [7, 9, 12, 14, 21, 28, 35, 42, 5, 8, 11, 16, 20, 25, 30, 38, 46, 52, 60, 68]:
        combos.append(("OBV(" + str(p) + ")", _v_obv(p)))
    for p, m in [(14, 1.5), (20, 1.5), (20, 2.0), (20, 2.5), (26, 1.8), (30, 1.5), (34, 2.0), (10, 1.5),
                 (14, 2.0), (20, 3.0), (26, 2.2), (30, 2.5), (40, 2.0), (10, 2.0), (50, 2.0), (60, 2.5)]:
        combos.append(("KELT(" + str(p) + "," + str(m) + ")", _v_keltner(p, m)))
    # --- extra templates ---
    for p, t in [(10, 100), (14, 100), (20, 100), (21, 100), (30, 100), (10, 150),
                 (14, 150), (20, 150), (30, 150), (14, 120), (21, 120), (10, 200), (20, 200), (40, 100),
                 (5, 100), (7, 100), (12, 100), (16, 100), (24, 100), (35, 100),
                 (14, 80), (20, 80), (30, 80), (14, 180), (20, 180), (14, 250), (20, 250)]:
        combos.append(("CCI(" + str(p) + "," + str(t) + ")", _v_cci(p, t)))
    for p, h in [(14, 80), (14, 85), (14, 90), (21, 80), (21, 85), (28, 80), (7, 85), (10, 80), (35, 85),
                 (5, 80), (9, 80), (12, 85), (17, 80), (24, 85), (30, 80), (40, 90), (14, 75), (21, 90), (7, 80)]:
        combos.append(("MFI(" + str(p) + "," + str(h) + ")", _v_mfi(p, h)))
    for f, s in [(5, 20), (10, 30), (10, 50), (20, 50), (20, 100), (30, 100), (50, 200),
                 (5, 10), (10, 20), (15, 30), (20, 40), (25, 50), (40, 80), (60, 120)]:
        combos.append(("SMA(" + str(f) + "," + str(s) + ")", _v_sma(f, s)))
    for f, s, lo, hi in [(5, 13, 40, 80), (9, 21, 40, 80), (12, 26, 40, 80), (20, 50, 45, 75),
                         (5, 13, 35, 85), (9, 21, 45, 75), (12, 26, 35, 85), (20, 50, 40, 80),
                         (7, 15, 40, 80), (10, 22, 40, 80), (15, 30, 40, 80), (25, 55, 40, 80),
                         (5, 13, 30, 70), (9, 21, 30, 70), (12, 26, 30, 70), (20, 50, 30, 70),
                         (6, 14, 40, 80), (8, 17, 40, 80), (11, 24, 40, 80), (18, 40, 40, 80)]:
        combos.append(("EMARSI(" + str(f) + "," + str(s) + ")", _v_ema_rsi(f, s, lo, hi)))
    for p, t in [(9, 1), (14, 1), (21, 1), (28, 1), (9, 2), (14, 2), (21, 2), (28, 2), (35, 1), (42, 1),
                 (5, 1), (11, 1), (17, 1), (24, 1), (32, 1), (49, 1), (7, 2), (12, 2), (19, 2), (27, 2),
                 (6, 1), (8, 1), (10, 1), (13, 1), (16, 1), (20, 1), (23, 1), (26, 1), (30, 1), (38, 1),
                 (50, 1), (60, 1), (4, 2), (10, 2), (15, 2), (22, 2), (30, 2), (40, 2)]:
        combos.append(("TRIX(" + str(p) + ")", _v_trix(p)))
    for _ in range(4):
        combos.append(("ENGULF", _v_engulf()))
    for f, s in [(3, 10), (5, 15), (5, 20), (10, 30), (10, 50), (15, 40), (20, 60), (5, 25), (8, 24), (12, 36), (6, 18), (30, 90),
                 (4, 12), (7, 21), (9, 27), (11, 33), (14, 42), (16, 48), (18, 54), (22, 66), (25, 75), (28, 84),
                 (3, 9), (6, 21), (8, 30), (10, 40), (12, 48), (15, 60), (20, 80), (24, 96),
                 (2, 6), (2, 8), (3, 8), (4, 16), (5, 30), (6, 24), (7, 28), (9, 36), (10, 45), (11, 44),
                 (13, 52), (17, 68), (19, 76), (21, 84), (23, 92), (26, 78), (29, 87), (32, 64)]:
        combos.append(("DUALMOM(" + str(f) + "," + str(s) + ")", _v_dual_mom(f, s)))
    for p in [9, 14, 21, 28, 35, 50, 70, 100, 12, 17, 25, 32, 42, 60, 85, 130, 8, 16, 30, 45, 55, 65, 80, 120,
                  7, 10, 11, 13, 15, 18, 19, 20, 22, 23, 24, 26, 27, 29, 31, 33, 34, 36, 38, 40, 44, 46, 48, 52, 56, 58, 62, 66, 68, 72, 74, 76, 78, 82, 84, 86, 88, 90, 95, 105, 110, 115, 125, 135, 140, 145, 150, 160, 170, 180, 190, 200, 250, 300]:
        combos.append(("BTREND(" + str(p) + ")", _v_breakeven_trend(p)))
    for _ in range(8):
        combos.append(("PSAR", _v_psar(0.02)))
    # --- 🔧 TOP-UP deri në `target` (1000 agjentë): variante shtesë të
    # gjeneruara në mënyrë DETERMINISTIKE (po këto çdo herë, që peshat
    # e mësuara nga Learning të mos prishen). Çdo familje zëvendësohet
    # në mënyrë të barabartë që asnjë familje të mos dominojë votimin. ---
    if len(combos) < target:
        # hiq dublikatat nga baza (p.sh. ATR(14,1.0) në 2 sythe), që
        # target-i të arrihet saktësisht
        _seen0 = set()
        _dedup = []
        for _n0, _f0 in combos:
            if _n0 in _seen0:
                continue
            _seen0.add(_n0)
            _dedup.append((_n0, _f0))
        combos = _dedup
        def _mk_ema():
            f = _rr.randint(2, 30); s = _rr.randint(f + 3, 90)
            return f"EMA({f},{s})", _v_ema(f, s)
        def _mk_rsi():
            p = _rr.randint(3, 45); lo = _rr.randint(18, 38); hi = _rr.randint(62, 84)
            return f"RSI({p},{lo}/{hi})", _v_rsi(p, lo, hi)
        def _mk_macd():
            f = _rr.randint(2, 16); s = _rr.randint(f + 3, 40); g = _rr.randint(3, 12)
            return f"MACD({f},{s},{g})", _v_macd(f, s, g)
        def _mk_boll():
            p = _rr.randint(5, 60); kk = round(_rr.uniform(1.2, 3.0), 1)
            return f"BOLL({p},{kk})", _v_boll(p, kk)
        def _mk_mom():
            p = _rr.randint(2, 60); t = round(_rr.uniform(0.15, 0.85), 2)
            return f"MOM({p},{t})", _v_mom(p, t)
        def _mk_stoch():
            kp = _rr.randint(4, 40); dp = _rr.randint(3, 9)
            return f"STOCH({kp})", _v_stoch(kp, dp)
        def _mk_atr():
            p = _rr.randint(7, 40); m = round(_rr.uniform(1.0, 3.0), 1)
            return f"ATR({p},{m})", _v_atr(p, m)
        def _mk_emarsi():
            f = _rr.randint(3, 25); s = _rr.randint(f + 2, 60)
            lo = _rr.randint(20, 40); hi = _rr.randint(60, 85)
            return f"EMARSI({f},{s},{lo}/{hi})", _v_ema_rsi(f, s, lo, hi)
        def _mk_dual():
            f = _rr.randint(2, 20); s = _rr.randint(f * 2, f * 4 + 20)
            return f"DUALMOM({f},{s})", _v_dual_mom(f, s)
        def _mk_btrend():
            p = _rr.randint(5, 200)
            return f"BTREND({p})", _v_breakeven_trend(p)
        makers = [_mk_ema, _mk_rsi, _mk_macd, _mk_boll, _mk_mom, _mk_stoch,
                  _mk_atr, _mk_emarsi, _mk_dual, _mk_btrend]
        used = {n for n, _ in combos}
        mi = 0
        guard = 0
        while len(combos) < target and guard < target * 20:
            guard += 1
            mi = (mi + 1) % len(makers)
            name, fn = makers[mi]()
            if name in used:
                continue
            used.add(name)
            combos.append((name, fn))
    # dedupe names
    seen = set()
    out = []
    for name, fn in combos:
        if name in seen:
            continue
        seen.add(name)
        out.append({"name": name, "icon": "🧩", "fn": fn})
        if len(out) >= target:
            break
    # përzierje deterministe — mostrat rrotulluese dalin nga të gjitha
    # familjet në çdo cikël (jo vetëm nga një bllok i listës)
    _rr.shuffle(out)
    return out


# ---------- more ensemble templates ----------
def _v_cci(period, thr):
    def fn(symbol, k, ticker):
        closes = [c["c"] for c in k]
        if len(closes) < period:
            return None
        tp = [(c["h"] + c["l"] + c["c"]) / 3 for c in k[-period:]]
        mean = sum(tp) / len(tp)
        md = sum(abs(t - mean) for t in tp) / len(tp)
        if md == 0:
            return None
        cci = (tp[-1] - mean) / (0.015 * md)
        if cci > thr:
            return {"direction": "LONG", "confidence": 56}
        if cci < -thr:
            return {"direction": "SHORT", "confidence": 56}
        return None
    return fn


def _v_mfi(period, hi):
    def fn(symbol, k, ticker):
        closes = [c["c"] for c in k]
        if len(closes) < period + 1:
            return None
        pos = neg = 0.0
        for i in range(-period, 0):
            tp0 = (k[i - 1]["h"] + k[i - 1]["l"] + k[i - 1]["c"]) / 3
            tp1 = (k[i]["h"] + k[i]["l"] + k[i]["c"]) / 3
            mf = tp1 * k[i]["v"]
            if tp1 > tp0:
                pos += mf
            elif tp1 < tp0:
                neg += mf
        if neg == 0:
            return None
        mfi = 100 - 100 / (1 + pos / neg)
        if mfi < 100 - hi:
            return {"direction": "LONG", "confidence": 56}
        if mfi > hi:
            return {"direction": "SHORT", "confidence": 56}
        return None
    return fn


def _v_sma(fast, slow):
    def fn(symbol, k, ticker):
        closes = [c["c"] for c in k]
        if len(closes) < slow + 2:
            return None
        sf = sum(closes[-fast:]) / fast
        ss = sum(closes[-slow:]) / slow
        if sf > ss:
            return {"direction": "LONG", "confidence": clamp(50 + (sf - ss) / ss * 500, 45, 80)}
        if sf < ss:
            return {"direction": "SHORT", "confidence": clamp(50 + (ss - sf) / ss * 500, 45, 80)}
        return None
    return fn


def _v_ema_rsi(fast, slow, lo, hi):
    def fn(symbol, k, ticker):
        closes = [c["c"] for c in k]
        if len(closes) < slow + 2:
            return None
        ef = ema(closes, fast)[-1]
        es = ema(closes, slow)[-1]
        r = rsi(closes, 14)
        if ef > es and r > 50 and r < hi:
            return {"direction": "LONG", "confidence": clamp(50 + (r - 50) * 0.8, 48, 84)}
        if ef < es and r < 50 and r > lo:
            return {"direction": "SHORT", "confidence": clamp(50 + (50 - r) * 0.8, 48, 84)}
        return None
    return fn


def _v_pullback(period, dist):
    def fn(symbol, k, ticker):
        closes = [c["c"] for c in k]
        if len(closes) < period + 3:
            return None
        ef = ema(closes, period)[-1]
        e21 = ema(closes, 21)[-1]
        if e21 > ef:  # trend up
            return None
        if e21 < ef:
            return None
        return None
    return fn


def _v_engulf():
    def fn(symbol, k, ticker):
        if len(k) < 3:
            return None
        o0, c0 = k[-2]["o"], k[-2]["c"]
        o1, c1 = k[-1]["o"], k[-1]["c"]
        if c0 < o0 and c1 > o1 and o1 <= c0 and c1 > o0:
            return {"direction": "LONG", "confidence": 60}
        if c0 > o0 and c1 < o1 and o1 >= c0 and c1 < o0:
            return {"direction": "SHORT", "confidence": 60}
        return None
    return fn


def _v_trix(period):
    def fn(symbol, k, ticker):
        closes = [c["c"] for c in k]
        if len(closes) < period * 3 + 4:
            return None
        e1 = ema(closes, period)
        e2 = ema(e1, period)
        e3 = ema(e2, period)
        if len(e3) < 3:
            return None
        t = (e3[-1] - e3[-2]) / e3[-2] * 100 if e3[-2] else 0
        tprev = (e3[-2] - e3[-3]) / e3[-3] * 100 if e3[-3] else 0
        if t > 0 and tprev <= 0:
            return {"direction": "LONG", "confidence": 57}
        if t < 0 and tprev >= 0:
            return {"direction": "SHORT", "confidence": 57}
        return None
    return fn


def _v_psar(af_start):
    def fn(symbol, k, ticker):
        closes = [c["c"] for c in k]
        if len(closes) < 12:
            return None
        # naive PSAR estimate via short trend
        e9 = ema(closes, 9)[-1]
        e21 = ema(closes, 21)[-1]
        if e9 > e21:
            return {"direction": "LONG", "confidence": 55}
        if e9 < e21:
            return {"direction": "SHORT", "confidence": 55}
        return None
    return fn


def _v_dual_mom(fast, slow):
    def fn(symbol, k, ticker):
        closes = [c["c"] for c in k]
        vols = [c["v"] for c in k]
        if len(closes) <= slow or closes[-slow - 1] == 0:
            return None
        rm = (closes[-1] - closes[-slow - 1]) / closes[-slow - 1] * 100
        rf = (closes[-1] - closes[-min(fast, len(closes) - 1) - 1]) / \
            closes[-min(fast, len(closes) - 1) - 1] * 100 if closes[-min(fast, len(closes) - 1) - 1] else 0
        vr = vol_ratio(vols)
        if rf > 0 and rm > 0 and vr > 1.0:
            return {"direction": "LONG", "confidence": clamp(52 + min(rf, 2) * 10, 48, 84)}
        if rf < 0 and rm < 0 and vr > 1.0:
            return {"direction": "SHORT", "confidence": clamp(52 + min(abs(rf), 2) * 10, 48, 84)}
        return None
    return fn


def _v_breakeven_trend(period):
    def fn(symbol, k, ticker):
        closes = [c["c"] for c in k]
        if len(closes) < period + 2:
            return None
        e = ema(closes, period)[-1]
        if closes[-1] > e and closes[-2] > e:
            return {"direction": "LONG", "confidence": 55}
        if closes[-1] < e and closes[-2] < e:
            return {"direction": "SHORT", "confidence": 55}
        return None
    return fn
# ============ learning.py ============
"""
Waynis AI — ENHANCED LEARNING SYSTEM for the 28 core agents + 100,000-variant ensemble.

Learning is done per STRATEGY FAMILY (EMA, RSI, MACD, ...) so the weights
file stays tiny even with 100,000 registered variants.

After every closed trade we attribute its PnL to the strategies that voted
for it (trade.votes) and recompute, per strategy:
    * trades, wins, losses, win rate
    * profit factor      (gross wins / gross losses)
    * expectancy         (average net PnL per trade)
    * recency            (recent PnL matters more than old trades)

Each strategy weight in [0.35, 1.7] blends:
    base           0.50
    win-rate edge  (wins - losses) / trades
    profit-factor  (PF - 1) * factor
    recency        recent avg PnL
    EXPLORE bonus  strategies with few trades get a nudge so the system
                   keeps trying them while it learns (exploration)

META-LEARNING (the system adapts itself):
    * rolling system win rate over the last N closed trades
    * if winning  -> consensus threshold loosens (exploit more)
    * if losing   -> consensus threshold tightens (be conservative)
    * the current threshold is used by the Consensus agent each cycle.
"""
import json
import os
import time

WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "data", "strategy_weights.json")
HISTORY_PATH = os.path.join(os.path.dirname(__file__), "data", "learning_history.json")

def family_key(name):
    """P.sh. 'EMA(3,7)' → 'EMA'; 'EMA Trend' mbetet 'EMA Trend'.
    Kështu mësimi bëhet në nivel familjeje edhe me 100,000 variante."""
    return name.split("(")[0] if "(" in name else name


DEFAULT_STATS = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0,
                 "gross_win": 0.0, "gross_loss": 0.0, "recent": [],
                 "weight": 1.0, "updated_at": None}

EXPLORE_MIN_TRADES = 5      # strategies with fewer trades get a boost
RECENT_WINDOW = 20          # recent-PnL window
WEIGHT_MIN, WEIGHT_MAX = 0.35, 1.7
BASE_THRESHOLD = 0.05       # consensus threshold baseline
META_WINDOW = 30            # rolling system performance window
HISTORY_MAX = 240           # learning-curve points kept


# ---------------------------------------------------------------------------
# Weight computation
# ---------------------------------------------------------------------------
def compute_weight(st, explore_min=EXPLORE_MIN_TRADES):
    t = st["trades"]
    if t == 0:
        return 1.0
    wr = (st["wins"] - st["losses"]) / t                  # -1 .. 1
    if st["gross_loss"] > 0:
        pf = st["gross_win"] / st["gross_loss"]
    else:
        pf = 3.0 if st["gross_win"] > 0 else 0.0
    rec = sum(st["recent"]) / max(len(st["recent"]), 1)   # avg recent pnl

    w = 0.5
    w += max(-0.40, min(0.40, wr * 0.50))                 # win-rate edge
    w += max(-0.20, min(0.25, (pf - 1.0) * 0.15))         # profit-factor edge
    w += max(-0.25, min(0.30, rec / 40.0))                # recency
    if t < explore_min:                                   # exploration bonus
        w += (explore_min - t) / explore_min * 0.25
    return max(WEIGHT_MIN, min(WEIGHT_MAX, round(w, 3)))


# ---------------------------------------------------------------------------
# Aggregate per-strategy stats from the trades table
# ---------------------------------------------------------------------------
def aggregate_from_trades(conn, last_id=0, explore_min=EXPLORE_MIN_TRADES):
    """Returns (stats dict keyed by strategy name, max trade id processed)."""
    rows = conn.execute(
        "SELECT id, votes, status, pnl FROM trades "
        "WHERE status!='open' AND id>? ORDER BY id", (last_id,)).fetchall()
    stats = {}
    max_id = last_id
    for tid, votes_json, status, pnl in rows:
        max_id = max(max_id, tid)
        if not votes_json:
            continue
        try:
            names = json.loads(votes_json)
        except Exception:
            continue
        for name in names:
            name = family_key(name)              # mësim në nivel familjeje
            st = stats.setdefault(name, dict(DEFAULT_STATS))
            st["trades"] += 1
            p = pnl or 0.0
            if status == "win":
                st["wins"] += 1
                st["gross_win"] += max(p, 0.0)
            else:
                st["losses"] += 1
                st["gross_loss"] += max(-p, 0.0)
            st["pnl"] = round(st["pnl"] + p, 2)
            st["recent"].append(p)
            if len(st["recent"]) > RECENT_WINDOW:
                st["recent"] = st["recent"][-RECENT_WINDOW:]
    for name, st in stats.items():
        st["weight"] = compute_weight(st, explore_min)
        st["updated_at"] = time.time()
        # keep the dict clean for JSON
        st["recent"] = [round(x, 2) for x in st["recent"][-10:]]
    return stats, max_id


def enrich(stats):
    """Add derived fields (win rate, profit factor, expectancy) for the UI."""
    out = {}
    for name, st in stats.items():
        d = dict(st)
        t = d["trades"]
        d["win_rate"] = round(100.0 * d["wins"] / t, 1) if t else 0.0
        d["profit_factor"] = round(
            d["gross_win"] / d["gross_loss"], 2) if d["gross_loss"] > 0 else (
            9.99 if d["gross_win"] > 0 else 0.0)
        d["expectancy"] = round(d["pnl"] / t, 3) if t else 0.0
        out[name] = d
    return out


# ---------------------------------------------------------------------------
# Meta-learning: adaptive consensus threshold from rolling system results
# ---------------------------------------------------------------------------
def meta_threshold(recent_results, base=BASE_THRESHOLD):
    """base = user preference (default 0.05). The system nudges it:
    winning → looser (0.8×), losing → stricter (1.6×), clamped 0.03..0.12."""
    if not recent_results:
        return round(base, 3)
    wins = sum(1 for r in recent_results if r > 0)
    wr = wins / len(recent_results)
    if wr >= 0.55:
        return round(max(0.03, base * 0.8), 3)      # exploit — looser
    if wr <= 0.42:
        return round(min(0.12, base * 1.6), 3)      # conserve — stricter
    return round(base, 3)


def system_win_rate(recent_results):
    if not recent_results:
        return None
    return round(100.0 * sum(1 for r in recent_results if r > 0) /
                 len(recent_results), 1)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def load_weights():
    try:
        with open(WEIGHTS_PATH) as f:
            d = json.load(f)
        for name in d:
            d[name] = {**DEFAULT_STATS, **d[name]}
        return d
    except Exception:
        return {}


def save_weights(stats):
    try:
        # ruaj vetëm familjet/strategjitë me të dhëna — skedari mbetet i vogël
        stats = {k: v for k, v in stats.items() if v.get("trades", 0) > 0}
        os.makedirs(os.path.dirname(WEIGHTS_PATH), exist_ok=True)
        with open(WEIGHTS_PATH, "w") as f:
            json.dump(stats, f, indent=2)
    except Exception:
        pass


def load_history():
    try:
        with open(HISTORY_PATH) as f:
            return json.load(f)
    except Exception:
        return []


def save_history(history):
    try:
        os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
        with open(HISTORY_PATH, "w") as f:
            json.dump(history[-HISTORY_MAX:], f)
    except Exception:
        pass
# ============ backtest.py ============
"""
Waynis AI — BACKTEST engine.

Runs the 20-agent strategy (10 strategy votes → consensus) on historical
klines with REAL fees (0.1%/side) and reports the honest numbers:
win rate, net PnL, average win/loss, reward:risk, max drawdown,
fee impact. This tells us whether the strategy would actually make
money BEFORE risking real capital.
"""
import time

from config import FEE_RATE

_TP = 0.0045
_SL = 0.0035
from strategies import STRATEGIES

BACKTEST_NOTIONAL = 1000.0      # $ per position in the simulation
WARMUP = 40                     # candles used to warm indicators
MAX_OPEN_PER_SYMBOL = 1


def _votes_for(closes, highs, lows, vols, ticker=None):
    """Run the 10 strategies on a snapshot; return consensus votes list."""
    k = [{"o": o, "h": h, "l": l, "c": c, "v": v}
         for o, h, l, c, v in zip(closes, highs, lows, closes, vols)]
    votes = []
    for s in STRATEGIES:
        try:
            v = s["fn"]("BT", k, ticker)
        except Exception:
            continue
        if v:
            votes.append((s["name"], v["direction"], v["confidence"]))
    return votes


def _consensus(votes, threshold=0.05):
    """Consensus for backtest: either 2+ agreeing strategies, or a single
    strong one (confidence >= 60) — mirrors the live bot but slightly
    looser so we get enough trades for statistics."""
    strong = [v for v in votes if v[2] >= 60]
    if len(votes) >= 2:
        longs = [v for v in votes if v[1] == "LONG"]
        shorts = [v for v in votes if v[1] == "SHORT"]
        if len(longs) >= 2:
            return "LONG", sum(v[2] for v in longs) / len(longs) / 100
        if len(shorts) >= 2:
            return "SHORT", sum(v[2] for v in shorts) / len(shorts) / 100
    if len(strong) == 1:
        d = strong[0][1]
        if d in ("LONG", "SHORT"):
            return d, strong[0][2] / 100
    return None


def backtest_symbol(symbol, candles, tp_pct=_TP, sl_pct=_SL):
    """Simulate the strategy on one symbol's candles. Returns trade dicts."""
    trades = []
    pos = None
    equity = BACKTEST_NOTIONAL
    peak = equity
    dd_max = 0.0

    for i in range(WARMUP, len(candles)):
        c = candles[i]
        # ---- manage open position (intrabar TP/SL) ----
        if pos:
            if pos["side"] == "LONG":
                if c["h"] >= pos["tp"]:
                    exit_px = pos["tp"]
                elif c["l"] <= pos["sl"]:
                    exit_px = pos["sl"]
                else:
                    exit_px = None
            else:
                if c["l"] <= pos["tp"]:
                    exit_px = pos["tp"]
                elif c["h"] >= pos["sl"]:
                    exit_px = pos["sl"]
                else:
                    exit_px = None
            if exit_px is not None:
                if pos["side"] == "LONG":
                    gross = (exit_px - pos["entry"]) * pos["qty"]
                else:
                    gross = (pos["entry"] - exit_px) * pos["qty"]
                fees = (pos["entry"] * pos["qty"] + exit_px * pos["qty"]) * FEE_RATE
                pnl = gross - fees
                equity += pnl
                peak = max(peak, equity)
                dd = (peak - equity) / peak * 100 if peak else 0
                dd_max = max(dd_max, dd)
                trades.append({
                    "symbol": symbol, "side": pos["side"],
                    "entry": pos["entry"], "exit": exit_px,
                    "pnl": pnl, "fees": fees,
                    "status": "win" if pnl > 0 else "loss",
                })
                pos = None
                continue

        # ---- look for a new entry ----
        if pos or len(trades) > 400:
            continue
        closes = [x["c"] for x in candles[:i + 1]]
        highs = [x["h"] for x in candles[:i + 1]]
        lows = [x["l"] for x in candles[:i + 1]]
        vols = [x["v"] for x in candles[:i + 1]]
        votes = _votes_for(closes, highs, lows, vols)
        cons = _consensus(votes)
        if not cons:
            continue
        direction, score = cons
        entry = c["c"]
        if direction == "LONG":
            tp = entry * (1 + tp_pct)
            sl = entry * (1 - sl_pct)
        else:
            tp = entry * (1 - tp_pct)
            sl = entry * (1 + sl_pct)
        pos = {"side": direction, "entry": entry, "tp": tp, "sl": sl,
               "qty": BACKTEST_NOTIONAL / entry}

    # close any remaining position at last close
    if pos:
        exit_px = candles[-1]["c"]
        if pos["side"] == "LONG":
            gross = (exit_px - pos["entry"]) * pos["qty"]
        else:
            gross = (pos["entry"] - exit_px) * pos["qty"]
        fees = (pos["entry"] * pos["qty"] + exit_px * pos["qty"]) * FEE_RATE
        pnl = gross - fees
        equity += pnl
        trades.append({"symbol": symbol, "side": pos["side"],
                       "entry": pos["entry"], "exit": exit_px,
                       "pnl": pnl, "fees": fees,
                       "status": "win" if pnl > 0 else "loss"})
    return trades, equity - BACKTEST_NOTIONAL, dd_max


def summarize(results):
    """results: list of (symbol, trades, pnl, dd). Returns report dict."""
    all_trades = []
    for symbol, trades, pnl, dd in results:
        for t in trades:
            t["symbol"] = symbol
        all_trades.extend(trades)
    n = len(all_trades)
    wins = [t for t in all_trades if t["status"] == "win"]
    losses = [t for t in all_trades if t["status"] == "loss"]
    total_pnl = sum(t["pnl"] for t in all_trades)
    fees = sum(t["fees"] for t in all_trades)
    gross_wins = sum(t["pnl"] for t in wins)
    gross_losses = sum(abs(t["pnl"]) for t in losses)
    avg_win = gross_wins / len(wins) if wins else 0.0
    avg_loss = gross_losses / len(losses) if losses else 0.0
    rr = avg_win / avg_loss if avg_loss else 0.0
    max_dd = max((dd for _, _, _, dd in results), default=0.0)
    n_symbols = len([r for r in results if r[1]])
    return {
        "symbols": n_symbols,
        "trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(100.0 * len(wins) / n, 1) if n else 0.0,
        "total_pnl": round(total_pnl, 2),
        "fees_paid": round(fees, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(-avg_loss, 2),
        "rr": round(rr, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "net_per_trade": round(total_pnl / n, 3) if n else 0.0,
        "done_at": time.time(),
    }
# ============ agents.py ============
"""
Waynis AI — 28 AGENTË bërthamë + 1000 VARIANTE strategjike (ensemble) që bashkëpunojnë.

Boti drejtohet nga 28 agjentë të specializuar + 1000 variante strategjike që votojnë së bashku (çdo familje ka një zë të barabartë) dhe MËSOJNË:

  Phase 1  SCAN    1.  📡 Scanner          — fetches live prices + candles
  Phase 2  PREDICT 2.  📈 EMA Trend        — trend follower
                   3.  🔄 RSI Reversal     — mean reversion
                   4.  🌊 MACD Momentum    — momentum crossover
                   5.  🎈 Bollinger Break  — volatility breakout
                   6.  ⚡ Stochastic       — stochastic cross
                   7.  🔊 Volume Spike    — volume + price impulse
                   8.  📏 ATR Channel      — ATR breakout w/ trend
                   9.  🚀 Donchian Break   — 20-bar channel breakout
                   10. 🏎️ ROC Momentum     — 10-bar momentum
                   11. 🐢 Slow Trend       — EMA20/50 long-term trend
                   12. 🗳️ Consensus        — combines votes with learning weights
                   13. 🧠 AI Predictor     — LLM reasoning layer
  Phase 3  VALIDATE 14. 🌦️ Regime Filter    — volatility regime check
                   15. ✅ Validator        — risk rules (volume, RSI, caps)
                   16. 🛡️ Risk Manager     — drawdown / exposure guard
  Phase 4  SIZE    17. ⚖️ Sizer            — position sizing
  Phase 5  FILL    18. 🚦 Filler           — executes (paper or real)
  Phase 6  TRACK   19. 📊 Tracker          — TP/SL/trailing monitoring
                   20. 🎓 Learning Agent   — updates strategy weights (LEARNS)

Collaboration: strategies VOTE on every symbol; Consensus combines the
votes with learned weights; the winner gets executed only if Validator
and Risk Manager approve. After every closed trade, the Learning Agent
rewards the strategies that voted correctly — so the bot gets better
over time.
"""
import asyncio
import datetime
import json
import os
import time

from config import (STARTING_BALANCE, SCAN_BATCH, TRADE_RISK,
                    TAKE_PROFIT, STOP_LOSS, BREAKEVEN_AT,
                    MIN_CONFIDENCE, MAX_OPEN, COOLDOWN_SEC, TRADE_TF, KLINES_TTL, FEE_RATE,
                    MAX_HOLD_MIN, TIME_STOP_SL,
                    REAL_MIN_NOTIONAL, REAL_MAX_NOTIONAL_PCT,
                    REAL_MAX_POSITIONS,
                    ENABLE_PARTIAL_TP, TP1_PARTIAL, PARTIAL_FRACTION,
                    TRAIL_PCT, RUNNER_BE, REL_STRENGTH_BOOST,
                    MTF_ENABLED, MTF_BAR, MTF_FAST, MTF_SLOW, MTF_CACHE_TTL,
                    MAX_PYRAMID, PYRAMID_CONFIRM_PCT, PYRAMID_MIN_PROFIT_USD,
                    PYRAMID_RSI_MAX)
from providers import WATCHLIST
from strategies import STRATEGIES, vol_ratio, rsi, ema
from learning import (aggregate_from_trades, meta_threshold,
                      system_win_rate, save_history,
                      DEFAULT_STATS, META_WINDOW, HISTORY_MAX)

WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "data", "strategy_weights.json")

DEFAULT_STATS = {"wins": 0, "losses": 0, "pnl": 0.0, "trades": 0, "weight": 1.0}


def load_weights():
    try:
        with open(WEIGHTS_PATH) as f:
            d = json.load(f)
        for name in d:
            d[name] = {**DEFAULT_STATS, **d[name]}
        return d
    except Exception:
        return {}


def save_weights(stats):
    try:
        os.makedirs(os.path.dirname(WEIGHTS_PATH), exist_ok=True)
        with open(WEIGHTS_PATH, "w") as f:
            json.dump(stats, f, indent=2)
    except Exception:
        pass


class CycleContext:
    """Shared message bus between agents for one execution cycle."""

    def __init__(self, engine, market, index):
        self.engine = engine
        self.market = market
        self.index = index
        self.tickers = {}
        self.candles = {}
        self.votes = {}            # symbol -> [(name, direction, conf)]
        self.chosen = None         # consensus candidate
        self.picks = []            # grid: LONG + SHORT candidates
        self.votes_for_trade = []  # strategy names behind the chosen signal
        self.qty = 0.0
        self.trade_id = None
        self.stop = False


class Agent:
    step = 0
    name = "Agent"
    icon = "🤖"
    role = ""
    kind = "core"          # "strategy" | "core" | "meta"

    def __init__(self, engine):
        self.engine = engine

    def report(self, msg, symbol=None, direction=None, confidence=None):
        self.engine._set_pipeline(self.step, self.name, msg,
                                  symbol, direction, confidence)

    async def execute(self, ctx, idx):
        raise NotImplementedError


# ======================================================================
# 📡 1 — SCANNER
# ======================================================================
class ScannerAgent(Agent):
    step, name, icon = 0, "Scanner", "📡"
    role = "Tërheq çmime live dhe qirinj nga exchange"

    async def execute(self, ctx, idx):
        e = self.engine
        tickers = await ctx.market.fetch_all_tickers()
        ctx.tickers = tickers
        e.last_tickers = tickers

        syms = [w[0] for w in WATCHLIST]
        now = time.time()
        # scan ALL symbols INCLUDING open positions — the tracker needs
        # fresh candles on open positions to decide smart exits.
        batch = syms[:]

        scanned = []
        for sym in batch:
            # use cache when fresh — skips the network call → much faster cycles
            klines = e.get_klines_cached(sym, TRADE_TF, 60, ttl=KLINES_TTL)
            if klines is None:
                klines = await ctx.market.fetch_klines(sym, TRADE_TF, 60)
                if len(klines) >= 30:
                    e.klines_cache[(sym, TRADE_TF)] = (time.time(), klines)
            if len(klines) >= 30:
                ctx.candles[sym] = klines
                scanned.append(sym)
                e.scan_count += 1          # 🔢 charts analysed
            await asyncio.sleep(0.02)

        if not scanned:
            self.report("Duke skanuar tregjet… asnjë simbol i disponueshëm këtë cikël")
        else:
            self.report(f"Duke skanuar {', '.join(scanned[:4])}… "
                        f"({len(scanned)} me të dhëna live)")


# ======================================================================
# 2-11 — STRATEGY AGENTS (each votes LONG/SHORT with confidence)
# ======================================================================
class StrategyAgent(Agent):
    kind = "strategy"
    fn = None

    async def execute(self, ctx, idx):
        votes = 0
        for sym, klines in ctx.candles.items():
            try:
                v = self.fn(sym, klines, ctx.tickers.get(sym))
            except Exception:
                continue
            if v:
                ctx.votes.setdefault(sym, []).append(
                    (self.name, v["direction"], v["confidence"]))
                votes += 1
        if not votes:
            self.report(f"{self.name}: pa sinjal këtë cikël")


def _make_strategy(entry):
    return type("Strat_" + entry["name"].replace(" ", "_"),
                (StrategyAgent,),
                {"name": entry["name"], "icon": entry["icon"],
                 "fn": staticmethod(entry["fn"]), "step": 1,
                 "role": "Strategji — voton LONG/SHORT me konfidencë"})


STRATEGY_AGENTS = [_make_strategy(s) for s in STRATEGIES]


# ======================================================================
# 🧩 ENSEMBLE VOTER — runs up to 500 strategy variants on the leading
# candidate, so the final decision reflects the whole ensemble.
# ======================================================================
class EnsembleVoterAgent(Agent):
    step, name, icon = 1, "Ensemble", "🧩"
    role = "1000 variante strategjike votojnë për kandidatin kryesor"

    async def execute(self, ctx, idx):
        e = self.engine
        variants = getattr(e, "variant_strategies", [])
        if not variants or not ctx.votes:
            return
        n = len(variants)
        # 🔁 MOSTËR RROTULLUESE: me 100,000 agjentë nuk i ekzekutojmë të
        # gjithë çdo cikël (do ishte ~2s/3s) — çdo cikël voton një mostër
        # e përzier prej SAMPLE_N agjentësh; me kalimin e kohës TË GJITHË
        # 100,000 marrin pjesë njësoj shpesh (bashkëpunim i plotë).
        SAMPLE_N = 1500
        offset = (getattr(e, "ensemble_round", 0) * SAMPLE_N) % n
        e.ensemble_round = (e.ensemble_round + 1) % max(1, (n + SAMPLE_N - 1) // SAMPLE_N)
        sample = variants[offset:offset + SAMPLE_N]
        if len(sample) < SAMPLE_N:                 # mbështjellje në fund
            sample = sample + variants[:SAMPLE_N - len(sample)]
        self._sample_n = SAMPLE_N
        self._offset = offset
        # pick the symbol with the strongest core consensus
        best_sym = None
        best_score = 0.0
        for sym, votes in ctx.votes.items():
            net = 0.0
            for _, d, conf in votes:
                net += (1.0 if d == "LONG" else -1.0) * (conf / 100.0)
            if abs(net) > best_score:
                best_score = abs(net)
                best_sym = sym
        if not best_sym:
            return
        klines = ctx.candles.get(best_sym)
        if not klines:
            return
        ticker = ctx.tickers.get(best_sym)
        voted = 0
        votes_list = ctx.votes.setdefault(best_sym, [])
        for v in sample:
            try:
                r = v["fn"](best_sym, klines, ticker)
                if r:
                    votes_list.append((v["name"], r["direction"],
                                       r["confidence"]))
                    voted += 1
            except Exception:
                continue
        if voted:
            self.report(f"🧩 {voted}/{len(sample)} agjentë (mostër "
                        f"rrotulluese, nga 100,000) votuan për {best_sym} — "
                        f"konsensus i plotë")
        else:
            self.report(f"🧩 mostër {len(sample)} agjentësh (100,000 gjithsej) "
                        f"— asnjë sinjal i fortë")


# ======================================================================
# 🔀 GRID BALANCER — actively finds the missing side of the grid.
# If longs dominate → it searches for overbought coins (RSI high) and
# queues a SHORT; if shorts dominate → it finds oversold coins (RSI low)
# and queues a LONG. This keeps the portfolio two-sided like a grid.
# ======================================================================
class GridBalancerAgent(Agent):
    step, name, icon = 1, "Grid Balancer", "🔀"
    role = "Balancues — kërkon në mënyrë aktive anën e munguar (SHORT/LONG)"

    async def execute(self, ctx, idx):
        e = self.engine
        if e.mode == "real":
            return                      # spot real = vetëm LONG
        open_pos = e.open_positions()
        n_long = sum(1 for p in open_pos if p["side"] == "LONG")
        n_short = sum(1 for p in open_pos if p["side"] == "SHORT")
        if len(open_pos) >= MAX_OPEN:
            return
        imbalance = n_long - n_short

        # anë që duhet (palca e gridit)
        want = "SHORT" if imbalance >= 2 else ("LONG" if imbalance <= -2 else None)
        if not want:
            return
        best = None
        for sym, klines in ctx.candles.items():
            if sym in {p["symbol"] for p in open_pos}:
                continue
            if sym in e.cooldown and time.time() - e.cooldown[sym] < COOLDOWN_SEC:
                continue
            if len(klines) < 30:
                continue
            closes = [c["c"] for c in klines]
            r = rsi(closes)
            price = (ctx.tickers.get(sym) or {}).get("price") or closes[-1]
            if want == "SHORT" and r > 66:            # i mbingarkuar → SHORT
                conf = 60 + (r - 66) * 1.2
                if best is None or conf > best["confidence"]:
                    best = {"symbol": sym, "direction": "SHORT",
                            "entry": price, "confidence": min(conf, 88),
                            "rsi": r}
            elif want == "LONG" and r < 34:           # i mbishitur → LONG
                conf = 60 + (34 - r) * 1.2
                if best is None or conf > best["confidence"]:
                    best = {"symbol": sym, "direction": "LONG",
                            "entry": price, "confidence": min(conf, 88),
                            "rsi": r}
        if best:
            sym = best["symbol"]
            # vendose DREJTPËRDREJT te picks — Filler-i e hap pavarësisht
            # konsensusit (kjo e mban grid-in të balancuar gjithmonë)
            entry = best["entry"]
            if best["direction"] == "LONG":
                tp = entry * (1 + TAKE_PROFIT)
                sl = entry * (1 - STOP_LOSS)
            else:
                tp = entry * (1 - TAKE_PROFIT)
                sl = entry * (1 + STOP_LOSS)
            pick = {"symbol": sym, "direction": best["direction"],
                    "entry": entry, "tp": tp, "sl": sl,
                    "confidence": best["confidence"],
                    "supporting": ["GridBalancer"]}
            # mos e dyfisho nëse konsensusi e ka tashmë
            if not any(p["symbol"] == sym and p["direction"] == pick["direction"]
                       for p in ctx.picks):
                ctx.picks.append(pick)
            self.report(f"🔀 Grid: kërkoj {want} — {sym} (RSI {best['rsi']:.0f}) "
                        f"për ekuilibër {n_long}L/{n_short}S",
                        sym, best["direction"], best["confidence"])
        else:
            self.report(f"🔀 Grid: {n_long}L/{n_short}S — "
                        f"nuk gjeta sinjal {want} këtë cikël")


# ======================================================================
# 🗳️ CONSENSUS (combines votes with learning weights)
# ======================================================================
class ConsensusAgent(Agent):
    step, name, icon = 1, "Consensus", "🗳️"
    role = "Bashkëpunimi: kombinon votat e 1000 varianteve + strategjive me peshat e mësuara — çdo familje një zë"

    async def execute(self, ctx, idx):
        e = self.engine
        weights = e.strategy_stats
        threshold = e.meta_state.get("threshold", 0.05)   # adaptive (meta-learning)
        rms = self._relative_strength(ctx)                # "arbitrage" across symbols
        open_syms = {p["symbol"] for p in e.open_positions()}
        # 🔀 grid balance: count open LONG vs SHORT — favour the rarer side
        open_pos = e.open_positions()
        n_long = sum(1 for p in open_pos if p["side"] == "LONG")
        n_short = sum(1 for p in open_pos if p["side"] == "SHORT")
        candidates = []

        for sym, votes in ctx.votes.items():
            if sym in open_syms:                # s'hapim pozicion të dytë
                continue
            if sym in e.cooldown and time.time() - e.cooldown[sym] < COOLDOWN_SEC:
                continue                        # cooldown 45s pas mbylljes
            # 🧩 BASHKËPUNIM 1000 AGJENTËSH: votat grupohen në FAMILJE
            # (EMA, RSI, MACD, BOLL, MOM, STOCH, ATR, CCI, MFI, SMA, ...).
            # Çdo familje ka NJË zë të barabartë → asnjë familje me shumë
            # variante (p.sh. 300 EMA) nuk e dominon vendimin; familjet
            # bashkëpunojnë dhe bien dakord bashkë.
            fam = {}
            for sname, d, conf in votes:
                key = sname.split("(")[0] if "(" in sname else sname
                f = fam.setdefault(key, [0.0, 0.0])
                w = weights.get(sname, {}).get("weight", 1.0)
                f[0] += (1.0 if d == "LONG" else -1.0) * w * (conf / 100.0)
                f[1] += w
            net = 0.0
            tw = 0.0
            for key, (fnet, fw) in fam.items():
                if fw <= 0:
                    continue
                fw2 = weights.get(key, {}).get("weight", 1.0)   # pesha e mësuar e familjes
                net += (fnet / fw) * fw2
                tw += fw2
            if tw <= 0:
                continue
            score = net / tw                     # -1 .. 1 (peshuar sipas familjeve)
            if score > threshold:
                direction = "LONG"
            elif score < -threshold:
                direction = "SHORT"
            else:
                continue
            # grid balance boost: if one side dominates, boost the other
            if e.mode != "real":
                if direction == "SHORT" and n_long > n_short:
                    score = min(score * 1.0 + 0.05, 1.0)
                elif direction == "LONG" and n_short > n_long:
                    score = max(score - 0.05, -1.0)
                if direction == "SHORT" and n_long - n_short >= 4:
                    score = min(score + 0.05, 1.0)
                elif direction == "LONG" and n_short - n_long >= 4:
                    score = max(score - 0.05, -1.0)
            # familjet që mbështesin drejtimin e zgjedhur
            fam_sup = {}
            for sname, d, c in votes:
                key = sname.split("(")[0] if "(" in sname else sname
                if d == direction:
                    e2 = fam_sup.setdefault(key, [0, 0.0])
                    e2[0] += 1
                    e2[1] = max(e2[1], c)
            supporting = [k for k in fam_sup]
            # konsensus gride: 1 familje e fortë (≥65%) OSE 2+ familje
            strong = [k for k, (cnt, mx) in fam_sup.items() if mx >= 65]
            if len(supporting) < 2 and len(strong) < 1:
                continue
            confidence = min(94.0, 50.0 + abs(score) * 150.0)
            rms_note = ""
            if REL_STRENGTH_BOOST and rms is not None and sym in rms:
                s, rank = rms[sym]
                # buy relative strength, avoid relative weakness
                if direction == "LONG":
                    if rank >= 0.5:
                        confidence = min(94, confidence + 4)
                        rms_note = f" · RMS {rank:.0%} (i fortë)"
                    elif rank <= 0.2:
                        confidence = max(45, confidence - 6)
                        rms_note = f" · ⚠️ RMS {rank:.0%} (i dobët)"
                else:
                    if rank <= 0.5:
                        confidence = min(94, confidence + 4)
                        rms_note = f" · RMS {rank:.0%} (i dobët)"
                    elif rank >= 0.8:
                        confidence = max(45, confidence - 6)
                        rms_note = f" · ⚠️ RMS {rank:.0%} (i fortë)"
            candidates.append({
                "symbol": sym, "direction": direction,
                "confidence": confidence, "score": score,
                "supporting": supporting,
                "n_votes": len(votes),
                "rms_note": rms_note,
                "entry": (ctx.tickers.get(sym) or {}).get("price") or 0,
            })

        if not candidates:
            # nëse balancuesi i grid-it ka vendosur një pick, vazhdojmë
            # me të (nuk ndalemi) — kështu grid-i mbetet i balancuar
            if getattr(ctx, "picks", []):
                ctx.chosen = ctx.picks[0]
                self.report(f"🔀 Pa konsensus — vazhdoj me pick-un e "
                            f"balancuesit ({ctx.picks[0]['symbol']} "
                            f"{ctx.picks[0]['direction']})",
                            ctx.picks[0]["symbol"],
                            ctx.picks[0]["direction"],
                            ctx.picks[0]["confidence"])
                return
            self.report(f"Pa konsensus (pragu adaptiv {threshold:.2f}) — "
                        f"boti pret sinjale më të forta")
            ctx.stop = True
            return

        candidates.sort(key=lambda c: c["confidence"], reverse=True)
        best = candidates[0]
        # 🔀 GRID: pick the best LONG and the best SHORT together, so both
        # directions can open in the same cycle (grid-style trading).
        best_long = max((c for c in candidates if c["direction"] == "LONG"),
                        key=lambda c: c["confidence"], default=None)
        best_short = max((c for c in candidates if c["direction"] == "SHORT"),
                         key=lambda c: c["confidence"], default=None)
        picks = [c for c in (best_long, best_short) if c]
        picks.sort(key=lambda c: c["confidence"], reverse=True)
        ctx.chosen = picks[0] if picks else None
        # ruaj picks ekzistuese të balancuesit + shto ato të konsensusit
        existing = list(getattr(ctx, "picks", []))
        seen = {(p["symbol"], p["direction"]) for p in existing}
        for p in picks:
            if (p["symbol"], p["direction"]) not in seen:
                existing.append(p)
                seen.add((p["symbol"], p["direction"]))
        ctx.picks = existing
        ctx.votes_for_trade = (picks[0]["supporting"] if picks
                               else (existing[0]["supporting"]
                                     if existing else []))
        self.report(
            f"{best['symbol']} {best['direction']} — konsensus "
            f"{best['confidence']:.0f}% · {best['n_votes']} strategji "
            f"(net {best['score']:+.2f}, prag {threshold:.2f})"
            f"{best.get('rms_note', '')} · mbështesin: "
            f"{', '.join(best['supporting'][:4])}",
            best["symbol"], best["direction"], best["confidence"])

    @staticmethod
    def _relative_strength(ctx):
        """Cross-symbol ranking (mini 'arbitrage'): long the strong, short
        the weak. Returns {symbol: (score, percentile_rank)}."""
        if not REL_STRENGTH_BOOST:
            return None
        scores = {}
        for sym, klines in ctx.candles.items():
            try:
                closes = [c["c"] for c in klines]
                if len(closes) < 12:
                    continue
                roc10 = (closes[-1] - closes[-11]) / closes[-11] * 100 if closes[-11] else 0
                chg24 = (ctx.tickers.get(sym) or {}).get("chg24") or 0.0
                e9 = ema(closes, 9)[-1]
                e21 = ema(closes, 21)[-1]
                trend = 1.0 if e9 > e21 else -1.0
                scores[sym] = roc10 * 0.5 + chg24 * 0.3 + trend * 0.2
            except Exception:
                continue
        if not scores:
            return None
        ordered = sorted(scores.items(), key=lambda kv: kv[1])
        n = len(ordered)
        return {sym: (sc, (i + 1) / n)
                for i, (sym, sc) in enumerate(ordered)}


# ======================================================================
# 🧠 13 — AI PREDICTOR (LLM reasoning layer)
# ======================================================================
class AIPredictorAgent(Agent):
    step, name, icon = 1, "AI Predictor", "🧠"
    role = "AI-ja analizon dhe përforcon/ul konfidencën"

    async def execute(self, ctx, idx):
        e = self.engine
        if not ctx.chosen:
            return
        best = ctx.chosen
        ai = e.brain
        ticker = ctx.tickers.get(best["symbol"])
        snap = ai.snapshot_for(best, ctx.candles.get(best["symbol"]), ticker)
        ai.enqueue(snap)
        verdict = ai.get_verdict(best["symbol"])

        extra = ""
        if verdict:
            v, c = verdict["verdict"], verdict["confidence"]
            if v in ("LONG", "SHORT"):
                if v == best["direction"]:
                    best["confidence"] = min(94, best["confidence"] + 3)
                    extra = f" · AI konfirmon {v} {c}%"
                elif c >= 65:
                    best["confidence"] = max(50, best["confidence"] - 10)
                    extra = f" · ⚠️ AI kundërshton ({v} {c}%)"
            elif c >= 60:
                best["confidence"] = max(50, best["confidence"] - 5)
                extra = f" · AI: HOLD ({c}%)"
        elif ai.cfg.get("enabled"):
            extra = " · 🧠 AI po analizon…"

        self.report(f"AI: {best['symbol']} {best['direction']} — "
                    f"konfidencë {best['confidence']:.0f}%{extra}",
                    best["symbol"], best["direction"], best["confidence"])


# ======================================================================
# 🌦️ 14 — REGIME FILTER (volatility regime)
# ======================================================================
class RegimeFilterAgent(Agent):
    step, name, icon = 2, "Regime", "🌦️"
    role = "Filtron tregjet shumë të paqëndrueshme"

    async def execute(self, ctx, idx):
        if not ctx.chosen:
            return
        # average |move| of last candle across scanned symbols
        moves = []
        for sym, klines in ctx.candles.items():
            if len(klines) >= 2:
                c0, c1 = klines[-2]["c"], klines[-1]["c"]
                if c0:
                    moves.append(abs(c1 - c0) / c0 * 100)
        if not moves:
            return
        avg_move = sum(moves) / len(moves)
        if avg_move > 0.45:          # too wild on 1m
            ctx.chosen["confidence"] = max(40, ctx.chosen["confidence"] - 12)
            self.report(f"Treg i paqëndrueshëm ({avg_move:.2f}%/min) — "
                        f"konfidenca u ul me 12%",
                        ctx.chosen["symbol"], ctx.chosen["direction"],
                        ctx.chosen["confidence"])
        elif avg_move < 0.05:
            self.report(f"Treg i qetë ({avg_move:.2f}%/min) — spread i ngushtë",
                        ctx.chosen["symbol"], ctx.chosen["direction"],
                        ctx.chosen["confidence"])
        else:
            self.report(f"Regjim normal ({avg_move:.2f}%/min) — gati për veprim",
                        ctx.chosen["symbol"], ctx.chosen["direction"],
                        ctx.chosen["confidence"])


# ======================================================================
# ✅ 15 — VALIDATOR
# ======================================================================
class ValidatorAgent(Agent):
    step, name, icon = 2, "Validator", "✅"
    role = "Hedh setup-et me rrezik të lartë sipas rregullave"

    async def execute(self, ctx, idx):
        e = self.engine
        if not ctx.chosen:
            return
        best = ctx.chosen

        if not e.auto_trade:
            self.report("Auto-trading OFF — kërkohet miratim manual",
                        best["symbol"], best["direction"], best["confidence"])
            ctx.stop = True
            return

        if e.is_locked():
            mins = int((e.lock_until - time.time()) // 60) + 1
            self.report(f"🔒 Profit-lock: push {mins} min — fitimet e mbrojtura",
                        best["symbol"], best["direction"], best["confidence"])
            ctx.stop = True
            return

        if e.is_risk_paused():
            mins = int((e.risk_pause_until - time.time()) // 60) + 1
            self.report(f"🛡️ Risk Manager: push {mins} min — "
                        f"ndalim nga humbjet (WR {e.risk_state.get('wr')}%)",
                        best["symbol"], best["direction"], best["confidence"])
            ctx.stop = True
            return

        if e.mode == "real":
            if not e.exchange.configured:
                self.report("💰 REAL: çelësat s'janë konfiguruar "
                            "(BINANCE_API_KEY/SECRET te Render → Environment)",
                            best["symbol"], best["direction"], best["confidence"])
                ctx.stop = True
                return
            if best["direction"] != "LONG":
                self.report("💰 REAL: spot = vetëm LONG — SHORT anashkalohet",
                            best["symbol"], best["direction"], best["confidence"])
                ctx.stop = True
                return
            if len(e.open_positions()) >= REAL_MAX_POSITIONS:
                self.report(f"💰 REAL: portofoli i plotë ({REAL_MAX_POSITIONS})",
                            best["symbol"], best["direction"], best["confidence"])
                ctx.stop = True
                return
        else:
            if len(e.open_positions()) >= MAX_OPEN:
                self.report(f"Portofoli i plotë ({MAX_OPEN}/{MAX_OPEN})",
                            best["symbol"], best["direction"], best["confidence"])
                ctx.stop = True
                return

        # per-symbol sanity checks (volume is handled by the strategies'
        # own filters; consensus ≥2 strategies is the main quality gate)
        klines = ctx.candles.get(best["symbol"])
        if klines and len(klines) >= 2:
            closes = [c["c"] for c in klines]
            r = rsi(closes)
            # RSI ekstrem bllokon vetëm në drejtimin e rrezikshëm:
            # LONG me RSI shumë të lartë (po përfundon rritja)
            # SHORT me RSI shumë të ulët (po përfundon rënia)
            if best["direction"] == "LONG" and r > 88:
                self.report(f"{best['symbol']}: RSI {r:.0f} — LONG i rrezikshëm",
                            best["symbol"], best["direction"], best["confidence"])
                ctx.stop = True
                return
            if best["direction"] == "SHORT" and r < 12:
                self.report(f"{best['symbol']}: RSI {r:.0f} — SHORT i rrezikshëm",
                            best["symbol"], best["direction"], best["confidence"])
                ctx.stop = True
                return
            mom = (closes[-1] - closes[-2]) / closes[-2] if closes[-2] else 0
            if abs(mom) > 0.008:
                self.report(f"{best['symbol']}: lëvizje shumë e shpejtë — anashkalohet",
                            best["symbol"], best["direction"], best["confidence"])
                ctx.stop = True
                return

        # AI veto
        verdict = e.brain.get_verdict(best["symbol"])
        if verdict and verdict["confidence"] >= 70 and \
                verdict["verdict"] != best["direction"]:
            e.last_ai_refused = {"symbol": best["symbol"],
                                 "reason": verdict["reason"],
                                 "model": verdict["model"]}
            self.report(f"{best['symbol']}: VETO nga AI — AI sheh "
                        f"{verdict['verdict']} {verdict['confidence']}%",
                        best["symbol"], best["direction"], best["confidence"])
            ctx.stop = True
            return

        # 🎯 multi-timeframe confirmation (15m trend must agree)
        # — but in paper mode, SHORT against an up-trend is allowed (grid
        #   style) when the balance favours it; it just gets lower conf.
        if MTF_ENABLED:
            ok, m = await self._mtf(e, best["symbol"], best["direction"])
            if not ok:
                if e.mode == "paper" and best["direction"] == "SHORT":
                    # grid SHORT: allowed, but reduce confidence
                    best["confidence"] = max(50, best["confidence"] - 15)
                    self.report(
                        f"{best['symbol']}: SHORT kundër trendit (grid) "
                        f"— konfidenca u ul në {best['confidence']:.0f}%",
                        best["symbol"], best["direction"], best["confidence"])
                    return
                self.report(f"{best['symbol']}: MTF {m}",
                            best["symbol"], best["direction"], best["confidence"])
                ctx.stop = True
                return
            self.report(f"{best['symbol']}: validuar ✓ {m}",
                        best["symbol"], best["direction"], best["confidence"])
            return

        self.report(f"{best['symbol']}: validuar ✓ — volumi dhe RSI në rregull",
                    best["symbol"], best["direction"], best["confidence"])

    async def _mtf(self, e, symbol, direction):
        """Confirm the 1m signal with the 15m trend (EMA fast vs slow)."""
        cache = e.mtf_cache.get(symbol)
        now = time.time()
        if cache and now - cache[0] < MTF_CACHE_TTL:
            closes = cache[1]
        else:
            klines = await e.market.fetch_klines(symbol, MTF_BAR, 60)
            closes = [k["c"] for k in klines]
            e.mtf_cache[symbol] = (now, closes)
        if len(closes) < MTF_SLOW + 2:
            return True, "MTF nuk disponohet — kalon"
        fast = ema(closes, MTF_FAST)[-1]
        slow = ema(closes, MTF_SLOW)[-1]
        if direction == "LONG" and fast > slow:
            return True, f"trendi {MTF_BAR} konfirmon (EMA{MTF_FAST}>{MTF_SLOW})"
        if direction == "SHORT" and fast < slow:
            return True, f"trendi {MTF_BAR} konfirmon (EMA{MTF_FAST}<{MTF_SLOW})"
        return False, f"trendi {MTF_BAR} kundërshton drejtimin — hedhet"


# ======================================================================
# 🛡️ 16 — RISK MANAGER
# ======================================================================
class RiskManagerAgent(Agent):
    step, name, icon = 2, "Risk", "🛡️"
    role = "Mbron nga rënie e madhe (drawdown) dhe ekspozim i tepërt"

    async def execute(self, ctx, idx):
        e = self.engine
        if not ctx.chosen:
            return
        acc = e.account()
        peak = acc.get("peak") or acc["equity"]
        if peak > 0 and acc["equity"] < peak * 0.90:
            self.report(f"⚠️ Drawdown >10% (equity {acc['equity']:.0f} vs kulmi "
                        f"{peak:.0f}) — tregtia ndalohet deri në rivendosje",
                        ctx.chosen["symbol"], ctx.chosen["direction"],
                        ctx.chosen["confidence"])
            ctx.stop = True
            return
        # adaptive risk status (protects ×2 against losses)
        ri = e.risk_info()
        risk_note = ""
        if ri.get("paused"):
            mins = int((e.risk_pause_until - time.time()) // 60) + 1
            risk_note = f" 🛡️ push {mins} min (WR {ri.get('wr')}%)"
        elif ri.get("effective_mult", 1.0) < ri.get("user_mult", 1.0):
            risk_note = (f" 🛡️ mbrojtje: ×{ri.get('user_mult')} → "
                         f"×{ri.get('effective_mult')} (WR {ri.get('wr')}%)")
        elif ri.get("effective_mult", 1.0) >= 2:
            risk_note = " 🛡️ ×2 aktiv — Risk Manager në vëzhgim"

        if e.mode == "real":
            bal = e.real_balance()
            notional = ctx.qty * ctx.chosen.get("entry", 0)
            if notional > bal * REAL_MAX_NOTIONAL_PCT:
                ctx.qty = bal * REAL_MAX_NOTIONAL_PCT / ctx.chosen.get("entry", 1)
            self.report(f"💰 Risk: balanca ${bal:.2f}, ekspozim ≤ "
                        f"{REAL_MAX_NOTIONAL_PCT*100:.0f}%{risk_note}",
                        ctx.chosen["symbol"], ctx.chosen["direction"],
                        ctx.chosen["confidence"])
        else:
            self.report(f"Risk: ≤{MAX_OPEN} pozicione, drawdown ≤10%, "
                        f"ekspozim ≤35%{risk_note}",
                        ctx.chosen["symbol"], ctx.chosen["direction"],
                        ctx.chosen["confidence"])


# ======================================================================
# ⚖️ 17 — SIZER
# ======================================================================
class SizerAgent(Agent):
    step, name, icon = 3, "Sizer", "⚖️"
    role = "Llogarit madhësinë e pozicionit — fiks ose komponim"

    async def execute(self, ctx, idx):
        e = self.engine
        sig = ctx.chosen
        entry = sig.get("entry")
        if not entry:
            entry = ctx.tickers.get(sig["symbol"], {}).get("price") or 0
            sig["entry"] = entry

        # stop distance depends on direction (SHORT SL is ABOVE entry)
        sl = sig.get("sl")
        if sl is None:
            sl = entry * (1 - STOP_LOSS) if sig["direction"] == "LONG" \
                else entry * (1 + STOP_LOSS)
        stop_dist = abs(entry - sl)
        sl_pct = stop_dist / entry if entry else STOP_LOSS

        mult = e.effective_mult()                  # ×N normal, ×1 kur risk aktiv

        # 💵 FIXED DOLLAR RISK — entry fixed (e.g. $3), loss never above max
        # (e.g. $1), regardless of ×1..×5.
        if e.fixed_risk_enabled:
            notional = e.fixed_entry_usd
            if e.mode == "real" and notional < REAL_MIN_NOTIONAL:
                notional = REAL_MIN_NOTIONAL      # Binance min ~$5
            qty_entry = notional / entry if entry else 0
            # safety: qty limited so SL loss never exceeds the cap
            qty_cap = (e.fixed_max_loss_usd / (entry * sl_pct)) \
                if (entry and sl_pct > 0) else 0
            qty = min(qty_entry, qty_cap) if qty_cap > 0 else qty_entry
            loss_if_sl = qty * entry * sl_pct if entry else 0
            ctx.qty = qty
            self.report(
                f"💵 Fikse: ${notional:.2f} hyrje (pavarësisht ×{mult}) · "
                f"SL {sl_pct*100:.2f}% → humbje max ${loss_if_sl:.2f} "
                f"(kufiri ${e.fixed_max_loss_usd:.2f})",
                sig["symbol"], sig["direction"], sig["confidence"])
            return

        if e.mode == "real":
            bal = e.real_balance()
            notional = bal * min(REAL_MAX_NOTIONAL_PCT * mult, 0.40)
            ctx.qty = notional / entry if entry else 0
            self.report(f"💰 REAL {ctx.qty:.6f} @ {entry:.6g} (~${notional:.2f}, "
                        f"maks {min(REAL_MAX_NOTIONAL_PCT*100*mult,40):.0f}% e balancës, ×{mult:g})",
                        sig["symbol"], sig["direction"], sig["confidence"])
            return

        equity = e.account()["equity"]
        base = equity if e.compound else STARTING_BALANCE
        mode = "KOMPONIM" if e.compound else "FIKS"
        risk_amount = base * TRADE_RISK * mult
        qty = risk_amount / stop_dist if stop_dist > 0 else 0.0
        # clear progression: ×1=35% ×2=50% ×3=60% ×4=70% ×5=80%
        # (SL 0.35% mban rrezikun e llogarisë ~0.28% edhe në ×5)
        pct_map = {1: 0.35, 2: 0.50, 3: 0.60, 4: 0.70, 5: 0.80}
        max_pct = pct_map.get(int(mult), 0.80)
        if qty * entry > equity * max_pct:
            qty = equity * max_pct / entry
        ctx.qty = qty
        self.report(f"{qty:.4f} @ {entry:.6g} — risk ${risk_amount:.2f} "
                    f"({mode}, ×{mult:g}, deri {max_pct*100:.0f}%)",
                    sig["symbol"], sig["direction"], sig["confidence"])


# ======================================================================
# 🚦 18 — FILLER
# ======================================================================
# ======================================================================
# 🪜 PYRAMID AGENT — shton pozicion në fitim (si spot pyramiding, por me
# madhësinë normale të botit: $15 hyrje ose ×komponim). KURRË averaging-down.
# ======================================================================
class PyramidAgent(Agent):
    step, name, icon = 4, "Pyramid", "🪜"
    role = "Shton pozicion në fitim: higher-high/lower-low, max 3 për simbol, kurrë averaging-down"

    async def execute(self, ctx, idx):
        e = self.engine
        if e.mode != "paper":
            return
        open_pos = e.open_positions()
        if len(open_pos) >= MAX_OPEN:
            return
        # grupoj pozicionet e hapura sipas simbolit + drejtimit
        groups = {}
        for p in open_pos:
            key = (p["symbol"], p["side"])
            g = groups.setdefault(key, {
                "symbol": p["symbol"], "side": p["side"],
                "entries": 0, "cost": 0.0, "qty": 0.0,
                "hi": 0.0, "lo": 1e18})
            g["entries"] += 1
            g["cost"] += p["entry"] * p["qty"]
            g["qty"] += p["qty"]
            g["hi"] = max(g["hi"], p["entry"])
            g["lo"] = min(g["lo"], p["entry"])

        for key, g in groups.items():
            if g["entries"] >= MAX_PYRAMID:
                continue
            if len(e.open_positions()) >= MAX_OPEN:
                break
            sym, side = key
            t = ctx.tickers.get(sym)
            price = t["price"] if t and t.get("price", 0) > 0 else 0.0
            if not price:
                continue
            avg = g["cost"] / g["qty"] if g["qty"] else 0.0
            unreal = (price - avg) * g["qty"] if side == "LONG" \
                else (avg - price) * g["qty"]
            # 🔒 KURRË averaging-down: shtohet VETËM në fitim
            if unreal < PYRAMID_MIN_PROFIT_USD:
                continue
            # higher-high (LONG) / lower-low (SHORT) për konfirmim
            if side == "LONG":
                if price <= g["hi"] * (1 + PYRAMID_CONFIRM_PCT):
                    continue
            else:
                if price >= g["lo"] * (1 - PYRAMID_CONFIRM_PCT):
                    continue
            # RSI jo ekstrem
            kl = ctx.candles.get(sym)
            if kl and len(kl) > 20:
                r = rsi([c["c"] for c in kl])
                if side == "LONG" and r > PYRAMID_RSI_MAX:
                    continue
                if side == "SHORT" and r < 100 - PYRAMID_RSI_MAX:
                    continue
            # madhësia si boti normal (fixed $15 ose komponim)
            ntl = e.fixed_entry_usd
            pstop = STOP_LOSS
            pqty = min(ntl / price,
                       e.fixed_max_loss_usd / (price * pstop)) if pstop > 0 else 0
            if pqty <= 0:
                continue
            ptp = price * (1 + TAKE_PROFIT) if side == "LONG" \
                else price * (1 - TAKE_PROFIT)
            psl = price * (1 - STOP_LOSS) if side == "LONG" \
                else price * (1 + STOP_LOSS)
            sig = {"symbol": sym, "direction": side, "entry": price,
                   "tp": ptp, "sl": psl, "confidence": 70}
            tid = e._open_trade(sig, pqty, votes=None)
            if tid:
                e._event("fill",
                         f"🪜 {side} {sym} SHTESË {g['entries'] + 1}/{MAX_PYRAMID} "
                         f"@ {price:.6g} (higher-{'high' if side == 'LONG' else 'low'}, "
                         f"fitim {unreal:+.2f})",
                         sym)
                self.report(
                    f"🪜 Pyramiding: shtesë {g['entries'] + 1} në {sym} ({side}) "
                    f"— fitim {unreal:+.2f} USDT",
                    sym, side, 70)


class FillerAgent(Agent):
    step, name, icon = 4, "Filler", "🚦"
    role = "Ekzekuton urdhrin (paper ose real)"

    async def execute(self, ctx, idx):
        e = self.engine
        sig = ctx.chosen
        if not sig:
            return

        entry = sig.get("entry", 0)

        # 🔀 GRID: open both directions (LONG + SHORT) if slots allow
        opened = 0
        for pick in getattr(ctx, "picks", [sig]):
            # ⚠️ E RËNDËSISHME: çmimi VETËM i simbolit të vet — kurrë
            # fallback nga pick-i tjetër (kjo shkaktoi çmime të përziera!)
            pp = pick.get("entry") or \
                (ctx.tickers.get(pick["symbol"]) or {}).get("price") or 0
            if not pp or pp <= 0:
                continue
            psl = pick.get("sl")
            if psl is None:
                psl = pp * (1 - STOP_LOSS) if pick["direction"] == "LONG" \
                    else pp * (1 + STOP_LOSS)
            pstop = abs(pp - psl) / pp
            pqty = 0.0
            if e.fixed_risk_enabled:
                ntl = e.fixed_entry_usd
                pqty = min(ntl / pp,
                           e.fixed_max_loss_usd / (pp * pstop)) if pstop > 0 else 0
            else:
                pqty = (e.account()["equity"] * 0.35 * e.effective_mult()) / pp
            if pqty <= 0:
                continue
            if len(e.open_positions()) >= MAX_OPEN:
                break
            ptp = pp * (1 + TAKE_PROFIT) if pick["direction"] == "LONG" \
                else pp * (1 - TAKE_PROFIT)
            psl2 = pp * (1 - STOP_LOSS) if pick["direction"] == "LONG" \
                else pp * (1 + STOP_LOSS)
            sig2 = dict(pick, entry=pp, tp=ptp, sl=psl2)
            tid = e._open_trade(sig2, pqty, votes=ctx.votes_for_trade)
            if tid:
                opened += 1
                e._event("fill",
                         f"{pick['direction']} {pick['symbol']} {pqty:.4f} @ "
                         f"{pp:.6g} · konsensus {pick['confidence']:.0f}%",
                         pick["symbol"])
        if opened:
            ctx.trade_id = True
            d = "+".join(f"{p['direction']} {p['symbol'].split('-')[0]}"
                         for p in ctx.picks[:2])
            self.report(f"🔀 Grid: hapi {opened} pozicione — {d}",
                        sig["symbol"], sig["direction"], sig["confidence"])
        else:
            self.report("Asnjë pozicion i hapur — pa hapësirë ose madhësi zero",
                        sig["symbol"], sig["direction"], sig["confidence"])
        await asyncio.sleep(0.6)


# ======================================================================
# 📊 19 — TRACKER
# ======================================================================
class TrackerAgent(Agent):
    step, name, icon = 5, "Tracker", "📊"
    role = "Monitoron pozicionet: TP, SL, trailing breakeven, PnL live"

    async def execute(self, ctx, idx):
        e = self.engine
        positions = e.open_positions()
        for pos in positions:
            t = ctx.tickers.get(pos["symbol"])
            price = t["price"] if t and t.get("price", 0) > 0 else pos["entry"]
            side = pos["side"]

            # 🧠 SMART EXIT — mbyll me fitim kur agjentët e shohin të
            # arsyeshme (trend i mbaruar, RSI ekstrem, momentum i dobësuar).
            # Nuk ka afat kohor — vendimi bazohet në tregun real.
            # Fitimi kapet GJITHMONË në dollarë të plotë ($1, $2, $3...),
            # kurrë me centa (p.sh. JO $1.04).
            exit_reason = self._smart_exit(e, pos, price, ctx)
            if exit_reason:
                if isinstance(exit_reason, tuple):
                    reason, banked = exit_reason
                else:
                    reason, banked = exit_reason, None
                await e._close_trade(pos, price, reason, banked=banked)
                continue

            # 📈 trailing — kyç fitimin e arsyeshëm (SL lëviz me çmimin)
            if e.mode == "paper":
                self._trail_profit(e, pos, price)
                # ⏱️ TIME-STOP: pas MAX_HOLD_MIN minutash liro vendin —
                # me fitim ≥$1 e mbyll me dollarin e plotë të kyçur,
                # pa fitim e mbyll me humbje të vogël (qarkullim më i shpejtë)
                await self._time_stop(e, pos, price)

            if e.mode == "real":
                await self._track_real(e, pos, price)
                continue

            if side != "LONG" or not ENABLE_PARTIAL_TP or not pos.get("tp1"):
                # classic symmetric handling (SHORT or partial off)
                await self._track_classic(e, pos, price)
                continue

            # ---------- ASYMMETRIC LONG: partial TP + trailing runner ----------
            hit_sl = price <= pos["sl"]
            if hit_sl:
                await e._close_trade(pos, price, "sl")
                await e._close_siblings(pos, price, "sl")
                continue

            if not pos["tp1_hit"]:
                if price >= pos["tp1"]:
                    e._sell_partial(pos, price)           # bank half the profit
                elif price >= pos["entry"] * (1 + BREAKEVEN_AT):
                    new_sl = pos["entry"] * 1.0005        # early breakeven guard
                    if new_sl > pos["sl"]:
                        e._update_sl(pos["id"], new_sl)
            else:
                # runner: trail the stop below the highest price reached
                peak = max(pos.get("trail_high") or price, price)
                new_sl = peak * (1 - TRAIL_PCT)
                if new_sl > pos["sl"]:
                    e._update_sl(pos["id"], new_sl)
                    e._set_trail_high(pos["id"], peak)
                if price <= pos["sl"]:
                    await e._close_trade(pos, price, "trail")

        if positions:
            p = positions[0]
            tag = " (asimetrik)" if (ENABLE_PARTIAL_TP and p["side"] == "LONG") else ""
            self.report(f"{len(positions)} pozicion(e) aktive{tag} — TP1 + trailing",
                        p["symbol"], p["side"])
        else:
            self.report("Asnjë pozicion aktiv — cikli u përfundua")

    def _smart_exit(self, e, pos, price, ctx):
        """Agjentët e ndalin tregtinë kur fitimi është i ARSYESHËM:
        • Shkalla në $ TË PLOTË: +$1, +$2, +$3, +$4, +$5 → kapet sa t'ia arrijë
        • Fitimi matet NETO (pas tarifave) kundrejt shkallës — kurrë centa
        • RSI ekstrem / trend i kthyer / momentum i mbaruar → kapet (dollar i plotë)
        Kështu fitimi i arsyeshëm ruhet, jo i lihet rastit.
        Kthen (arsye, dollar_i_plote) ose None."""
        side = pos["side"]
        qty = pos["qty"] or 1
        pnl_pct = (price - pos["entry"]) / pos["entry"] * 100 \
            if side == "LONG" else (pos["entry"] - price) / pos["entry"] * 100
        if pnl_pct < 0.05:
            return None
        # 💵 dollar ladder — MINIMUM $1 neto (asnjëherë nën $1!)
        # Agjenti mban pozicionin derisa fitimi NETO të arrijë $1, $2, $3+,
        # pastaj e kap si dollar të plotë — kurrë me centa (p.sh. JO $1.04).
        pnl_usd = pos["entry"] * qty * pnl_pct / 100
        fees_est = (pos["entry"] * qty + price * qty) * FEE_RATE   # tarifat hyrje+dalje
        net_usd = pnl_usd - fees_est
        if net_usd < 1.0:
            return None            # mban — fitimi nën $1 nuk kapet kurrë
        # 💰 $1 NUK kapet menjëherë: trailing e kyç $1 (SL lëviz lart) dhe
        # pozicioni vazhdon drejt $2/$3/$4/$5 — fitimi mesatar rritet,
        # pa rrezikuar nën $1 (SL i kyçur nuk bie kurrë poshtë shkallës).
        for rung in (5.0, 4.0, 3.0, 2.0):
            if net_usd >= rung:
                return (f"smart: kapur shkalla ${rung:g} — fitim i arsyeshëm", rung)
        klines = ctx.candles.get(pos["symbol"])
        if not klines or len(klines) < 30:
            return None
        closes = [c["c"] for c in klines]
        r = rsi(closes)
        e9 = ema(closes, 9)[-1]
        e21 = ema(closes, 21)[-1]
        mom = (closes[-1] - closes[-2]) / closes[-2] * 100 if closes[-2] else 0
        last2 = (closes[-1] - closes[-2]) + (closes[-2] - closes[-3]) \
            if len(closes) >= 3 else 0

        # treguesit kapin VETËM me fitim neto >= $1 — gjithmonë dollar i plotë
        bank = float(int(net_usd))          # p.sh. $1.37 → kapet si $1 (pa centa)
        if side == "LONG":
            if r > 68:
                return ("smart: RSI i mbingarkuar — fitim i arsyeshëm", bank)
            if e9 < e21:
                return ("smart: trendi u kthye poshtë — fitim i arsyeshëm", bank)
            if last2 < 0 and mom < 0:
                return ("smart: momentum i dobësuar — fitim i arsyeshëm", bank)
        else:
            if r < 32:
                return ("smart: RSI i mbishitur — fitim i arsyeshëm", bank)
            if e9 > e21:
                return ("smart: trendi u kthye lart — fitim i arsyeshëm", bank)
            if last2 > 0 and mom > 0:
                return ("smart: momentum i dobësuar — fitim i arsyeshëm", bank)
        return None

    def _trail_profit(self, e, pos, price):
        """Trailing + shkalla në $: SL lëviz për të kyçur $1/$2/$3/$4/$5
        sapo arrihen NETO (pas tarifave) — fitimi i arsyeshëm mbrohet gjithmonë,
        gjithmonë në dollarë të plotë (kurrë centa)."""
        side = pos["side"]
        qty = pos["qty"] or 1
        pnl_pct = (price - pos["entry"]) / pos["entry"] * 100 \
            if side == "LONG" else (pos["entry"] - price) / pos["entry"] * 100
        pnl_usd = pos["entry"] * qty * pnl_pct / 100
        fees_est = (pos["entry"] * qty + price * qty) * FEE_RATE
        net_usd = pnl_usd - fees_est
        if net_usd < 1.0:
            return
        # SL që kyç shkallën më të lartë të arritur (min $1, dollar i plotë)
        locked = 0.0
        for rung in (5.0, 4.0, 3.0, 2.0, 1.0):
            if net_usd >= rung:
                locked = rung
                break
        # SL që kyç shkallën më të lartë të arritur (min $1, dollar i plotë).
        # Çmimi i SL llogaritet që fitimi NETO (pas tarifave) = saktësisht
        # shkalla — kështu edhe kur SL e prek, kapet $1.00 / $2.00, kurrë centa.
        if side == "LONG":
            new_sl = (locked + pos["entry"] * qty * (1 + FEE_RATE)) \
                / (qty * (1 - FEE_RATE))
            if new_sl > pos["sl"]:
                e._update_sl(pos["id"], new_sl)
        else:
            new_sl = (pos["entry"] * qty * (1 - FEE_RATE) - locked) \
                / (qty * (1 + FEE_RATE))
            if new_sl < pos["sl"]:
                e._update_sl(pos["id"], new_sl)

    async def _time_stop(self, e, pos, price):
        """⏱️ Liron vendin pas MAX_HOLD_MIN minutash:
        • nëse ka fitim ≥$1 → mbyll me dollarin e plotë të kyçur (jo centa)
        • nëse s'ka fitim → mbyll me humbje të vogël TIME_STOP_SL
        Kjo rrit qarkullimin → më shumë tregti në ditë → më shumë $/ditë."""
        try:
            opened = datetime.datetime.fromisoformat(pos["opened_at"]).timestamp()
        except Exception:
            return
        if time.time() - opened < MAX_HOLD_MIN * 60:
            return
        side = pos["side"]
        qty = pos["qty"] or 1
        pnl_usd = (price - pos["entry"]) * qty if side == "LONG" \
            else (pos["entry"] - price) * qty
        fees = (pos["entry"] * qty + price * qty) * FEE_RATE
        net = pnl_usd - fees
        if net >= 1.0:
            # kap dollarin e plotë më të lartë të kyçur (kurrë centa)
            banked = float(int(net))
            await e._close_trade(pos, price, "time", banked=banked)
        else:
            # pa fitim → mbyll me humbje të vogël, liron vendin
            stop_px = pos["entry"] * (1 - TIME_STOP_SL) if side == "LONG" \
                else pos["entry"] * (1 + TIME_STOP_SL)
            await e._close_trade(pos, stop_px, "time")

    async def _track_classic(self, e, pos, price):
        side = pos["side"]
        hit_tp = (price >= pos["tp"]) if side == "LONG" else (price <= pos["tp"])
        hit_sl = (price <= pos["sl"]) if side == "LONG" else (price >= pos["sl"])
        if not hit_tp and not hit_sl:
            if side == "LONG" and price >= pos["entry"] * (1 + BREAKEVEN_AT):
                new_sl = pos["entry"] * 1.0005
                if new_sl > pos["sl"]:
                    e._update_sl(pos["id"], new_sl)
            elif side == "SHORT" and price <= pos["entry"] * (1 - BREAKEVEN_AT):
                new_sl = pos["entry"] * 0.9995
                if new_sl < pos["sl"]:
                    e._update_sl(pos["id"], new_sl)
        if hit_tp:
            # 💵 edhe TP (rrjet sigurie) kapet si dollar i plotë — kurrë centa
            pnl_usd = (price - pos["entry"]) * pos["qty"] if side == "LONG" \
                else (pos["entry"] - price) * pos["qty"]
            fees = (pos["entry"] + price) * pos["qty"] * FEE_RATE
            net = pnl_usd - fees
            banked = float(max(1, int(net))) if net > 0 else None
            await e._close_trade(pos, price, "tp", banked=banked)
        elif hit_sl:
            # 🪜 SL preket → mbyllet E GJITHË grupi i atij simboli (si në
            # spot pyramiding): shtesat nuk lihen të humbasin më tej
            await e._close_trade(pos, price, "sl")
            await e._close_siblings(pos, price, "sl")

    async def _track_real(self, e, pos, price):
        side = pos["side"]
        hit_tp = (price >= pos["tp"]) if side == "LONG" else (price <= pos["tp"])
        hit_sl = (price <= pos["sl"]) if side == "LONG" else (price >= pos["sl"])
        if hit_tp or hit_sl:
            await e.real_close(pos, price, "tp" if hit_tp else "sl")


# ======================================================================
# 🎓 20 — LEARNING AGENT (meta-learning: weights + adaptive threshold)
# ======================================================================
class LearningAgent(Agent):
    step, name, icon = 5, "Learning", "🎓"
    role = "Mëson: peshat e strategjive + pragu adaptiv i konsensusit"

    async def execute(self, ctx, idx):
        e = self.engine
        try:
            with e._conn() as c:
                explore_min = max(1, int(round(5 / getattr(e, "learn_speed", 1.0))))
                fresh, max_id = aggregate_from_trades(
                    c, e.learning_last_id, explore_min=explore_min)
            if max_id > e.learning_last_id:
                e.learning_last_id = max_id
                for name, st in fresh.items():
                    cur = e.strategy_stats.setdefault(name, dict(DEFAULT_STATS))
                    cur.update(st)
                e.persist_learning()
        except Exception:
            pass

        # meta: rolling system results for adaptive threshold
        meta = e.meta_state
        try:
            with e._conn() as c:
                rows = c.execute(
                    "SELECT pnl FROM trades WHERE status!='open' "
                    "ORDER BY id DESC LIMIT ?", (META_WINDOW,)).fetchall()
            results = [r[0] or 0.0 for r in rows][::-1]
            meta["recent"] = results[-META_WINDOW:]
            meta["threshold"] = meta_threshold(
                results, base=getattr(e, "user_threshold", 0.05))
            meta["system_win_rate"] = system_win_rate(results)
        except Exception:
            pass

        # record learning-curve history point
        now = time.time()
        if not e.learning_history or now - e.learning_history[-1]["t"] > 120:
            weights = [s.get("weight", 1.0)
                       for s in e.strategy_stats.values()]
            e.learning_history.append({
                "t": now,
                "avg_weight": round(sum(weights) / max(len(weights), 1), 3),
                "threshold": meta.get("threshold", 0.05),
                "sys_wr": meta.get("system_win_rate"),
                "trained": sum(1 for s in e.strategy_stats.values()
                               if s.get("trades", 0) > 0),
            })
            e.learning_history = e.learning_history[-HISTORY_MAX:]
            save_history(e.learning_history)

        # trained = strategies with enough trades (speed scales the bar)
        speed = getattr(e, "learn_speed", 1.0)
        trained_bar = max(1, int(round(5 / speed)))   # ×2 speed → 3 tregti
        trained = sum(1 for s in e.strategy_stats.values()
                      if s.get("trades", 0) >= trained_bar)
        if trained:
            top = sorted(
                ((n, s.get("weight", 1.0), s.get("trades", 0))
                 for n, s in e.strategy_stats.items() if s.get("trades", 0) > 0),
                key=lambda x: x[1], reverse=True)[:3]
            wr = meta.get("system_win_rate")
            wr_s = f" · sistemi {wr}%" if wr is not None else ""
            self.report(
                f"🎓 {trained}/10 strategji të trajnuara · prag "
                f"{meta.get('threshold', 0.05):.2f}{wr_s} · më të forta: "
                f"{', '.join(n for n, _, _ in top)}")
        else:
            self.report("🎓 Në pritje të tregtive për të mësuar")


# ======================================================================
# ALL 20 AGENTS (order = execution order)
# ======================================================================
ALL_AGENTS = ([ScannerAgent] + STRATEGY_AGENTS +
              [EnsembleVoterAgent, GridBalancerAgent, ConsensusAgent,
               AIPredictorAgent, RegimeFilterAgent, ValidatorAgent,
               RiskManagerAgent, SizerAgent, PyramidAgent, FillerAgent,
               TrackerAgent, LearningAgent])
# ============ engine.py ============
"""
Waynis AI — trading engine (COORDINATOR).

The coordinator owns the account state and drives the six specialised
trading agents (agents.py) through the 6-Cycle Execution Pipeline:

    Scan → Predict → Validate → Size → Fill → Track

Modes:
  * paper (default) — simulated trades with REAL market prices.
  * real  — REAL money, SPOT only, LONG-only, on Binance (or OKX).
            Keys come from environment variables only. TP/SL are attached
            to the exchange (bracket orders) for protection.
"""
import asyncio
import json
import os
import random
import sqlite3
import time
from datetime import datetime, timezone

from config import (STARTING_BALANCE, CYCLE_SECONDS, SCAN_BATCH, TRADE_RISK,
                    TAKE_PROFIT, STOP_LOSS, BREAKEVEN_AT, MIN_CONFIDENCE,
                    MAX_OPEN, FEE_RATE, REAL_MIN_NOTIONAL,
                    REAL_MAX_NOTIONAL_PCT, REAL_MAX_POSITIONS,
                    ENABLE_PARTIAL_TP, TP1_PARTIAL, PARTIAL_FRACTION,
                    TRAIL_PCT, RUNNER_BE,
                    EQUITY_LOCK_ENABLED, EQUITY_LOCK_PCT,
                    EQUITY_LOCK_PAUSE_MIN,
                    DCA_ENABLED, DCA_AMOUNT, DCA_INTERVAL_MIN, DCA_SYMBOL,
                    COMPOUND_MULT_MAX,
                    RISK_ADAPTIVE_ENABLED, RISK_LOOKBACK, RISK_BAD_WR,
                    RISK_BAD_NET, RISK_DELEVERAGE_TO, RISK_PAUSE_MIN,
                    RISK_RESUME_MIN,
                    FIXED_RISK_ENABLED, FIXED_ENTRY_USD, FIXED_MAX_LOSS_USD,
                    ENSEMBLE_ENABLED, AGENT_TARGET, MAX_PYRAMID)
from providers import MarketData, WATCHLIST
from agents import (CycleContext, ScannerAgent, ALL_AGENTS,
                    load_weights, save_weights, DEFAULT_STATS)
from brain import AIBrain
from exchange import get_exchange, to_exchange_symbol
from learning import load_history, enrich
from strategies import generate_variant_strategies
from turso import (query as turso_query, exec_sql as turso_exec,
                   batch_exec as turso_batch, enabled as turso_enabled,
                   _creds as _turso_creds)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "paper.db")
SETTINGS_PATH = os.path.join(BASE_DIR, "data", "trading_config.json")

PIPELINE_AGENTS = [  # metadata for the UI
    {"name": "Scanner",   "icon": "📡", "role": "Tërheq çmime live + qirinj"},
    {"name": "Predictor", "icon": "🎯", "role": "EMA 9/21 + RSI 14 parashikim"},
    {"name": "Validator", "icon": "✅", "role": "Rregullat e rrezikut dhe volumit"},
    {"name": "Sizer",     "icon": "⚖️", "role": "Madhësia e pozicionit (fiks / komponim)"},
    {"name": "Filler",    "icon": "⚡", "role": "Ekzekutimi i urdhrit"},
    {"name": "Tracker",   "icon": "📊", "role": "TP / SL / trailing / PnL live"},
]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _load_settings():
    """Load settings: SQLite first (most durable), then JSON fallback."""
    try:
        db = sqlite3.connect(DB_PATH)
        try:
            row = db.execute("SELECT value FROM settings WHERE key='cfg'").fetchone()
            if row:
                return json.loads(row[0])
        except Exception:
            pass
        finally:
            db.close()
    except Exception:
        pass
    try:
        with open(SETTINGS_PATH) as f:
            return json.load(f)
    except Exception:
        return {"mode": "paper"}


def _save_settings(s):
    """Save settings to SQLite (durable on Render) AND JSON (fallback)."""
    try:
        db = sqlite3.connect(DB_PATH)
        db.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
        db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('cfg',?)",
                   (json.dumps(s),))
        db.commit()
        db.close()
    except Exception:
        pass
    try:
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w") as f:
            json.dump(s, f, indent=2)
    except Exception:
        pass


class PaperEngine:
    def __init__(self, market: MarketData):
        self.market = market
        self.loop = None
        self._lock = asyncio.Lock()
        self.running = True
        self.auto_trade = True
        # 🪜 SPOT-ONLY mode: kur aktiv, boti normal nuk hap tregti të reja
        # (vetëm spot pyramiding punon). Ruhet në cilësimet.
        self.spot_only = bool(_load_settings().get("spot_only", False))
        # cilësimi ruhet edhe në Turso (cloud) — mbijeton rindezjet e Render-it
        try:
            _sp = turso_query("SELECT val FROM kv WHERE key='spot_only'")
            if _sp and _sp[0][0] is not None:
                self.spot_only = str(_sp[0][0]).lower() in ("1", "true", "yes")
        except Exception:
            pass
        if self.spot_only:
            self.auto_trade = False
        self.compound = True          # COMPOUND sizing by default
        self.started_at = time.time() # session start (big timer in UI)
        self.scan_count = 0           # charts analysed by the agents
        settings = _load_settings()
        self.mode = settings.get("mode", "paper")   # "paper" | "real"
        self.exchange = get_exchange()              # real-money client
        self.real_balance_cache = (0.0, 0.0)        # (ts, balance)
        self.lock_until = 0.0                       # 🔒 profit-lock until ts
        self.equity_lock_enabled = settings.get("equity_lock_enabled",
                                                EQUITY_LOCK_ENABLED)
        self.equity_lock_pct = settings.get("equity_lock_pct", EQUITY_LOCK_PCT)
        self.compound_mult = float(settings.get("compound_mult", 1.0))  # ×1..×2
        # 🛡️ adaptive risk state (protects against ×2 losses)
        self.risk_pause_until = 0.0
        self.risk_state = {"mode": "normal", "mult": self.compound_mult,
                           "pause_until": 0.0, "last_check": 0.0,
                           "wr": None, "net": None}
        # 🧩 ensemble — hundreds of strategy variants vote with the core
        self.variant_strategies = generate_variant_strategies(
            AGENT_TARGET) if ENSEMBLE_ENABLED else []
        self.variant_count = len(self.variant_strategies)
        self.ensemble_round = 0                 # 🔁 mostër rrotulluese (100k agjentë)
        # 💵 fixed dollar risk (entry fixed, max loss fixed, ignores ×N)
        self.fixed_risk_enabled = settings.get("fixed_risk_enabled",
                                               FIXED_RISK_ENABLED)
        self.fixed_entry_usd = settings.get("fixed_entry_usd", FIXED_ENTRY_USD)
        self.fixed_max_loss_usd = settings.get("fixed_max_loss_usd",
                                               FIXED_MAX_LOSS_USD)
        # 📈 DCA state
        self.dca_enabled = settings.get("dca_enabled", DCA_ENABLED)
        self.dca_amount = settings.get("dca_amount", DCA_AMOUNT)
        self.dca_interval = settings.get("dca_interval_min", DCA_INTERVAL_MIN)
        self.dca_symbol = settings.get("dca_symbol", DCA_SYMBOL)
        # 🎯 multi-timeframe cache
        self.mtf_cache = {}                          # symbol -> (ts, closes)
        # ⚡ perf caches (make cycles much faster)
        self.klines_cache = {}                       # (sym,bar) -> (ts, klines)
        self.ensemble_cache = {}                     # sym -> (ts, votes)
        # ⚙️ user learning controls
        self.user_threshold = float(settings.get("user_threshold", 0.05))
        self.learn_speed = float(settings.get("learn_speed", 1.0))  # 0.5 slow..2 fast
        self.strategy_stats = load_weights()        # 🎓 learned weights
        self.learning_last_id = int(self.strategy_stats.pop("__last_trade_id", 0) or 0)
        self.meta_state = {"recent": [], "threshold": 0.05,
                           "system_win_rate": None}
        self.learning_history = load_history()      # learning curve points
        # twenty autonomous agents + coordinator (this engine)
        self.agents = [cls(self) for cls in ALL_AGENTS]
        self.pipeline = {
            "step": 0,
            "step_name": "Scanner",
            "agent": "Scanner",
            "agent_icon": "📡",
            "message": "Duke nisur 6 agjentët dhe koordinatorin…",
            "symbol": None,
            "direction": None,
            "confidence": 0.0,
            "since": now_iso(),
            "last_cycle_ms": 0,
            "cycles_run": 0,
        }
        self.equity_history = []          # [(ts, equity)] — për kurbën komponuese
        self.cooldown = {}                # symbol -> ts (rihapje e ndaluar 5 min)
        self.last_tickers = {}            # latest tickers for mark-to-market
        self.last_ai = None               # latest AI verdict (for UI)
        self.last_ai_refused = None       # latest AI veto (for UI)
        self.brain = AIBrain(self)        # 🧠 AI reasoning layer (background)
        self._ensure_db()

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------
    def get_klines_cached(self, symbol, interval="1m", limit=60, ttl=4.0):
        """Reuse klines for TTL seconds → no refetch every cycle."""
        key = (symbol, interval)
        now = time.time()
        hit = self.klines_cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
        return None

    def _ensure_db(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS account(
                id INTEGER PRIMARY KEY CHECK(id=1),
                balance REAL, peak REAL, started_at TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS trades(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT, side TEXT, entry REAL, exit REAL, qty REAL,
                tp REAL, sl REAL, status TEXT, opened_at TEXT, closed_at TEXT,
                pnl REAL, confidence REAL, reason TEXT,
                fees REAL, bracket TEXT, votes TEXT,
                tp1 REAL, tp1_hit INTEGER DEFAULT 0,
                partial_pnl REAL, trail_high REAL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT, type TEXT, msg TEXT, symbol TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS dca_buys(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL, symbol TEXT, price REAL,
                amount_usd REAL, qty REAL)""")
            # migrate older DBs: add fees/bracket/votes/partial-tp if missing
            cols = [r[1] for r in c.execute("PRAGMA table_info(trades)").fetchall()]
            for col, ddl in [("fees", "REAL"), ("bracket", "TEXT"),
                             ("votes", "TEXT"), ("tp1", "REAL"),
                             ("tp1_hit", "INTEGER DEFAULT 0"),
                             ("partial_pnl", "REAL"),
                             ("trail_high", "REAL")]:
                if col not in cols:
                    try:
                        c.execute(f"ALTER TABLE trades ADD COLUMN {col} {ddl}")
                    except Exception:
                        pass
            row = c.execute("SELECT * FROM account WHERE id=1").fetchone()
            pending = []
            if not row:
                c.execute(
                    "INSERT INTO account(id,balance,peak,started_at) VALUES(1,?,?,?)",
                    (STARTING_BALANCE, STARTING_BALANCE, now_iso()))
                self._turso_ensure_schema()
                if not self._turso_restore(c, pending):
                    # 🎨 DEMO e bukur (sipas kërkesës së përdoruesit): një
                    # histori e shënuar "demo" që e bën panelin të gjallë.
                    # Këto JANË numra jo-realë — shënohen si "demo" në panel.
                    self._seed_history(c)
                    self._seed_equity(c)
                    pending.append(
                        ("seed",
                         "🎨 Demo e mbjellë (numra jo-realë, për pamje) — "
                         "fitimi i vërtetë vjen nga tregtitë reale të botit"))
                    if turso_enabled():
                        pending.append(
                            ("sync",
                             "☁️ Turso i lidhur — ruajtja përgjithmonë aktive"))
        # 🔒 ngjarjet emetohen PAS mbylljes së transaksionit — një lidhje
        # e dytë e hapur brenda "with" shkakton "database is locked" në Render
        for etype, msg in pending:
            self._event(etype, msg)

    def _conn(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        # timeout: pret deri 15s nëse një lidhje tjetër e mban skedarin
        # (parandalon "database is locked" në Render/Python 3.11)
        return sqlite3.connect(DB_PATH, timeout=15)

    # ------------------------------------------------------------------
    # ☁️ Turso — ruajtja përgjithmonë (databazë falas në internet)
    # ------------------------------------------------------------------
    def _turso_ensure_schema(self):
        if not turso_enabled():
            return
        turso_exec(
            "CREATE TABLE IF NOT EXISTS account(id INTEGER PRIMARY KEY, "
            "balance REAL, peak REAL, started_at TEXT)")
        turso_exec(
            "CREATE TABLE IF NOT EXISTS trades(id INTEGER PRIMARY KEY, "
            "symbol TEXT, side TEXT, entry REAL, exit REAL, qty REAL, "
            "tp REAL, sl REAL, status TEXT, opened_at TEXT, closed_at TEXT, "
            "pnl REAL, confidence REAL, reason TEXT, fees REAL, "
            "bracket TEXT, votes TEXT, tp1 REAL, tp1_hit INTEGER DEFAULT 0, "
            "partial_pnl REAL, trail_high REAL)")
        turso_exec(
            "CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY "
            "AUTOINCREMENT, ts TEXT, type TEXT, msg TEXT, symbol TEXT)")

    def _turso_restore(self, c, pending=None):
        """Nëse lokalja u fshi (rindezje Render), rikthe historinë e
        vërtetë nga Turso. Kthen True nëse u rikthye diçka.
        `pending` = listë ku shtohen ngjarjet që do të emetohen PAS
        transaksionit (shmang "database is locked")."""
        if not turso_enabled():
            return False
        rows = turso_query(
            "SELECT id,symbol,side,entry,exit,qty,tp,sl,status,opened_at,"
            "closed_at,pnl,confidence,reason,fees,bracket,votes,tp1,"
            "tp1_hit,partial_pnl,trail_high FROM trades ORDER BY id")
        if not rows:
            return False
        c.execute("DELETE FROM trades")
        for r in rows:
            if len(r) < 21:
                continue
            (tid, symbol, side, entry, exit_px, qty, tp, sl, status,
             opened_at, closed_at, pnl, confidence, reason, fees, bracket,
             votes, tp1, tp1_hit, partial_pnl, trail_high) = r
            c.execute(
                "INSERT INTO trades(id,symbol,side,entry,exit,qty,tp,sl,"
                "status,opened_at,closed_at,pnl,confidence,reason,fees,"
                "bracket,votes,tp1,tp1_hit,partial_pnl,trail_high) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (tid, symbol, side, entry, exit_px, qty, tp, sl, status,
                 opened_at, closed_at, pnl, confidence, reason, fees,
                 bracket, votes, tp1, tp1_hit, partial_pnl, trail_high))
        acct = turso_query(
            "SELECT balance, peak, started_at FROM account WHERE id=1")
        if acct and acct[0]:
            bal, peak, started = acct[0]
            c.execute(
                "UPDATE account SET balance=?, peak=?, started_at=? WHERE id=1",
                (bal if bal is not None else STARTING_BALANCE,
                 peak if peak is not None else STARTING_BALANCE,
                 started or now_iso()))
        if pending is not None:
            pending.append(("sync",
                            f"☁️ Historia u rikthye nga Turso "
                            f"({len(rows)} tregti) — asgjë nuk humbi"))
        else:
            self._event("sync",
                        f"☁️ Historia u rikthye nga Turso "
                        f"({len(rows)} tregti) — asgjë nuk humbi")
        return True

    def turso_status(self):
        """Për panelin: a është lidhur ruajtja përgjithmonë? (+ detaje diagnostike)"""
        import os as _os
        base = _os.path.dirname(_os.path.abspath(__file__))
        jf = _os.path.join(base, "turso.json")
        file_ok = _os.path.exists(jf)
        env_url = bool(_os.environ.get("TURSO_URL", "").strip())
        env_tok = bool(_os.environ.get("TURSO_TOKEN", "").strip())
        if not turso_enabled():
            return {"enabled": False, "db": None,
                    "debug": {"file_found": file_ok, "env_url": env_url,
                              "env_token": env_tok, "base": base}}
        try:
            u, _ = _turso_creds()
            return {"enabled": True,
                    "db": u.split("://", 1)[-1].split(".")[0] + ".turso.io",
                    "debug": {"file_found": file_ok, "env_url": env_url,
                              "env_token": env_tok}}
        except Exception:
            return {"enabled": False, "db": None,
                    "debug": {"file_found": file_ok, "env_url": env_url,
                              "env_token": env_tok}}

    def _turso_push_snapshot(self):
        """Shtyn historinë e vërtetë + balancën në Turso (një kërkesë).
        Nuk prek tregtitë demo (seed). Nëse Turso është offline, vazhdojmë
        lokal — rindezja tjetër e suksesshme sinkronizon gjithçka."""
        if not turso_enabled():
            return
        try:
            with self._conn() as c:
                rows = c.execute(
                    "SELECT id,symbol,side,entry,exit,qty,tp,sl,status,"
                    "opened_at,closed_at,pnl,confidence,reason,fees,bracket,"
                    "votes,tp1,tp1_hit,partial_pnl,trail_high FROM trades "
                    "WHERE reason IS NULL OR reason != 'seed-history'"
                ).fetchall()
                bal, peak, started = c.execute(
                    "SELECT balance, peak, started_at FROM account WHERE id=1"
                ).fetchone()
        except Exception:
            return
        if not rows and bal is None:
            return
        items = [
            ("DELETE FROM trades WHERE reason IS NULL OR "
             "reason != 'seed-history'", [])]
        placeholders = ",".join("?" * 21)
        for r in rows:
            items.append((
                "INSERT INTO trades(id,symbol,side,entry,exit,qty,tp,sl,"
                "status,opened_at,closed_at,pnl,confidence,reason,fees,"
                "bracket,votes,tp1,tp1_hit,partial_pnl,trail_high) "
                "VALUES(" + placeholders + ")", list(r)))
        items.append((
            "INSERT INTO account(id,balance,peak,started_at) VALUES(1,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET balance=excluded.balance, "
            "peak=excluded.peak, started_at=excluded.started_at",
            [bal if bal is not None else STARTING_BALANCE,
             peak if peak is not None else STARTING_BALANCE,
             started or now_iso()]))
        turso_batch(items)

    def _seed_history(self, c):
        """Seed a fixed paper history so the dashboard feels alive.

        🎯 DETERMINISTE: përdor random.Random(20260808) — çdo rindezje
        prodhon TË NJËJTËT tregti, TË NJËJTËN balancë dhe TË NJËJTIN
        "Sot" (nuk kërcejnë më numrat 52→32 pas rifreskimit/rihapjes).
        Tregtitë shpërndahen në 5 orët e fundit që të mos dalin nga
        dritarja 24-orëshe e pnl_24h gjatë sesionit.
        """
        rng = random.Random(20260808)         # 🔒 fiks — po këto çdo herë
        symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT",
                   "XRP-USDT", "DOGE-USDT", "ADA-USDT"]
        base_px = {"BTC-USDT": 64000, "ETH-USDT": 3100, "SOL-USDT": 145,
                   "BNB-USDT": 590, "XRP-USDT": 0.55, "DOGE-USDT": 0.07,
                   "ADA-USDT": 0.20}
        base = time.time() - 5 * 3600         # 5 orët e fundit (të qëndrueshme)
        trades = []
        for i in range(14):
            sym = symbols[i % len(symbols)]
            entry = base_px[sym] * (0.97 + rng.random() * 0.06)
            win = i not in (3, 11)          # 12 wins / 2 losses -> 85.7%
            side = "LONG" if rng.random() > 0.3 else "SHORT"
            notional = 1200 + rng.random() * 1800   # $1.2k–$3k pozicion
            qty = notional / entry
            if win:
                pnl = round(notional * 0.0026 * (0.8 + rng.random() * 0.5))
                status = "win"
            else:
                pnl = -round(notional * 0.0055 * (0.8 + rng.random() * 0.4))
                status = "loss"
            exit_px = entry + (pnl / qty) if side == "LONG" else entry - (pnl / qty)
            opened = base + i * 1100 + rng.random() * 400
            closed = opened + 180 + rng.random() * 900
            tp_px = entry * (1.0045 if side == "LONG" else 0.9955)
            sl_px = entry * (0.9965 if side == "LONG" else 1.0035)
            trades.append((
                sym, side, entry, exit_px, qty, tp_px, sl_px, status,
                datetime.fromtimestamp(opened, timezone.utc).isoformat(),
                datetime.fromtimestamp(closed, timezone.utc).isoformat(),
                round(pnl, 2), 68 + rng.random() * 24,
                "seed-history",
            ))
        c.executemany(
            "INSERT INTO trades(symbol,side,entry,exit,qty,tp,sl,status,"
            "opened_at,closed_at,pnl,confidence,reason) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", trades)
        realized = sum(t[10] for t in trades)
        bal = STARTING_BALANCE + realized
        c.execute("UPDATE account SET balance=?, peak=MAX(peak,?) WHERE id=1",
                  (bal, bal))
        c.execute("INSERT INTO events(ts,type,msg,symbol) VALUES(?,?,?,?)",
                  (now_iso(), "seed",
                   "Historik demo i mbjellë: 14 tregti të mbyllura", None))

    def _seed_equity(self, c=None):
        if c is None:
            with self._conn() as conn:
                end = conn.execute(
                    "SELECT balance FROM account WHERE id=1").fetchone()[0]
        else:
            end = c.execute(
                "SELECT balance FROM account WHERE id=1").fetchone()[0]
        now = time.time()
        pts = []
        n = 36
        span = 24 * 3600
        rng = random.Random(20260808)         # 🔒 kurba fikse — e njëjtë çdo herë
        for i in range(n + 1):
            frac = i / n
            t = now - (n - i) * (span / n)
            val = STARTING_BALANCE + (end - STARTING_BALANCE) * frac
            if 0 < i < n:    # pika e parë (24 orë më parë) = saktësisht 10,000
                val += (rng.random() - 0.5) * max(8.0, abs(end - STARTING_BALANCE) * 0.03)
            pts.append((t, round(val, 2)))
        self.equity_history = pts

    def set_compound_mult(self, mult):
        self.compound_mult = max(1.0, min(COMPOUND_MULT_MAX, float(mult)))
        s = _load_settings()
        s["compound_mult"] = self.compound_mult
        _save_settings(s)
        self.risk_state["mult"] = self.compound_mult
        self._event("settings",
                    f"💥 Komponimi ×{self.compound_mult:g} — "
                    f"pozicionet {'dyfishohen' if self.compound_mult >= 2 else 'normale'}")
        return self.compound_mult

    # ------------------------------------------------------------------
    # 🛡️ Adaptive risk — protects against ×2 losses
    # ------------------------------------------------------------------
    def effective_mult(self):
        """The multiplier actually used by the Sizer. The risk manager can
        temporarily reduce ×2 → ×1 when the bot is losing, so losses never
        actually run at ×2 while we're in a bad patch."""
        if self.is_risk_paused():
            return 1.0
        return self.risk_state.get("mult", self.compound_mult)

    def is_risk_paused(self):
        return time.time() < self.risk_pause_until

    def risk_info(self):
        s = self.risk_state
        return {
            "adaptive": RISK_ADAPTIVE_ENABLED,
            "mode": s.get("mode"),
            "mult": s.get("mult"),
            "effective_mult": self.effective_mult(),
            "user_mult": self.compound_mult,
            "paused": self.is_risk_paused(),
            "pause_until": s.get("pause_until", 0.0),
            "wr": s.get("wr"),
            "net": s.get("net"),
        }

    def set_learning(self, threshold=None, speed=None):
        if threshold is not None:
            self.user_threshold = max(0.03, min(0.12, float(threshold)))
        if speed is not None:
            self.learn_speed = max(0.5, min(3.0, float(speed)))
        s = _load_settings()
        s["user_threshold"] = self.user_threshold
        s["learn_speed"] = self.learn_speed
        _save_settings(s)
        self._event("settings",
                    f"🎓 Mësimi: pragu {self.user_threshold:.2f}, "
                    f"shpejtësia ×{self.learn_speed:g}")
        return self.learning_controls()

    def learning_controls(self):
        return {"threshold": self.user_threshold, "speed": self.learn_speed}

    def set_fixed_risk(self, enabled=None, entry=None, max_loss=None):
        if enabled is not None:
            self.fixed_risk_enabled = bool(enabled)
        if entry is not None:
            self.fixed_entry_usd = max(1.0, float(entry))
        if max_loss is not None:
            self.fixed_max_loss_usd = max(0.25, float(max_loss))
        s = _load_settings()
        s.update({"fixed_risk_enabled": self.fixed_risk_enabled,
                  "fixed_entry_usd": self.fixed_entry_usd,
                  "fixed_max_loss_usd": self.fixed_max_loss_usd})
        _save_settings(s)
        self._event("settings",
                    f"💵 Rrezik fiks: {'ON' if self.fixed_risk_enabled else 'OFF'} — "
                    f"hyrje ${self.fixed_entry_usd:.2f}, humbje max "
                    f"${self.fixed_max_loss_usd:.2f} (pavarësisht ×N)")
        return self.fixed_risk_info()

    def fixed_risk_info(self):
        return {"enabled": self.fixed_risk_enabled,
                "entry_usd": self.fixed_entry_usd,
                "max_loss_usd": self.fixed_max_loss_usd}

    def recent_closed(self, n=RISK_LOOKBACK):
        with self._conn() as c:
            rows = c.execute(
                "SELECT pnl, status FROM trades WHERE status!='open' "
                "ORDER BY id DESC LIMIT ?", (n,)).fetchall()
        return [(p or 0.0, st) for p, st in rows][::-1]

    def risk_manager_tick(self):
        """Called each cycle: evaluate recent performance and adjust risk.
        Returns True if trading should be paused (new entries blocked)."""
        if not RISK_ADAPTIVE_ENABLED:
            return False
        now = time.time()
        # cooldown between checks
        if now - self.risk_state.get("last_check", 0) < RISK_RESUME_MIN * 60:
            return self.is_risk_paused()

        recent = self.recent_closed()
        if len(recent) < 4:
            return False
        wins = sum(1 for _, st in recent if st == "win")
        wr = wins / len(recent)
        net = sum(p for p, _ in recent)
        self.risk_state["wr"] = round(wr * 100, 1)
        self.risk_state["net"] = round(net, 2)
        self.risk_state["last_check"] = now

        # losing → de-risk (reduce ×2 to ×1) and/or pause
        if wr < RISK_BAD_WR or net < RISK_BAD_NET:
            if self.compound_mult >= 2:
                self.risk_state["mult"] = RISK_DELEVERAGE_TO
                self.risk_state["mode"] = "de-risk"
                self._event(
                    "risk",
                    f"🛡️ Risk Manager: humbje në {len(recent)} tregtitë e fundit "
                    f"(WR {wr*100:.0f}%, net ${net:+.2f}) → komponimi u ul "
                    f"në ×{RISK_DELEVERAGE_TO:g} për t'u mbrojtur")
            self.risk_pause_until = now + RISK_PAUSE_MIN * 60
            self.risk_state["pause_until"] = self.risk_pause_until
            self.risk_state["mode"] = "pause"
            self._event(
                "risk",
                f"🛡️ Risk Manager: push {RISK_PAUSE_MIN} min — ndal tregtitë e reja "
                f"derisa tregu të stabilizohet (WR {wr*100:.0f}%, net ${net:+.2f})")
            return True

        # performing well → restore the user's multiplier
        if self.risk_state.get("mult", 1.0) < self.compound_mult:
            self.risk_state["mult"] = self.compound_mult
            self.risk_state["mode"] = "normal"
            self._event("risk",
                        f"🛡️ Risk Manager: performancë e mirë (WR {wr*100:.0f}%) "
                        f"→ komponimi u kthye në ×{self.compound_mult:g}")
        else:
            self.risk_state["mode"] = "normal"
        return False

    # ------------------------------------------------------------------
    # 🔒 Equity profit lock
    # ------------------------------------------------------------------
    def is_locked(self):
        return time.time() < self.lock_until

    def lock_info(self):
        return {
            "enabled": bool(self.equity_lock_enabled),
            "pct": self.equity_lock_pct,
            "locked": self.is_locked(),
            "until": self.lock_until,
        }

    def set_equity_lock(self, enabled=None, pct=None):
        if enabled is not None:
            self.equity_lock_enabled = bool(enabled)
        if pct is not None:
            self.equity_lock_pct = max(0.003, min(0.15, float(pct)))
        s = _load_settings()
        s["equity_lock_enabled"] = self.equity_lock_enabled
        s["equity_lock_pct"] = self.equity_lock_pct
        _save_settings(s)
        self._event("settings",
                    f"🔒 Mbrojtja e fitimit: {'ON' if self.equity_lock_enabled else 'OFF'} "
                    f"({self.equity_lock_pct*100:.1f}% nga kulmi)")
        return self.lock_info()

    async def _close_all(self, reason="lock"):
        closed = 0
        for pos in self.open_positions():
            price = self.last_tickers.get(pos["symbol"], {}).get("price") \
                or pos["entry"]
            if self.mode == "real":
                await self.real_close(pos, price, reason)
            else:
                await self._close_trade(pos, price, reason)
            closed += 1
        return closed

    async def check_profit_lock(self):
        """If equity falls more than X% below its peak, close EVERYTHING
        and pause new entries — this is the 'don't give back the gains'
        protection."""
        if not self.equity_lock_enabled or self.is_locked():
            return False
        acc = self.account()
        eq = acc["equity"]
        with self._conn() as c:
            row = c.execute("SELECT peak FROM account WHERE id=1").fetchone()
            peak = float(row[0]) if row and row[0] else eq
        if eq > peak:
            with self._conn() as c:
                c.execute("UPDATE account SET peak=? WHERE id=1", (eq,))
            return False
        floor = peak * (1.0 - self.equity_lock_pct)
        if eq < floor and peak > 0:
            n = await self._close_all("lock")
            self.lock_until = time.time() + EQUITY_LOCK_PAUSE_MIN * 60
            with self._conn() as c:
                c.execute("UPDATE account SET peak=? WHERE id=1",
                          (self.account()["equity"],))
            self._event(
                "lock",
                f"🔒 Mbrojtja e fitimit: equity ra nën {self.equity_lock_pct*100:.1f}% "
                f"nga kulmi ${peak:.2f} → u mbyllën {n} pozicione. "
                f"Push {EQUITY_LOCK_PAUSE_MIN} min para tregtive të reja.",
                None)
            self._set_pipeline(0, "Lock", "🔒 Profit-lock aktiv — push përkohësisht")
            return True
        return False

    # ------------------------------------------------------------------
    # 📈 DCA (dollar-cost averaging)
    # ------------------------------------------------------------------
    def dca_set(self, enabled=None, amount=None, interval=None, symbol=None):
        if enabled is not None:
            self.dca_enabled = bool(enabled)
        if amount is not None:
            self.dca_amount = max(1.0, float(amount))
        if interval is not None:
            self.dca_interval = max(5, int(interval))
        if symbol:
            self.dca_symbol = str(symbol).upper()
        s = _load_settings()
        s.update({"dca_enabled": self.dca_enabled, "dca_amount": self.dca_amount,
                  "dca_interval_min": self.dca_interval,
                  "dca_symbol": self.dca_symbol})
        _save_settings(s)
        self._event("settings",
                    f"📈 DCA: {'ON' if self.dca_enabled else 'OFF'} — "
                    f"${self.dca_amount} çdo {self.dca_interval} min te {self.dca_symbol}")
        return self.dca_status()

    def dca_status(self):
        with self._conn() as c:
            rows = c.execute(
                "SELECT id,ts,symbol,price,amount_usd,qty FROM dca_buys "
                "ORDER BY id").fetchall()
        buys = [{"id": r[0], "ts": r[1], "symbol": r[2], "price": r[3],
                 "amount_usd": r[4], "qty": r[5]} for r in rows]
        total_invested = sum(b["amount_usd"] for b in buys)
        total_qty = sum(b["qty"] for b in buys)
        price = self.last_tickers.get(self.dca_symbol, {}).get("price") or 0.0
        if not price and buys:
            price = buys[-1]["price"]
        value = total_qty * price if price else 0.0
        pnl = value - total_invested
        pnl_pct = (pnl / total_invested * 100) if total_invested else 0.0
        return {
            "enabled": self.dca_enabled,
            "amount": self.dca_amount,
            "interval_min": self.dca_interval,
            "symbol": self.dca_symbol,
            "buys": len(buys),
            "total_invested": round(total_invested, 2),
            "total_qty": round(total_qty, 8),
            "current_price": round(price, 8),
            "value": round(value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "last_buy_ts": buys[-1]["ts"] if buys else None,
        }

    async def dca_check(self):
        """If DCA enabled and interval passed -> make the periodic buy."""
        if not self.dca_enabled:
            return
        try:
            with self._conn() as c:
                row = c.execute(
                    "SELECT MAX(ts) FROM dca_buys").fetchone()
            last_ts = row[0] or 0.0
            if time.time() - last_ts < self.dca_interval * 60:
                return
            price = self.last_tickers.get(self.dca_symbol, {}).get("price")
            if not price:
                tickers = await self.market.fetch_all_tickers()
                self.last_tickers = tickers
                price = self.last_tickers.get(self.dca_symbol, {}).get("price")
            if not price or price <= 0:
                return
            qty = self.dca_amount / price
            if self.mode == "real" and self.exchange.configured:
                sym = to_exchange_symbol(self.dca_symbol, self.exchange)
                await asyncio.to_thread(self.exchange.market_buy, sym, qty)
            with self._conn() as c:
                c.execute(
                    "INSERT INTO dca_buys(ts,symbol,price,amount_usd,qty) "
                    "VALUES(?,?,?,?,?)",
                    (time.time(), self.dca_symbol, price,
                     self.dca_amount, qty))
            self._event("dca",
                        f"📈 DCA: bleva ${self.dca_amount:.2f} {self.dca_symbol} "
                        f"@ {price:.4g} ({qty:.8f})",
                        self.dca_symbol)
        except Exception as e:
            self._event("error", f"DCA: {str(e)[:80]}")

    async def dca_backtest(self, symbol=None, amount=5.0, interval_days=1.0,
                           days=365):
        """Simulate DCA over the last N days using REAL daily candles.
        Shows what periodic buying would have returned."""
        symbol = symbol or self.dca_symbol
        candles = await self.market.fetch_klines_history(symbol, "1d", days + 10)
        if len(candles) < 30:
            return {"error": "Të dhëna të pamjaftueshme"}
        buys = []
        step = max(1, int(round(interval_days)))
        for i in range(0, len(candles), step):
            c = candles[i]
            buys.append({"ts": c["t"], "price": c["c"], "qty": amount / c["c"]})
        if not buys:
            return {"error": "Asnjë blerje"}
        total_invested = amount * len(buys)
        total_qty = sum(b["qty"] for b in buys)
        last_price = candles[-1]["c"]
        value = total_qty * last_price
        pnl = value - total_invested
        pnl_pct = pnl / total_invested * 100 if total_invested else 0
        first_price = buys[0]["price"]
        lump_value = (total_invested / first_price) * last_price
        lump_pnl = lump_value - total_invested
        avg_cost = total_invested / total_qty
        return {
            "symbol": symbol,
            "buys": len(buys),
            "amount_per_buy": amount,
            "interval_days": interval_days,
            "period_days": round((candles[-1]["t"] - candles[0]["t"]) / 86400000, 1),
            "total_invested": round(total_invested, 2),
            "total_qty": round(total_qty, 8),
            "avg_cost": round(avg_cost, 4),
            "last_price": round(last_price, 4),
            "value": round(value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "lump_pnl": round(lump_pnl, 2),
            "lump_pnl_pct": round((lump_value - total_invested) / total_invested * 100, 2),
        }

    # ------------------------------------------------------------------
    # Mode (paper / real)
    # ------------------------------------------------------------------
    def set_mode(self, mode):
        mode = "real" if mode == "real" else "paper"
        old = self.mode
        self.mode = mode
        _save_settings({"mode": mode})
        self._event("settings",
                    f"Modaliteti: {'💰 REAL (para të vërteta)' if mode == 'real' else '📝 Paper (demo)'}")
        if mode == "real":
            self.exchange = get_exchange()
        return mode

    def real_status(self):
        st = self.exchange.status()
        st["mode"] = self.mode
        st["min_notional"] = REAL_MIN_NOTIONAL
        st["max_positions"] = REAL_MAX_POSITIONS
        st["max_notional_pct"] = REAL_MAX_NOTIONAL_PCT
        st["fee_rate"] = FEE_RATE
        try:
            st["balance_usdt"] = self.real_balance()
        except Exception:
            st["balance_usdt"] = None
        return st

    def real_balance(self, force=False):
        """Cached USDT balance from the exchange (cache 10s)."""
        ts, bal = self.real_balance_cache
        if force or time.time() - ts > 10:
            bal = self.exchange.balance_usdt()
            self.real_balance_cache = (time.time(), bal)
        return bal

    # ------------------------------------------------------------------
    # Account / status helpers
    # ------------------------------------------------------------------
    def account(self):
        if self.mode == "real":
            try:
                bal = self.real_balance()
            except Exception:
                bal = 0.0
            return {
                "balance": round(bal, 2),
                "equity": round(bal, 2),
                "peak": round(max(bal, self.real_balance_cache[1]), 2) if False else round(bal, 2),
                "unrealized": 0.0,
                "growth": round(bal / STARTING_BALANCE, 4) if STARTING_BALANCE else 0.0,
                "started_at": now_iso(),
                "real": True,
            }
        with self._conn() as c:
            row = c.execute("SELECT balance,peak,started_at FROM account WHERE id=1").fetchone()
            balance, peak, started_at = float(row[0]), float(row[1]), row[2]
        open_pos = self.open_positions()
        unreal = sum(p["pnl"] for p in open_pos)
        equity = balance + unreal
        return {
            "balance": round(balance, 2),
            "equity": round(equity, 2),
            "peak": round(max(peak, equity), 2),
            "unrealized": round(unreal, 2),
            "growth": round(equity / STARTING_BALANCE, 4),
            "started_at": started_at,
            "real": False,
        }

    def open_positions(self):
        with self._conn() as c:
            rows = c.execute(
                "SELECT symbol,side,entry,qty,tp,sl,opened_at,id,confidence,"
                "bracket,tp1,tp1_hit,partial_pnl,trail_high "
                "FROM trades WHERE status='open'").fetchall()
        out = []
        for r in rows:
            (sym, side, entry, qty, tp, sl, opened, tid, conf, bracket,
             tp1, tp1_hit, partial_pnl, trail_high) = r
            price = self.last_tickers.get(sym, {}).get("price") or entry
            if side == "LONG":
                pnl = (price - entry) * qty
            else:
                pnl = (entry - price) * qty
            out.append({
                "id": tid, "symbol": sym, "side": side, "entry": entry,
                "qty": qty, "tp": tp, "sl": sl, "opened_at": opened,
                "confidence": conf, "pnl": round(pnl, 2), "price": price,
                "bracket": bracket, "tp1": tp1, "tp1_hit": bool(tp1_hit),
                "partial_pnl": round(partial_pnl or 0.0, 2),
                "trail_high": trail_high,
            })
        return out

    def _sell_partial(self, pos, price):
        """Take profit on half the position (TP1). Remaining half becomes a
        runner with a trailing stop — this is what makes wins bigger."""
        half = pos["qty"] * PARTIAL_FRACTION
        gross = (price - pos["entry"]) * half
        fees = (pos["entry"] * half + price * half) * FEE_RATE
        net = gross - fees
        with self._conn() as c:
            c.execute(
                "UPDATE trades SET qty=qty-?, tp1_hit=1, partial_pnl=?, sl=? "
                "WHERE id=?",
                (half, net, pos["entry"] * (1 + RUNNER_BE), pos["id"]))
            c.execute(
                "UPDATE account SET balance=balance+?, "
                "peak=MAX(peak,balance+?) WHERE id=1", (net, net))
        self._event(
            "partial",
            f"⚡ {pos['side']} {pos['symbol']}: TP1 +{TP1_PARTIAL*100:.1f}% — "
            f"gjysma u mbyll {net:+.2f} USDT · pjesa tjetër vazhdon me trailing",
            pos["symbol"])

    def stats(self):
        with self._conn() as c:
            closed = c.execute(
                "SELECT status, pnl, closed_at, fees FROM trades "
                "WHERE status!='open'").fetchall()
        wins = sum(1 for s, _, _, _ in closed if s == "win")
        total = len(closed)
        win_rate = round(100.0 * wins / total, 1) if total else 0.0
        realized = round(sum(p for _, p, _, _ in closed), 2)
        fees = round(sum(f for _, _, _, f in closed if f), 2)
        # asymmetry: average win vs average loss (the "arbitrage" edge)
        wins_pnl = [p for s, p, _, _ in closed if s == "win" and p > 0]
        loss_pnl = [p for s, p, _, _ in closed if s == "loss" and p < 0]
        avg_win = round(sum(wins_pnl) / len(wins_pnl), 2) if wins_pnl else 0.0
        avg_loss = round(sum(loss_pnl) / len(loss_pnl), 2) if loss_pnl else 0.0
        rr = round(avg_win / abs(avg_loss), 2) if avg_loss else 0.0
        now = time.time()
        cutoff = now - 86400
        snap24 = [e for e in self.equity_history if e[0] <= cutoff]
        if snap24:
            pnl24 = self.account()["equity"] - snap24[-1][1]
        else:
            pnl24 = round(sum(p for _, p, ts, _ in closed
                              if ts and datetime.fromisoformat(ts).timestamp() >= cutoff), 2)
        try:
            started = datetime.fromisoformat(self.account()["started_at"]).timestamp()
            hours = max((now - started) / 3600.0, 24.0)
            avg_day = round(realized / hours * 24.0, 2)
        except Exception:
            avg_day = 0.0
        return {
            "win_rate": win_rate,
            "wins": wins,
            "losses": total - wins,
            "trades": total,
            "realized": realized,
            "fees_paid": fees,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "rr": rr,
            "pnl_24h": round(pnl24, 2),
            "avg_day": avg_day,
            "open": len(self.open_positions()),
        }

    def agents_info(self):
        out = []
        for a in self.agents:
            info = {"name": a.name, "icon": a.icon, "role": a.role,
                    "step": a.step, "kind": a.kind,
                    "active": self.pipeline.get("agent") == a.name}
            if a.kind == "strategy":
                st = self.strategy_stats.get(a.name, dict(DEFAULT_STATS))
                info.update({"weight": st.get("weight", 1.0),
                             "wins": st.get("wins", 0),
                             "losses": st.get("losses", 0),
                             "trades": st.get("trades", 0),
                             "pnl": round(st.get("pnl", 0.0), 2)})
            out.append(info)
        return out

    # ------------------------------------------------------------------
    # Coordinator loop
    # ------------------------------------------------------------------
    async def run(self):
        self.loop = asyncio.get_running_loop()
        AIBrain.ensure_ollama()
        await self.brain.start()
        idx = 0
        while self.running:
            t0 = time.perf_counter()
            try:
                async with self._lock:
                    await self._cycle(idx)
                idx += 1
            except Exception as e:
                self._set_pipeline(0, "Scanner", f"Gabim: {e}")
            self.pipeline["last_cycle_ms"] = int((time.perf_counter() - t0) * 1000)
            self._sample_equity()
            await asyncio.sleep(CYCLE_SECONDS)

    async def run_cycle_now(self):
        async with self._lock:
            await self._cycle(-1)
        return self.pipeline

    async def _cycle(self, idx):
        self.pipeline["cycles_run"] += 1
        # 🔒 profit-lock check before anything else
        try:
            await self.check_profit_lock()
        except Exception:
            pass
        # 📈 DCA periodic buy
        try:
            await self.dca_check()
        except Exception:
            pass
        # 🛡️ adaptive risk check (protect against ×2 losses)
        try:
            self.risk_manager_tick()
        except Exception:
            pass
        ctx = CycleContext(self, self.market, idx)
        for agent in self.agents:
            if ctx.stop:
                break
            self.pipeline["agent"] = agent.name
            self.pipeline["agent_icon"] = agent.icon
            try:
                await agent.execute(ctx, idx)
            except Exception as exc:
                self._set_pipeline(agent.step, agent.name, f"Gabim: {exc}")
                break

    # ------------------------------------------------------------------
    # Order management (owned by the coordinator; agents call these)
    # ------------------------------------------------------------------
    def _open_trade(self, sig, qty, bracket=None, votes=None):
        if qty <= 0:
            return None
        entry = sig["entry"]
        tp1 = None
        if ENABLE_PARTIAL_TP and sig.get("direction") == "LONG":
            tp1 = entry * (1 + TP1_PARTIAL)
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO trades(symbol,side,entry,qty,tp,sl,status,"
                "opened_at,confidence,bracket,votes,tp1) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (sig["symbol"], sig["direction"], entry, qty,
                 sig["tp"], sig["sl"], "open", now_iso(), sig["confidence"],
                 json.dumps(bracket) if bracket else None,
                 json.dumps(votes or []), tp1))
            tid = cur.lastrowid
        # ☁️ ruaj përgjithmonë (PAS komitimit — përndryshe push-i nuk
        # e sheh tregtinë e re)
        self._turso_push_snapshot()
        return tid

    def _update_sl(self, trade_id, new_sl):
        with self._conn() as c:
            c.execute("UPDATE trades SET sl=? WHERE id=?", (new_sl, trade_id))

    def _set_trail_high(self, trade_id, peak):
        with self._conn() as c:
            c.execute("UPDATE trades SET trail_high=? WHERE id=?", (peak, trade_id))

    async def _close_trade(self, pos, price, reason, banked=None):
        """Close a PAPER position (with real fees simulated).
        If TP1 already banked half the profit, the trade's total PnL shown
        in the ledger = runner PnL + partial PnL (balance credits only the
        runner part — the partial was already credited at TP1).

        💵 `banked` = dollarë të plotë ($1, $2, $3...) që agjenti kyçi —
        fitimi regjistrohet si dollar i plotë, KURRË me centa (p.sh. JO $1.04).
        `min(pnl, banked)` garanton që kurrë nuk regjistrohet më shumë se
        fitimi real (neto) i pozicionit."""
        qty = pos["qty"]
        if pos["side"] == "LONG":
            gross = (price - pos["entry"]) * qty
        else:
            gross = (pos["entry"] - price) * qty
        fees = (pos["entry"] * qty + price * qty) * FEE_RATE
        pnl = gross - fees
        if banked is not None:
            pnl = round(min(pnl, banked), 2)     # 💵 dollar i plotë, kurrë centa
        partial = pos.get("partial_pnl") or 0.0
        total_pnl = pnl + partial
        status = "win" if total_pnl > 0 else "loss"
        with self._conn() as c:
            c.execute(
                "UPDATE trades SET exit=?, status=?, closed_at=?, pnl=?, "
                "reason=?, fees=? WHERE id=?",
                (price, status, now_iso(), total_pnl, reason, fees, pos["id"]))
            c.execute(
                "UPDATE account SET balance=balance+?, peak=MAX(peak,balance+?) "
                "WHERE id=1", (pnl, pnl))
        self.cooldown[pos["symbol"]] = time.time()
        self._turso_push_snapshot()          # ☁️ fitimi i kyçur ruhet
        if reason.startswith("smart:"):
            label = "Smart"
        elif reason == "tp":
            label = "TP"
        elif reason == "sl":
            label = "SL"
        else:
            label = "exit"
        self._event("close",
                    f"{pos['side']} {pos['symbol']} u mbyll ({label}) "
                    f"{'+' if total_pnl >= 0 else ''}{self._fmt_usd(total_pnl)} "
                    f"USDT (tarifa ${fees:.2f})",
                    pos["symbol"])

    def set_spot_only(self, active):
        """🪜 Kalon botin në modalitetin SPOT PYRAMIDING vetëm:
        auto_trade OFF (s'hap tregti të reja) + mbaj mend cilësimin."""
        self.spot_only = bool(active)
        self.auto_trade = not self.spot_only
        s = _load_settings()
        s["spot_only"] = self.spot_only
        _save_settings(s)
        try:
            turso_exec("INSERT INTO kv(key,val) VALUES('spot_only',?) "
                       "ON CONFLICT(key) DO UPDATE SET val=excluded.val",
                       ["1" if self.spot_only else "0"])
        except Exception:
            pass
        self._event("settings",
                    "🪜 SPOT PYRAMIDING " + ("AKTIV — vetëm spot pyramiding"
                                             if self.spot_only else
                                             "OFF — boti normal vazhdon"))

    async def close_all_open(self, reason="spot-only"):
        """Mbyll të gjitha pozicionet e hapura të botit normal."""
        try:
            pos = self.open_positions()
            for p in pos:
                price = p.get("price") or p["entry"]
                await self._close_trade(p, price, reason)
            self._turso_push_snapshot()
            self._event("settings",
                        f"📦 U mbyllën {len(pos)} pozicione — {reason}")
            return len(pos)
        except Exception:
            return 0

    async def _close_siblings(self, pos, price, reason):
        """🪜 Mbyll shtesat (sibling-et) e të njëjtit simbol+anë — përdoret
        kur SL i një pozicioni preket: i gjithë grupi del bashkë, si në
        strategjinë spot pyramiding (s'lihen shtesat të humbin më tej)."""
        try:
            sibs = [p for p in self.open_positions()
                    if p["symbol"] == pos["symbol"]
                    and p["side"] == pos["side"]
                    and p["id"] != pos["id"]]
            for s in sibs:
                await self._close_trade(s, price, reason)
        except Exception:
            pass

    def pyramid_summary(self):
        """Për panelin: sa grupe kanë shtesa piramidale."""
        try:
            with self._conn() as c:
                rows = c.execute(
                    "SELECT symbol, side, COUNT(*) FROM trades "
                    "WHERE status='open' GROUP BY symbol, side").fetchall()
        except Exception:
            rows = []
        groups = [{"symbol": s, "side": d, "entries": n}
                  for s, d, n in rows if n > 1]
        adds = sum(n - 1 for _, _, n in rows if n > 1)
        return {"groups": len(groups), "adds": adds,
                "max": MAX_PYRAMID, "active_groups": len(rows)}

    @staticmethod
    def _fmt_usd(x):
        """Formaton dollarët: $1 → '1', $1.37 → '1.37' (fitimet e kyçura
        janë gjithmonë dollarë të plotë, kështu dalin pa centa)."""
        return f"{x:g}" if abs(x - round(x)) < 1e-9 else f"{x:.2f}"

    # ------------------------------------------------------------------
    # REAL-money order management (spot, LONG-only)
    # ------------------------------------------------------------------
    async def real_open(self, sig, qty):
        """Open a real LONG position with TP/SL attached on the exchange."""
        ex = self.exchange
        sym = to_exchange_symbol(sig["symbol"], ex)
        try:
            res = await asyncio.to_thread(ex.market_buy, sym, qty)
        except Exception as e:
            self._event("error", f"💰 REAL: dështoi hapja {sym}: {str(e)[:100]}")
            return None
        fill = res.get("fill", {})
        exec_price = float(fill.get("fills", [{}])[0].get("price", 0)) if isinstance(fill, dict) else 0
        if not exec_price:
            exec_price = res.get("price", sig["entry"])
        entry = exec_price or sig["entry"]
        sig2 = dict(sig)
        sig2["entry"] = entry
        sig2["tp"] = entry * (1 + 0.0045)
        sig2["sl"] = entry * (1 - 0.0035)
        tid = self._open_trade(sig2, qty, bracket=res.get("bracket"))
        if tid:
            self._event("fill",
                        f"💰 REAL {sig['direction']} {sig['symbol']} "
                        f"{qty:.6f} @ {entry:.6g} (TP/SL në exchange)",
                        sig["symbol"])
        return tid

    async def real_close(self, pos, price, reason):
        """Close a real LONG position: cancel bracket, market sell."""
        ex = self.exchange
        sym = to_exchange_symbol(pos["symbol"], ex)
        qty = pos["qty"]
        try:
            bracket = json.loads(pos.get("bracket") or "[]")
            res = await asyncio.to_thread(ex.market_sell_all, sym, qty, bracket)
        except Exception as e:
            self._event("error",
                        f"💰 REAL: dështoi mbyllja {sym}: {str(e)[:100]}")
            return
        exit_price = price
        try:
            fills = res.get("fills", []) if isinstance(res, dict) else []
            if fills:
                exit_price = float(fills[0].get("price", price))
        except Exception:
            pass
        gross = (exit_price - pos["entry"]) * qty
        fees = (pos["entry"] * qty + exit_price * qty) * FEE_RATE
        pnl = gross - fees
        status = "win" if pnl > 0 else "loss"
        with self._conn() as c:
            c.execute(
                "UPDATE trades SET exit=?, status=?, closed_at=?, pnl=?, "
                "reason=?, fees=? WHERE id=?",
                (exit_price, status, now_iso(), pnl, reason, fees, pos["id"]))
        self.cooldown[pos["symbol"]] = time.time()
        self.real_balance_cache = (0.0, 0.0)
        self._turso_push_snapshot()          # ☁️ ruaj përgjithmonë
        label = "TP" if reason == "tp" else ("SL" if reason == "sl" else "exit")
        self._event("close",
                    f"💰 REAL {pos['side']} {pos['symbol']} u mbyll ({label}) "
                    f"{'+' if pnl >= 0 else ''}{pnl:.2f} USDT",
                    pos["symbol"])

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------
    def _set_pipeline(self, step, name, msg, symbol=None, direction=None, conf=None):
        self.pipeline.update({
            "step": step,
            "step_name": name,
            "agent": name,
            "message": msg,
            "symbol": symbol,
            "direction": direction,
            "confidence": conf if conf is not None else self.pipeline.get("confidence", 0),
            "since": now_iso(),
        })

    def _event(self, etype, msg, symbol=None):
        with self._conn() as c:
            c.execute("INSERT INTO events(ts,type,msg,symbol) VALUES(?,?,?,?)",
                      (now_iso(), etype, msg, symbol))
        with self._conn() as c:
            c.execute("DELETE FROM events WHERE id NOT IN "
                      "(SELECT id FROM events ORDER BY id DESC LIMIT 500)")

    def recent_events(self, limit=40):
        with self._conn() as c:
            rows = c.execute(
                "SELECT id,ts,type,msg,symbol FROM events ORDER BY id DESC LIMIT ?",
                (limit,)).fetchall()
        return [{"id": r[0], "ts": r[1], "type": r[2], "msg": r[3],
                 "symbol": r[4]} for r in rows]

    def trades(self, limit=60):
        with self._conn() as c:
            rows = c.execute(
                "SELECT id,symbol,side,entry,exit,qty,tp,sl,status,opened_at,"
                "closed_at,pnl,confidence,reason,fees,bracket,votes,tp1,"
                "tp1_hit,partial_pnl FROM trades "
                "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        keys = ["id", "symbol", "side", "entry", "exit", "qty", "tp", "sl",
                "status", "opened_at", "closed_at", "pnl", "confidence",
                "reason", "fees", "bracket", "votes", "tp1",
                "tp1_hit", "partial_pnl"]
        out = []
        for r in rows:
            d = dict(zip(keys, r))
            if d["status"] == "open":
                price = self.last_tickers.get(d["symbol"], {}).get("price") or d["entry"]
                if d["side"] == "LONG":
                    d["pnl"] = round((price - d["entry"]) * d["qty"], 2)
                else:
                    d["pnl"] = round((d["entry"] - price) * d["qty"], 2)
                d["price_live"] = price
            out.append(d)
        return out

    def equity_curve(self, limit=400):
        out = [{"t": int(ts), "e": eq} for ts, eq in self.equity_history[-limit:]]
        latest = self.account()["equity"]
        if not out or out[-1]["e"] != latest:
            out.append({"t": int(time.time()), "e": latest})
        return out

    def _sample_equity(self):
        eq = self.account()["equity"]
        now = time.time()
        if not self.equity_history or now - self.equity_history[-1][0] >= 60:
            self.equity_history.append((now, eq))
            self.equity_history = [e for e in self.equity_history if now - e[0] <= 86400 * 2]

    def reset(self, seed=False, reset_learning=False):
        with self._conn() as c:
            for t in ("trades", "events"):
                c.execute(f"DELETE FROM {t}")
            c.execute("UPDATE account SET balance=?, peak=?, started_at=? WHERE id=1",
                      (STARTING_BALANCE, STARTING_BALANCE, now_iso()))
            # seed hiqet plotësisht — kurrë tregti të sajuara (85% ishte fiktive)
        self.equity_history = []
        self.cooldown = {}
        if reset_learning:
            self.strategy_stats = {}
            self.learning_last_id = 0
            save_weights(self.strategy_stats)
            self._event("reset", "Peshat e mësuara të strategjive u rivendosën")
        else:
            self.learning_last_id = 0
        if seed:
            self._seed_equity()
        self._event("reset", "Llogaria u rivendos")

    def persist_learning(self):
        """Persist learning weights + last processed trade id."""
        stats = dict(self.strategy_stats)
        stats["__last_trade_id"] = self.learning_last_id
        save_weights(stats)

    def learning_status(self):
        """Rich learning view for the UI."""
        enriched = enrich(self.strategy_stats)
        by_weight = sorted(enriched.items(),
                           key=lambda kv: kv[1].get("weight", 1.0),
                           reverse=True)
        return {
            "strategies": dict(by_weight),
            "meta": self.meta_state,
            "history": self.learning_history[-120:],
            "trained": sum(1 for s in self.strategy_stats.values()
                           if s.get("trades", 0) > 0),
        }
# ============ main.py ============
"""
Waynis AI — paper trading bot. FastAPI server.

Serves the mobile-first dashboard (static/index.html) and a JSON/WS API.
"""
import asyncio
import json
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from providers import MarketData, WATCHLIST
from engine import PaperEngine, CYCLE_SECONDS
from config import FEE_RATE, SCAN_BATCH

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = BASE          # files live at project root (flat, phone-friendly deploy)

app = FastAPI(title="Waynis AI", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

market = MarketData()
engine = PaperEngine(market)

clients = set()


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup():
    app.state.task = asyncio.create_task(engine.run())
    # warm the ticker cache so the first page load is instant
    await asyncio.to_thread(_warmup)

def _warmup():
    import urllib.request
    try:
        urllib.request.urlopen(
            "https://www.okx.com/api/v5/market/tickers?instType=SPOT",
            timeout=8)
    except Exception:
        pass

def _serve_file(relpath: str, media_type: str):
    """Read a file from disk and return it as bytes (robust for all hosts,
    unlike FileResponse which can fail on some PaaS setups)."""
    from fastapi.responses import Response
    path = os.path.join(STATIC, relpath)
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return JSONResponse(
            {"error": f"Skedari '{relpath}' nuk u gjet (u provua: {path})"},
            status_code=404)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return Response(content=data, media_type=media_type,
                    headers={"Cache-Control": "no-cache"})


@app.get("/", include_in_schema=False)
async def index():
    return _serve_file("index.html", "text/html; charset=utf-8")


@app.get("/debug", include_in_schema=False)
async def debug():
    """Troubleshooting: where files live and what exists."""
    import glob
    cwd = os.getcwd()
    base = BASE
    here = [f for f in os.listdir(base) if os.path.isfile(os.path.join(base, f))]
    return {
        "cwd": cwd,
        "base": base,
        "files_in_base": here,
        "index_exists": os.path.exists(os.path.join(base, "index.html")),
    }


# Web app assets (flat layout — no /static subfolder needed)
for _name, _path, _mime in [("manifest.webmanifest", "manifest.webmanifest",
                             "application/manifest+json"),
                            ("sw.js", "sw.js", "application/javascript"),
                            ("icon-192.png", "icon-192.png", "image/png"),
                            ("icon-512.png", "icon-512.png", "image/png")]:
    @app.get("/" + _name, include_in_schema=False)
    async def _asset(path=_path, mime=_mime):
        return _serve_file(path, mime)

    # backwards-compatible aliases under /static/
    @app.get("/static/" + _name, include_in_schema=False)
    async def _asset_old(path=_path, mime=_mime):
        return _serve_file(path, mime)


# ---------------------------------------------------------------
# APK downloads + source code zip (for Render deployment)
# ---------------------------------------------------------------
def _find_file(name):
    """Look for a file in the project root or in /home/user."""
    for p in (os.path.join(BASE, name), os.path.join("/home/user", name)):
        if os.path.exists(p):
            return p
    return None


@app.get("/apk", include_in_schema=False)
async def download_apk():
    """Serve the Android APK with the correct MIME + download headers,
    so it downloads as a pristine binary (not mangled by any viewer)."""
    from fastapi.responses import StreamingResponse
    apk = _find_file("WaynisAI.apk")
    if not apk:
        return JSONResponse({"error": "APK nuk gjendet"}, status_code=404)
    with open(apk, "rb") as f:
        data = f.read()
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.android.package-archive",
        headers={
            "Content-Disposition": 'attachment; filename="WaynisAI.apk"',
            "Content-Length": str(len(data)),
            "Cache-Control": "no-store",
        })


@app.get("/apk.zip", include_in_schema=False)
async def download_apk_zip():
    """Serve the APK wrapped in a ZIP (more resilient to transfer
    mangling than a raw APK in some download flows)."""
    from fastapi.responses import StreamingResponse
    z = _find_file("WaynisAI-Instalo.zip")
    if not z:
        return JSONResponse({"error": "ZIP nuk gjendet"}, status_code=404)
    with open(z, "rb") as f:
        data = f.read()
    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="WaynisAI-Instalo.zip"',
            "Content-Length": str(len(data)),
            "Cache-Control": "no-store",
        })


@app.get("/code.zip", include_in_schema=False)
async def download_code():
    """Zip the whole deployable project (flat) for Render/GitHub upload.
    Built on the fly so it is always in sync with the current code."""
    import io
    import zipfile
    from fastapi.responses import StreamingResponse

    deploy_files = ["main.py", "engine.py", "agents.py", "brain.py",
                    "config.py", "providers.py", "requirements.txt",
                    "render.yaml", "README.md", "index.html",
                    "manifest.webmanifest", "sw.js",
                    "icon-192.png", "icon-512.png"]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in deploy_files:
            p = os.path.join(BASE, f)
            if os.path.isfile(p):
                z.write(p, f)
    data = buf.getvalue()
    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="WaynisAI-Kodi.zip"',
            "Content-Length": str(len(data)),
            "Cache-Control": "no-store",
        })


@app.get("/deploy.zip", include_in_schema=False)
async def download_deploy_zip():
    """Serve the easy-deploy package (single-file app) — no GitHub needed:
    Hugging Face Spaces or Glitch, just 2-3 files to upload."""
    from fastapi.responses import StreamingResponse
    z = _find_file("WaynisAI-DeployLehte.zip")
    if not z:
        return JSONResponse({"error": "ZIP nuk gjendet"}, status_code=404)
    with open(z, "rb") as f:
        data = f.read()
    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="WaynisAI-DeployLehte.zip"',
            "Content-Length": str(len(data)),
            "Cache-Control": "no-store",
        })


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    return {"ok": True, "t": engine.pipeline["cycles_run"]}


@app.get("/api/status")
async def status():
    acc = engine.account()
    stats = engine.stats()
    real = None
    if engine.mode == "real":
        try:
            real = engine.real_status()
        except Exception as e:
            real = {"error": str(e)[:120]}
    return {
        "account": acc,
        "stats": stats,
        "pipeline": engine.pipeline,
        "cycle_seconds": CYCLE_SECONDS,
        "auto_trade": engine.auto_trade,
        "compound": engine.compound,
        "compound_mult": engine.compound_mult,
        "mode": engine.mode,
        "real": real,
        "fee_rate": FEE_RATE,
        "lock": engine.lock_info(),
        "risk": engine.risk_info(),
        "fixed_risk": engine.fixed_risk_info(),
        "learning_ctrl": engine.learning_controls(),
        "dca": engine.dca_status(),
        "mtf_enabled": True,
        "session": {
            "started_at": engine.started_at,
            "scan_count": engine.scan_count,
            "watchlist_size": len(WATCHLIST),
            "scanned_per_cycle": SCAN_BATCH,
        },
        "ensemble": {"enabled": engine.variant_count > 0,
                     "variants": engine.variant_count,
                     "core_strategies": 16,
                     "total_strategies": engine.variant_count + 16},
        "turso": engine.turso_status(),
        "pyramid": engine.pyramid_summary(),
        "agents": engine.agents_info(),
        "ai": engine.brain.status(),
        "ai_last": engine.last_ai,
        "watchlist": [w[0] for w in WATCHLIST],
    }


@app.get("/api/tickers")
async def tickers():
    t = await market.fetch_all_tickers()
    return {"tickers": list(t.values())}


@app.get("/api/klines")
async def klines(symbol: str = "BTC-USDT", interval: str = "1m", limit: int = 150):
    sym = MarketData.okx_of(symbol)
    limit = max(30, min(500, int(limit)))
    data = await market.fetch_klines(sym, interval, limit)
    return {"symbol": sym, "interval": interval, "candles": data}


@app.get("/api/equity")
async def equity(limit: int = 400):
    return {"history": engine.equity_curve(limit)}


@app.get("/api/trades")
async def trades(limit: int = 60):
    return {"trades": engine.trades(limit)}


@app.get("/api/events")
async def events(limit: int = 40):
    return {"events": engine.recent_events(limit)}


@app.post("/api/cycle/run")
async def run_cycle():
    result = await engine.run_cycle_now()
    return {"ok": True, "pipeline": result}


@app.get("/api/ai/settings")
async def ai_settings_get():
    cfg = engine.brain.cfg
    return {"ok": True, "config": {
        k: cfg[k] for k in ("enabled", "provider", "model", "openai_model",
                            "base_url", "verdict_ttl")
    }, "has_key": bool(cfg.get("api_key")),
       "status": engine.brain.status()}


@app.post("/api/ai/settings")
async def ai_settings_set(body: dict):
    patch = {}
    for k in ("enabled", "provider", "model", "openai_model", "base_url",
              "api_key", "verdict_ttl"):
        if k in body:
            patch[k] = body[k]
    cfg = engine.brain.update_config(patch)
    engine._event("settings",
                  f"AI konfiguruar: {cfg.get('provider')} / {cfg.get('model')} "
                  f"{'AKTIV' if cfg.get('enabled') else 'OFF'}")
    return {"ok": True, "config": cfg, "status": engine.brain.status()}


@app.post("/api/settings")
async def set_settings(body: dict):
    if "auto_trade" in body:
        engine.auto_trade = bool(body["auto_trade"])
        engine._event("settings",
                      "Auto-trading " + ("ON" if engine.auto_trade else "OFF"))
    if "compound" in body:
        engine.compound = bool(body["compound"])
        engine._event("settings",
                      "Komponimi (compound) " +
                      ("AKTIV — pozicionet rriten me equity"
                       if engine.compound else
                       "OFF — madhësi fikse pozicionesh"))
    if "mode" in body:
        new_mode = engine.set_mode(str(body["mode"]))
        return {"ok": True, "mode": new_mode,
                "auto_trade": engine.auto_trade,
                "compound": engine.compound}
    if "compound_mult" in body:
        mult = engine.set_compound_mult(body["compound_mult"])
        return {"ok": True, "compound_mult": mult}
    if "threshold" in body or "learn_speed" in body:
        info = engine.set_learning(threshold=body.get("threshold"),
                                   speed=body.get("learn_speed"))
        return {"ok": True, "learning_ctrl": info}
    if any(k in body for k in ("fixed_risk_enabled", "fixed_entry_usd",
                               "fixed_max_loss_usd")):
        info = engine.set_fixed_risk(
            enabled=body.get("fixed_risk_enabled"),
            entry=body.get("fixed_entry_usd"),
            max_loss=body.get("fixed_max_loss_usd"))
        return {"ok": True, "fixed_risk": info}
    if "equity_lock_enabled" in body or "equity_lock_pct" in body:
        info = engine.set_equity_lock(
            enabled=body.get("equity_lock_enabled"),
            pct=body.get("equity_lock_pct"))
        return {"ok": True, "lock": info}
    return {"ok": True, "auto_trade": engine.auto_trade,
            "compound": engine.compound, "mode": engine.mode}


@app.post("/api/webhook/tradingview")
async def tradingview_webhook(body: dict = None):
    """Receives TradingView alerts (webhook) and turns them into trades.

    In TradingView (Premium) create an Alert → Webhook URL →
    paste this endpoint URL, and set the message (JSON):
      {"symbol":"BTCUSDT","side":"buy","price":0}
    side: buy/sell  (or long/short)
    """
    if body is None:
        body = {}
    symbol = str(body.get("symbol") or body.get("ticker") or "").upper()
    side = str(body.get("side") or body.get("action") or body.get("direction") or "").lower()
    price = float(body.get("price") or 0) or None

    # normalize symbol: BTCUSDT -> BTC-USDT
    if symbol and "-" not in symbol and symbol.endswith("USDT"):
        symbol = symbol[:-4] + "-USDT"
    # validate symbol is in watchlist
    ok_syms = {w[0] for w in WATCHLIST}
    if symbol not in ok_syms:
        return {"ok": False, "error": f"Simboli '{symbol}' nuk është në watchlist"}

    direction = None
    if side in ("buy", "long", "l"):
        direction = "LONG"
    elif side in ("sell", "short", "s"):
        direction = "SHORT"
    else:
        return {"ok": False, "error": f"Drejtimi '{side}' i panjohur (përdor buy/sell)"}

    # build a signal and execute through the same engine path
    import engine as eng
    sig = {"symbol": symbol, "direction": direction,
           "entry": price or (engine.last_tickers.get(symbol) or {}).get("price") or 0,
           "confidence": 80.0}
    # attach TP/SL (LONG: SL below; SHORT: SL above)
    if direction == "LONG":
        sig["tp"] = sig["entry"] * 1.0045
        sig["sl"] = sig["entry"] * 0.9965
    else:
        sig["tp"] = sig["entry"] * 0.9955
        sig["sl"] = sig["entry"] * 1.0035
    if not sig["entry"]:
        tickers = await market.fetch_all_tickers()
        engine.last_tickers = tickers
        sig["entry"] = (tickers.get(symbol) or {}).get("price") or 0
    if not sig["entry"]:
        return {"ok": False, "error": "Nuk u gjet çmimi"}

    qty = 0.0
    if engine.fixed_risk_enabled:
        notional = engine.fixed_entry_usd
        sl_pct = 0.0035
        qty = min(notional / sig["entry"],
                  engine.fixed_max_loss_usd / (sig["entry"] * sl_pct))
    else:
        qty = (engine.account()["equity"] * 0.35) / sig["entry"]

    if qty <= 0:
        return {"ok": False, "error": "Madhësi zero"}

    if engine.mode == "real" and engine.exchange.configured:
        tid = await engine.real_open(sig, qty)
    else:
        tid = engine._open_trade(sig, qty, votes=["TradingView"])
        if tid:
            engine._event("tv",
                          f"📡 TradingView: {direction} {symbol} "
                          f"{qty:.6f} @ {sig['entry']:.6g}",
                          symbol)

    engine._event("settings",
                  f"📡 TradingView sinjal: {direction} {symbol}")
    return {"ok": True, "trade_id": tid, "symbol": symbol,
            "direction": direction, "qty": round(qty, 6),
            "entry": sig["entry"], "mode": engine.mode}


@app.get("/api/webhook/info")
async def webhook_info():
    """Instructions + the webhook URL to paste into TradingView."""
    return {"ok": True,
            "webhook_url": f"https://waynis-ai-1.onrender.com/api/webhook/tradingview",
            "example": '{"symbol":"BTCUSDT","side":"buy"}',
            "note": "Vendos URL-në te TradingView → Alert → Webhook URL"}


@app.get("/api/learning")
async def learning():
    return {"ok": True, "learning": engine.learning_status()}


@app.post("/api/backtest/run")
async def backtest_run(symbols: str = "BTC-USDT,ETH-USDT,SOL-USDT,BNB-USDT,XRP-USDT,DOGE-USDT,ADA-USDT,AVAX-USDT,SUI-USDT,DOGE-USDT"):
    """Run the 20-agent strategy over ~40 days of 1h historical data
    with real fees. Returns the honest backtest report."""
    import backtest as bt
    syms = [s.strip() for s in symbols.split(",") if s.strip()]
    results = []
    for sym in dict.fromkeys(syms):
        try:
            candles = await market.fetch_klines_history(sym, "1h", 900)
            if len(candles) < 80:
                continue
            trades, pnl, dd = await asyncio.to_thread(
                bt.backtest_symbol, sym, candles)
            results.append((sym, trades, pnl, dd))
        except Exception:
            continue
    report = bt.summarize(results)
    engine._event("backtest",
                  f"🧪 Backtest: {report['trades']} tregti, win rate "
                  f"{report['win_rate']}%, PnL {report['total_pnl']:+.2f} USDT, "
                  f"R:R {report['rr']}, drawdown {report['max_drawdown_pct']}%")
    return {"ok": True, "report": report}


@app.get("/api/dca")
async def dca_status():
    return {"ok": True, "dca": engine.dca_status()}


@app.get("/api/dca/backtest")
async def dca_backtest(symbol: str = "BTC-USDT", amount: float = 5.0,
                       interval_days: float = 1.0, days: int = 365):
    r = await engine.dca_backtest(symbol, amount, interval_days, days)
    return {"ok": True, "result": r}


@app.post("/api/dca/settings")
async def dca_settings(body: dict):
    info = engine.dca_set(
        enabled=body.get("enabled"),
        amount=body.get("amount"),
        interval=body.get("interval_min"),
        symbol=body.get("symbol"))
    return {"ok": True, "dca": info}


@app.get("/api/real/status")
async def real_status():
    try:
        return {"ok": True, "real": engine.real_status()}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


@app.post("/api/reset")
async def reset(seed: bool = False):
    """Rivendos llogarinë nga e para.
    seed=true → mbjell demen e bukur (85%, Sot +52 — numra JO-realë, të
    shënuar si demo). seed=false → $10,000 i pastër pa asnjë tregti."""
    engine.reset(seed=seed)
    # pastro edhe cloud-in që historia e vjetër të mos rikthehet
    try:
        engine._turso_push_snapshot()
    except Exception:
        pass
    return {"ok": True, "balance": engine.account()["balance"],
            "demo": bool(seed)}


# ---------------------------------------------------------------------------
# WebSocket live feed
# ---------------------------------------------------------------------------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=0.5)
                if msg == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                pass
            except Exception:
                break

            tickers_data = await market.fetch_all_tickers()
            acc = engine.account()
            stats = engine.stats()
            payload = {
                "type": "tick",
                "tickers": [v for v in tickers_data.values()],
                "account": acc,
                "stats": stats,
                "pipeline": engine.pipeline,
            }
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                break
            await asyncio.sleep(CYCLE_SECONDS)
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(ws)


# ---------------------------------------------------------------------------
# Entry point — PORT comes from the environment (Render sets it);
# default 7860 = Hugging Face Spaces Docker port.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "7860"))
    uvicorn.run(app, host="0.0.0.0", port=port)
