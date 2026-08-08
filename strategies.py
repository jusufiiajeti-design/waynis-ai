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
