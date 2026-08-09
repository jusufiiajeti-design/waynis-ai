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
