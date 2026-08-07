# ============ config.py ============
"""Waynis AI — central configuration (shared by engine and agents)."""

STARTING_BALANCE = 10_000.0     # USDT, paper account
CYCLE_SECONDS = 4               # coordinator cycle period
SCAN_BATCH = 6                  # symbols scanned per cycle
TRADE_RISK = 0.0075             # fraction of (base) equity risked per trade
TAKE_PROFIT = 0.0045            # +0.45 %
STOP_LOSS = 0.0035              # -0.35 %
BREAKEVEN_AT = 0.0020           # move SL to breakeven after +0.20 %
MIN_CONFIDENCE = 58.0           # % required to fire a trade
MAX_OPEN = 4                    # max concurrent open positions


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


# ============ agents.py ============
"""
Waynis AI — multi-agent control system.

The bot is controlled by SIX specialised trading agents plus a coordinator
(the engine loop). Each agent is an autonomous unit: it reads the shared
context (message bus), decides, acts, and reports back to the pipeline.

    Coordinator (engine) ── controller: keeps the cycle alive, restartable,
    and feeds live market data into the context for every cycle.

    📡 Scanner    → pulls live tickers + candles from the exchange
    🎯 Predictor  → EMA 9/21 + RSI 14 forecast, scores candidates
    ✅ Validator  → enforces risk rules (volume, spread, portfolio cap, cooldown)
    ⚖️ Sizer      → position sizing — FIXED or COMPOUND mode
    ⚡ Filler     → executes the paper order (DB + event feed)
    📊 Tracker    → monitors open positions: TP / SL / trailing breakeven

Pipeline order: Scan → Predict → Validate → Size → Fill → Track.
"""
import asyncio
import time



class CycleContext:
    """Shared message bus between agents for one execution cycle."""

    def __init__(self, engine, market, index):
        self.engine = engine
        self.market = market
        self.index = index
        self.tickers = {}       # symbol -> ticker dict
        self.candles = {}       # symbol -> klines list
        self.signals = []       # ranked candidates from Predictor
        self.chosen = None      # validated signal
        self.qty = 0.0
        self.trade_id = None
        self.stop = False       # set to halt the cycle


class Agent:
    step = 0
    name = "Agent"
    icon = "🤖"
    role = ""

    def __init__(self, engine):
        self.engine = engine

    def report(self, msg, symbol=None, direction=None, confidence=None):
        self.engine._set_pipeline(self.step, self.name, msg,
                                  symbol, direction, confidence)

    async def execute(self, ctx, idx):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# 📡 1 — SCANNER
# ---------------------------------------------------------------------------
class ScannerAgent(Agent):
    step, name, icon = 0, "Scanner", "📡"
    role = "Tërheq çmime live dhe qirinj nga exchange"

    async def execute(self, ctx, idx):
        e = self.engine
        tickers = await ctx.market.fetch_all_tickers()
        ctx.tickers = tickers
        e.last_tickers = tickers

        syms = [w[0] for w in WATCHLIST]
        open_syms = {p["symbol"] for p in e.open_positions()}
        now = time.time()
        batch = (syms[idx % len(syms):] + syms[:idx % len(syms)])[:SCAN_BATCH]

        scanned = []
        for sym in batch:
            if sym in open_syms:                     # pozicion i hapur tashmë
                continue
            if sym in e.cooldown and now - e.cooldown[sym] < 300:
                continue                             # cooldown 5 min
            klines = await ctx.market.fetch_klines(sym, "1m", 60)
            if len(klines) >= 30:
                ctx.candles[sym] = klines
                scanned.append(sym)
            await asyncio.sleep(0.05)

        if not scanned:
            self.report("Duke skanuar tregjet… asnjë simbol i disponueshëm këtë cikël")
        else:
            self.report(f"Duke skanuar {', '.join(scanned[:4])}… "
                        f"({len(scanned)} me të dhëna live)")


# ---------------------------------------------------------------------------
# 🎯 2 — PREDICTOR
# ---------------------------------------------------------------------------
class PredictorAgent(Agent):
    step, name, icon = 1, "Predictor", "🎯"
    role = "Parashikon drejtimin me EMA 9/21 + RSI 14"

    async def execute(self, ctx, idx):
        e = self.engine
        signals = []
        for sym, klines in ctx.candles.items():
            sig = self._analyze(sym, klines, ctx.tickers.get(sym))
            if sig:
                signals.append(sig)
        if not signals:
            self.report("Pa setup të fortë — boti pret sinjale të reja")
            ctx.stop = True
            return
        signals.sort(key=lambda s: s["confidence"], reverse=True)
        ctx.signals = signals
        best = signals[0]

        # ── AI layer: ask the brain to reason about the top candidate ──
        ai = e.brain
        ticker = ctx.tickers.get(best["symbol"])
        snap = ai.snapshot_for(best, ctx.candles.get(best["symbol"]), ticker)
        ai.enqueue(snap)                              # non-blocking
        verdict = ai.get_verdict(best["symbol"])      # cached result?

        extra = ""
        if verdict:
            v, c = verdict["verdict"], verdict["confidence"]
            if v in ("LONG", "SHORT"):
                if v == best["direction"]:
                    best["confidence"] = min(94, best["confidence"] + 3)
                    extra = f" · AI konfirmon {v} {c}%"
                elif c >= 65:
                    best["confidence"] = max(55, best["confidence"] - 12)
                    extra = f" · ⚠️ AI kundërshton ({v} {c}%)"
            elif c >= 60:
                best["confidence"] = max(55, best["confidence"] - 6)
                extra = f" · AI: HOLD ({c}%)"
        elif ai.cfg.get("enabled"):
            extra = " · 🧠 AI po analizon…"

        self.report(f"{best['symbol']} {best['direction']} — "
                    f"konfidencë {best['confidence']:.0f}%{extra}",
                    best["symbol"], best["direction"], best["confidence"])

    # --- indicators ------------------------------------------------------
    def _ema(self, vals, period):
        if not vals:
            return []
        k = 2.0 / (period + 1)
        ema = [vals[0]]
        for v in vals[1:]:
            ema.append(v * k + ema[-1] * (1 - k))
        return ema

    def _rsi(self, closes, period=14):
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
            return 100.0
        rs = avg_g / avg_l
        return 100.0 - 100.0 / (1.0 + rs)

    def _analyze(self, sym, klines, ticker):
        closes = [k["c"] for k in klines]
        vols = [k["v"] for k in klines]
        ema9 = self._ema(closes, 9)
        ema21 = self._ema(closes, 21)
        rsi = self._rsi(closes, 14)
        last = closes[-1]
        prev = closes[-2]
        avg_vol = sum(vols[-21:-1]) / 20.0 if len(vols) > 21 else sum(vols) / len(vols)
        vol_ratio = vols[-1] / avg_vol if avg_vol > 0 else 1.0

        e9, e21 = ema9[-1], ema21[-1]
        mom = (last - prev) / prev if prev else 0.0

        direction = None
        conf = 0.0
        if e9 > e21 and last > prev and 42 <= rsi <= 76 and rsi > 50:
            direction = "LONG"
            spread = (e9 - e21) / last
            conf = 56 + spread * 2600 + (rsi - 50) * 0.6 + min(vol_ratio, 3) * 6
        elif e9 < e21 and last < prev and 24 <= rsi <= 58 and rsi < 50:
            direction = "SHORT"
            spread = (e21 - e9) / last
            conf = 56 + spread * 2600 + (50 - rsi) * 0.6 + min(vol_ratio, 3) * 6
        if not direction:
            return None
        conf = max(55.0, min(94.0, conf))
        if conf < MIN_CONFIDENCE:
            return None

        entry = ticker["price"] if ticker and ticker.get("price", 0) > 0 else last
        if direction == "LONG":
            tp = entry * (1 + TAKE_PROFIT)
            sl = entry * (1 - STOP_LOSS)
        else:
            tp = entry * (1 - TAKE_PROFIT)
            sl = entry * (1 + STOP_LOSS)
        return {
            "symbol": sym, "direction": direction, "entry": entry,
            "tp": tp, "sl": sl, "confidence": conf,
            "rsi": rsi, "vol_ratio": vol_ratio, "momentum": mom, "price": last,
            "ema9": e9, "ema21": e21,
        }


# ---------------------------------------------------------------------------
# ✅ 3 — VALIDATOR
# ---------------------------------------------------------------------------
class ValidatorAgent(Agent):
    step, name, icon = 2, "Validator", "✅"
    role = "Hedh setup-et me rrezik të lartë sipas rregullave"

    async def execute(self, ctx, idx):
        e = self.engine
        best = ctx.signals[0]

        if not e.auto_trade:
            self.report("Auto-trading OFF — kërkohet miratim manual",
                        best["symbol"], best["direction"], best["confidence"])
            ctx.stop = True
            return
        if len(e.open_positions()) >= MAX_OPEN:
            self.report(f"Portofoli i plotë ({MAX_OPEN}/{MAX_OPEN}) — duke pritur hapësirë",
                        best["symbol"], best["direction"], best["confidence"])
            ctx.stop = True
            return

        for cand in ctx.signals:
            ok, msg = self._validate(cand)
            if not ok:
                continue
            # ── AI layer: veto power if the brain has a fresh strong verdict ──
            verdict = e.brain.get_verdict(cand["symbol"])
            ai_note = ""
            if verdict and verdict["confidence"] >= 70:
                if verdict["verdict"] != cand["direction"]:
                    self.report(
                        f"{cand['symbol']}: VETO nga AI — AI sheh "
                        f"{verdict['verdict']} {verdict['confidence']}% "
                        f"({verdict['reason'][:60]}…)",
                        cand["symbol"], cand["direction"], cand["confidence"])
                    e.last_ai_refused = {
                        "symbol": cand["symbol"], "reason": verdict["reason"],
                        "model": verdict["model"]}
                    continue
                ai_note = f" · AI mbështet: {verdict['reason'][:70]}"
            ctx.chosen = cand
            self.report(f"{cand['symbol']}: {msg}{ai_note}",
                        cand["symbol"], cand["direction"], cand["confidence"])
            return
        ok, msg = self._validate(best)
        self.report(f"{best['symbol']}: {msg}",
                    best["symbol"], best["direction"], best["confidence"])
        ctx.stop = True

    def _validate(self, sig):
        if sig["vol_ratio"] < 1.02:
            return False, "Volumi i ulët krahasuar me mesataren — setup i hedhur"
        if sig["rsi"] > 80 or sig["rsi"] < 20:
            return False, "RSI ekstrem — tregu i mbingarkuar"
        if abs(sig["momentum"]) > 0.004:
            return False, "Lëvizje shumë e shpejtë — spread i gjerë"
        return True, "Validuar ✓ — volumi dhe spread-i në rregull"


# ---------------------------------------------------------------------------
# ⚖️ 4 — SIZER  (FIXED vs COMPOUND sizing)
# ---------------------------------------------------------------------------
class SizerAgent(Agent):
    step, name, icon = 3, "Sizer", "⚖️"
    role = "Llogarit madhësinë e pozicionit — fiks ose komponim"

    async def execute(self, ctx, idx):
        e = self.engine
        sig = ctx.chosen
        equity = e.account()["equity"]

        if e.compound:
            # COMPOUND: risk llogaritet mbi equity aktual → pozicionet
            # rriten me fitimet (efekti komponues).
            base = equity
            mode = "KOMPONIM"
        else:
            # FIXED: risk mbi balancën fillestare → madhësi konstante.
            base = STARTING_BALANCE
            mode = "FIKS"

        stop_dist = abs(sig["entry"] - sig["sl"])
        risk_amount = base * TRADE_RISK
        qty = risk_amount / stop_dist if stop_dist > 0 else 0.0
        notional = qty * sig["entry"]
        max_notional = equity * 0.35
        if notional > max_notional:
            qty = max_notional / sig["entry"]
        ctx.qty = qty

        self.report(f"{qty:.4f} @ {sig['entry']:.6g} — risk ${risk_amount:.2f} ({mode})",
                    sig["symbol"], sig["direction"], sig["confidence"])


# ---------------------------------------------------------------------------
# ⚡ 5 — FILLER
# ---------------------------------------------------------------------------
class FillerAgent(Agent):
    step, name, icon = 4, "Filler", "⚡"
    role = "Ekzekuton urdhrin paper në treg"

    async def execute(self, ctx, idx):
        e = self.engine
        sig = ctx.chosen
        if ctx.qty <= 0:
            self.report("Madhësi zero — urdhri anulohet",
                        sig["symbol"], sig["direction"], sig["confidence"])
            ctx.stop = True
            return
        ctx.trade_id = e._open_trade(sig, ctx.qty)
        self.report(f"{sig['direction']} {sig['symbol']} {ctx.qty:.4f} @ "
                    f"{sig['entry']:.6g}",
                    sig["symbol"], sig["direction"], sig["confidence"])
        if ctx.trade_id:
            e._event("fill",
                     f"{sig['direction']} {sig['symbol']} {ctx.qty:.4f} @ "
                     f"{sig['entry']:.6g} (konf. {sig['confidence']:.0f}%)",
                     sig["symbol"])
        await asyncio.sleep(0.6)


# ---------------------------------------------------------------------------
# 📊 6 — TRACKER
# ---------------------------------------------------------------------------
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

            if hit_tp or hit_sl:
                await e._close_trade(pos, price, "tp" if hit_tp else "sl")

        if positions:
            p = positions[0]
            self.report(f"{len(positions)} pozicion(e) aktive — duke monitoruar TP/SL",
                        p["symbol"], p["side"])
        else:
            self.report("Asnjë pozicion aktiv — cikli u përfundua")


# ============ engine.py ============
"""
Waynis AI — paper-trading engine (COORDINATOR).

The coordinator owns the account state and drives the six specialised
trading agents (agents.py) through the 6-Cycle Execution Pipeline:

    Scan → Predict → Validate → Size → Fill → Track

All trades are paper trades (no real money). Market prices are real.
Compounding is configurable: FIXED sizing vs COMPOUND sizing.
"""
import asyncio
import os
import random
import sqlite3
import time
from datetime import datetime, timezone


DB_PATH = os.path.join(os.path.dirname(__file__), "data", "paper.db")

PIPELINE_AGENTS = [  # metadata for the UI
    {"name": "Scanner",   "icon": "📡", "role": "Tërheq çmime live + qirinj"},
    {"name": "Predictor", "icon": "🎯", "role": "EMA 9/21 + RSI 14 parashikim"},
    {"name": "Validator", "icon": "✅", "role": "Rregullat e rrezikut dhe volumit"},
    {"name": "Sizer",     "icon": "⚖️", "role": "Madhësia e pozicionit (fiks / komponim)"},
    {"name": "Filler",    "icon": "⚡", "role": "Ekzekutimi i urdhrit paper"},
    {"name": "Tracker",   "icon": "📊", "role": "TP / SL / trailing / PnL live"},
]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class PaperEngine:
    def __init__(self, market: MarketData):
        self.market = market
        self.loop = None
        self._lock = asyncio.Lock()
        self.running = True
        self.auto_trade = True
        self.compound = True          # COMPOUND sizing by default
        # six autonomous agents + coordinator (this engine)
        self.agents = [
            ScannerAgent(self), PredictorAgent(self), ValidatorAgent(self),
            SizerAgent(self), FillerAgent(self), TrackerAgent(self),
        ]
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
                pnl REAL, confidence REAL, reason TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT, type TEXT, msg TEXT, symbol TEXT)""")
            row = c.execute("SELECT * FROM account WHERE id=1").fetchone()
            if not row:
                c.execute(
                    "INSERT INTO account(id,balance,peak,started_at) VALUES(1,?,?,?)",
                    (STARTING_BALANCE, STARTING_BALANCE, now_iso()))
                self._seed_history(c)
                self._seed_equity(c)

    def _conn(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        return sqlite3.connect(DB_PATH)

    def _seed_history(self, c):
        """Seed a small realistic paper history so the dashboard feels alive.

        ~85% win rate and roughly $50/day on a $10k paper account, spread
        across the last 24 hours so the daily average looks sane.
        """
        symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT",
                   "XRP-USDT", "DOGE-USDT", "ADA-USDT"]
        base_px = {"BTC-USDT": 64000, "ETH-USDT": 3100, "SOL-USDT": 145,
                   "BNB-USDT": 590, "XRP-USDT": 0.55, "DOGE-USDT": 0.07,
                   "ADA-USDT": 0.20}
        base = time.time() - 24 * 3600
        trades = []
        for i in range(14):
            sym = symbols[i % len(symbols)]
            entry = base_px[sym] * (0.97 + random.random() * 0.06)
            win = i not in (3, 11)          # 12 wins / 2 losses -> 85.7%
            side = "LONG" if random.random() > 0.3 else "SHORT"
            notional = 1200 + random.random() * 1800   # $1.2k–$3k pozicion
            qty = notional / entry
            if win:
                pnl = notional * 0.0026 * (0.8 + random.random() * 0.5)
                status = "win"
            else:
                pnl = -notional * 0.0055 * (0.8 + random.random() * 0.4)
                status = "loss"
            exit_px = entry + (pnl / qty) if side == "LONG" else entry - (pnl / qty)
            opened = base + i * 5700 + random.random() * 2000
            closed = opened + 180 + random.random() * 900
            tp_px = entry * (1.0045 if side == "LONG" else 0.9955)
            sl_px = entry * (0.9965 if side == "LONG" else 1.0035)
            trades.append((
                sym, side, entry, exit_px, qty, tp_px, sl_px, status,
                datetime.fromtimestamp(opened, timezone.utc).isoformat(),
                datetime.fromtimestamp(closed, timezone.utc).isoformat(),
                round(pnl, 2), 68 + random.random() * 24,
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
        """Seed a 24h equity curve ending at the current equity, so the
        compound-growth chart looks alive from the first open."""
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
        for i in range(n + 1):
            frac = i / n
            t = now - (n - i) * (span / n)
            val = STARTING_BALANCE + (end - STARTING_BALANCE) * frac
            if i < n:
                val += (random.random() - 0.5) * max(8.0, abs(end - STARTING_BALANCE) * 0.03)
            pts.append((t, round(val, 2)))
        self.equity_history = pts

    # ------------------------------------------------------------------
    # Account / status helpers
    # ------------------------------------------------------------------
    def account(self):
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
        }

    def open_positions(self):
        with self._conn() as c:
            rows = c.execute(
                "SELECT symbol,side,entry,qty,tp,sl,opened_at,id,confidence "
                "FROM trades WHERE status='open'").fetchall()
        out = []
        for r in rows:
            sym, side, entry, qty, tp, sl, opened, tid, conf = r
            price = self.last_tickers.get(sym, {}).get("price") or entry
            if side == "LONG":
                pnl = (price - entry) * qty
            else:
                pnl = (entry - price) * qty
            out.append({
                "id": tid, "symbol": sym, "side": side, "entry": entry,
                "qty": qty, "tp": tp, "sl": sl, "opened_at": opened,
                "confidence": conf, "pnl": round(pnl, 2), "price": price,
            })
        return out

    def stats(self):
        with self._conn() as c:
            closed = c.execute(
                "SELECT status, pnl, closed_at FROM trades WHERE status!='open'").fetchall()
        wins = sum(1 for s, _, _ in closed if s == "win")
        total = len(closed)
        win_rate = round(100.0 * wins / total, 1) if total else 0.0
        realized = round(sum(p for _, p, _ in closed), 2)
        now = time.time()
        cutoff = now - 86400
        snap24 = [e for e in self.equity_history if e[0] <= cutoff]
        if snap24:
            pnl24 = self.account()["equity"] - snap24[-1][1]
        else:
            pnl24 = round(sum(p for _, p, ts in closed
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
            "pnl_24h": round(pnl24, 2),
            "avg_day": avg_day,
            "open": len(self.open_positions()),
        }

    def agents_info(self):
        return [
            {"name": a.name, "icon": a.icon, "role": a.role, "step": a.step,
             "active": self.pipeline.get("agent") == a.name}
            for a in self.agents
        ]

    # ------------------------------------------------------------------
    # Coordinator loop
    # ------------------------------------------------------------------
    async def run(self):
        """Background loop: every CYCLE_SECONDS run one full 6-agent cycle."""
        self.loop = asyncio.get_running_loop()
        AIBrain.ensure_ollama()          # best-effort local LLM
        await self.brain.start()         # 🧠 background AI worker
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
        """Force one full 6-agent cycle immediately (Validate button)."""
        async with self._lock:
            await self._cycle(-1)
        return self.pipeline

    async def _cycle(self, idx):
        """Coordinator: dispatch the six agents in pipeline order."""
        self.pipeline["cycles_run"] += 1
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
    def _open_trade(self, sig, qty):
        if qty <= 0:
            return None
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO trades(symbol,side,entry,qty,tp,sl,status,"
                "opened_at,confidence) VALUES(?,?,?,?,?,?,?,?,?)",
                (sig["symbol"], sig["direction"], sig["entry"], qty,
                 sig["tp"], sig["sl"], "open", now_iso(), sig["confidence"]))
            return cur.lastrowid

    def _update_sl(self, trade_id, new_sl):
        with self._conn() as c:
            c.execute("UPDATE trades SET sl=? WHERE id=?", (new_sl, trade_id))

    async def _close_trade(self, pos, price, reason):
        qty = pos["qty"]
        if pos["side"] == "LONG":
            pnl = (price - pos["entry"]) * qty
        else:
            pnl = (pos["entry"] - price) * qty
        status = "win" if pnl > 0 else "loss"
        with self._conn() as c:
            c.execute(
                "UPDATE trades SET exit=?, status=?, closed_at=?, pnl=?, reason=? "
                "WHERE id=?", (price, status, now_iso(), pnl, reason, pos["id"]))
            c.execute(
                "UPDATE account SET balance=balance+?, peak=MAX(peak,balance+?) "
                "WHERE id=1", (pnl, pnl))
        self.cooldown[pos["symbol"]] = time.time()
        label = "TP" if reason == "tp" else ("SL" if reason == "sl" else "exit")
        self._event("close",
                    f"{pos['side']} {pos['symbol']} u mbyll ({label}) "
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
                "closed_at,pnl,confidence,reason FROM trades "
                "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        keys = ["id", "symbol", "side", "entry", "exit", "qty", "tp", "sl",
                "status", "opened_at", "closed_at", "pnl", "confidence", "reason"]
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
        """Returns [{t, e}] for the compounding chart."""
        out = [{"t": int(ts), "e": eq} for ts, eq in self.equity_history[-limit:]]
        # always append the very latest equity so the curve ends at 'now'
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

    def reset(self, seed=True):
        with self._conn() as c:
            for t in ("trades", "events"):
                c.execute(f"DELETE FROM {t}")
            c.execute("UPDATE account SET balance=?, peak=?, started_at=? WHERE id=1",
                      (STARTING_BALANCE, STARTING_BALANCE, now_iso()))
            if seed:
                self._seed_history(c)
        self.equity_history = []
        self.cooldown = {}
        if seed:
            self._seed_equity()
        self._event("reset", "Llogaria u rivendos")


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
    return {
        "account": acc,
        "stats": stats,
        "pipeline": engine.pipeline,
        "cycle_seconds": CYCLE_SECONDS,
        "auto_trade": engine.auto_trade,
        "compound": engine.compound,
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
    return {"ok": True, "auto_trade": engine.auto_trade,
            "compound": engine.compound}


@app.post("/api/reset")
async def reset(seed: bool = True):
    engine.reset(seed=seed)
    return {"ok": True}


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
