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
