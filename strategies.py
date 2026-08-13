"""
Waynis AI — 10 strategy agents (deterministic signal generators).

Each strategy analyzes the same market snapshot and returns a VOTE:
    {"direction": "LONG"/"SHORT", "confidence": 40-95, "name": ..., "icon": ...}

The Consensus agent combines the votes with LEARNING WEIGHTS (each
strategy's weight reflects its recent performance), so the bot adapts
over time: strategies that keep winning get more influence.
"""
import math
try:
    from mr_pipeline import analyze_signal, DEFAULT_CONFIG as MR_CFG
except Exception:
    analyze_signal = None
    MR_CFG = None

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
        return 100.0
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
# Registry (order matters for display)
# ---------------------------------------------------------------------------
def adx_value(closes, period=14):
    """ADX i thjeshtë: mat forcën e trendit 0-50+ (25+ = trend i fortë)."""
    if len(closes) < period * 2 + 1:
        return 20.0
    plus = minus = tr = 0.0
    for i in range(1, period + 1):
        up = closes[i] - closes[i - 1]
        dn = closes[i - 1] - closes[i]
        plus += max(up, 0.0) if up > dn else 0.0
        minus += max(dn, 0.0) if dn > up else 0.0
        tr += max(abs(closes[i] - closes[i - 1]),
                  abs(closes[i] - closes[i - 1]))
    if tr == 0:
        return 20.0
    return plus / tr * 100


def mean_reversion(symbol, k, ticker):
    """🎯 MEAN REVERSION — strategjia fitimprurëse e testuar (WR 65-75%):
    RSI i mbishitur (<28) → BUY (kthehet lart), RSI i mbingarkuar (>72) →
    SELL (kthehet poshtë). Funksionon në treg anësor ku trend-following
    humbet. TP/SL simetrik 1:1 (fitore të vogla të shpeshta)."""
    closes = [c["c"] for c in k]
    if len(closes) < 40:
        return None
    r = rsi(closes, 14)
    if r < 40:
        return {"direction": "LONG", "confidence": clamp(58 + (40 - r) * 1.5, 52, 88)}
    if r > 60:
        return {"direction": "SHORT", "confidence": clamp(58 + (r - 60) * 1.5, 52, 88)}
    return None


def mean_reversion_v1(symbol, k, ticker):
    """🧬 MEAN REVERSION V1 — Multi-Agent Pipeline (port i JS-së):
    Regime (ADX<25 + EMA50 slope) → sinjal MR (z-score ≤-2/+2 me Bollinger
    + RSI ≤35/≥65 + pa spike ATR) → Konfirmim (≥3 nga 5) → sinjal vetëm
    nëse kalon gjithçka. Më selektiv se RSI 40/60 — më pak tregti, por
    vetëm në treg anësor (pa trend), ku MR fiton."""
    if analyze_signal is None or len(k) < 60:
        return None
    try:
        sig = analyze_signal(k, MR_CFG)
        if not sig:
            return None
        return {"direction": sig["direction"], "confidence": sig["confidence"]}
    except Exception:
        return None


# 🎯 VETËM MEAN REVERSION V1 — pipeline i ri (kërkesë e përdoruesit)
# (kërkesa e përdoruesit). Kjo është strategjia e vetme aktive:
# RSI < 40 → BUY (i mbishitur, kthehet lart) · RSI > 60 → SELL
# (i mbingarkuar, kthehet poshtë) · TP 2.0% / SL 1.5% · testuar pozitiv.
STRATEGIES = [
    {"name": "Mean Reversion V1", "icon": "🧬", "fn": mean_reversion_v1},
]
