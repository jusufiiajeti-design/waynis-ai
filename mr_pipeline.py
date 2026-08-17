"""
Mean Reversion Multi-Agent Pipeline — V1 (port Python)
======================================================
Port besnik i meanReversionAgents.js për Waynis AI (boti Python).

6 agjentë: Regime -> MeanReversion -> Confirmation -> Risk+Defense
           -> Portfolio -> Execution

Përdoret nga:
  • strategies.mean_reversion_v1  — sinjali i tregtisë (direction + confidence)
  • mr_pipeline.analyze          — pipeline i plotë (për test/debug)
  • mr_pipeline.DefenseAgent     — makina mbrojtëse NORMAL/CAUTION/DEFENSE/RECOVERY/KILL_SWITCH
"""

import math

# ----------------------------------------------------------------------
# CONFIG (identike me defaultConfig të JS-së)
# ----------------------------------------------------------------------

DEFAULT_CONFIG = {
    # Regime
    "adxPeriod": 14,
    "adxTrendThreshold": 999.0,  # 🏆 SWEEP: ADX-i e dëmtonte (WR 14→62%) — tani OFF
    "emaFast": 50,
    "emaSlow": 200,
    "emaSlopeMaxPct": 0.05,
    # Mean reversion
    "bbPeriod": 20,
    "bbStdDev": 2.0,
    "zscorePeriod": 20,
    "rsiPeriod": 14,
    "rsiLongMax": 38.0,          # 🏆 SWEEP: RSI 38/62 fituesi (WR 62%)
    "rsiShortMin": 62.0,         # 🏆 SWEEP
    "atrPeriod": 14,
    "atrSpikeMult": 2.0,         # akorduar nga 1.5 (më pak refuzime nga spike)
    # Confirmation
    "confirmationMinNormal": 1,  # ⚡ TREGTIM MENJËHERË: mjafton 1 konfirmim
    "confirmationMinCaution": 2,
    # Risk
    "riskPctNormal": 0.0025,
    "riskPctCaution": 0.0010,
    "slAtrMult": 1.0,
    "tpAtrMult": 1.3,
    # Defense state machine
    "lossesToCaution": 2,
    "lossesToDefense": 3,
    "recoveryWaitCandles": 240,
    "dailyDrawdownStopPct": 0.015,
    "killSwitchDrawdownPct": 0.08,
    # Portfolio
    "maxOpenTrades": 2,
    # Capital
    "startingCapital": 50,
    "takerFeePct": 0.001,
}

# ----------------------------------------------------------------------
# INDICATORS — seri (e fundit = candle aktual), asnjë varësi e jashtme
# ----------------------------------------------------------------------

def _ema(values, period):
    k = 2.0 / (period + 1)
    out = [None] * len(values)
    prev = values[0]
    out[0] = prev
    for i in range(1, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def _sma(values, period):
    out = [None] * len(values)
    s = 0.0
    for i in range(len(values)):
        s += values[i]
        if i >= period:
            s -= values[i - period]
        if i >= period - 1:
            out[i] = s / period
    return out


def _stddev(values, period, means):
    out = [None] * len(values)
    for i in range(period - 1, len(values)):
        m = means[i]
        if m is None:
            continue
        ss = 0.0
        for j in range(i - period + 1, i + 1):
            ss += (values[j] - m) ** 2
        out[i] = math.sqrt(ss / period)
    return out


def _rsi_series(closes, period):
    out = [50.0] * len(closes)
    avg_g = avg_l = 0.0
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        g = max(d, 0.0)
        l = max(-d, 0.0)
        if i <= period:
            avg_g += g / period
            avg_l += l / period
            out[i] = 50.0
        else:
            avg_g = (avg_g * (period - 1) + g) / period
            avg_l = (avg_l * (period - 1) + l) / period
            rs = 100.0 if avg_l == 0 else avg_g / avg_l
            out[i] = 100.0 if avg_l == 0 else 100.0 - 100.0 / (1.0 + rs)
    return out


def _true_range(candles):
    out = [0.0] * len(candles)
    for i in range(len(candles)):
        hi, lo = candles[i]["h"], candles[i]["l"]
        if i == 0:
            out[i] = hi - lo
        else:
            pc = candles[i - 1]["c"]
            out[i] = max(hi - lo, abs(hi - pc), abs(lo - pc))
    return out


def _atr_series(candles, period):
    return _ema(_true_range(candles), period)


def _adx_series(candles, period):
    plus_dm = [0.0]
    minus_dm = [0.0]
    for i in range(1, len(candles)):
        up = candles[i]["h"] - candles[i - 1]["h"]
        dn = candles[i - 1]["l"] - candles[i]["l"]
        plus_dm.append(up if (up > dn and up > 0) else 0.0)
        minus_dm.append(dn if (dn > up and dn > 0) else 0.0)
    tr = _ema(_true_range(candles), period)
    plus_di = [((100.0 * v) / tr[i]) if tr[i] else 0.0 for i, v in enumerate(_ema(plus_dm, period))]
    minus_di = [((100.0 * v) / tr[i]) if tr[i] else 0.0 for i, v in enumerate(_ema(minus_dm, period))]
    dx = []
    for i in range(len(plus_di)):
        s = plus_di[i] + minus_di[i]
        dx.append((100.0 * abs(plus_di[i] - minus_di[i])) / s if s else 0.0)
    return _ema(dx, period)


def _bollinger_series(closes, period, mult):
    mid = _sma(closes, period)
    sd = _stddev(closes, period, mid)
    upper = [None if m is None else m + mult * sd[i] for i, m in enumerate(mid)]
    lower = [None if m is None else m - mult * sd[i] for i, m in enumerate(mid)]
    return upper, mid, lower


def _zscore_series(closes, period):
    mean = _sma(closes, period)
    sd = _stddev(closes, period, mean)
    out = [None] * len(closes)
    for i in range(len(closes)):
        if mean[i] is None or not sd[i]:
            out[i] = None
        else:
            out[i] = (closes[i] - mean[i]) / sd[i]
    return out


# ----------------------------------------------------------------------
# AGENT 1: REGIME
# ----------------------------------------------------------------------

def _regime(ind, i, cfg):
    adx_val = ind["adx"][i]
    if adx_val is None or adx_val >= cfg["adxTrendThreshold"]:
        return False, "TREND (ADX high)"
    fast_now = ind["emaFast"][i]
    fast_prev = ind["emaFast"][i - 1]
    if fast_prev:
        slope = abs((fast_now - fast_prev) / fast_prev) * 100
        if slope >= cfg["emaSlopeMaxPct"]:
            return False, "EMA slope too steep"
    return True, ""


# ----------------------------------------------------------------------
# AGENT 2: MEAN REVERSION SIGNAL
# ----------------------------------------------------------------------

def _mr_signal(candles, ind, i, cfg):
    z = ind["zscore"][i]
    bb_lo = ind["bbLower"][i]
    bb_hi = ind["bbUpper"][i]
    r = ind["rsi"][i]
    atr_v = ind["atr"][i]
    atr_avg = ind["atrAvg50"][i]
    close = candles[i]["c"]
    if z is None or bb_lo is None or not atr_avg:
        return None
    if atr_v > cfg["atrSpikeMult"] * atr_avg:
        return None  # volatility spike — mos hyr
    # 🏆 SWEEP: z-score 2.0 (i rreptë) — sinjalet ekstreme vetëm (WR 62%)
    if z <= -2.0 and r <= cfg["rsiLongMax"]:
        return "LONG"
    if z >= 2.0 and r >= cfg["rsiShortMin"]:
        return "SHORT"
    return None


# ----------------------------------------------------------------------
# AGENT 3: CONFIRMATION (0-5)
# ----------------------------------------------------------------------

def _confirmation(candles, ind, i, side):
    if i < 2:
        return 0
    score = 0
    r_now = ind["rsi"][i]
    r_prev = ind["rsi"][i - 1]
    z_now = ind["zscore"][i]
    z_prev2 = ind["zscore"][i - 2]
    close = candles[i]["c"]
    if side == "LONG":
        if r_now > r_prev:
            score += 1
        if close > ind["bbLower"][i]:
            score += 1
        if z_now is not None and z_prev2 is not None and z_now > z_prev2:
            score += 1
    else:
        if r_now < r_prev:
            score += 1
        if close < ind["bbUpper"][i]:
            score += 1
        if z_now is not None and z_prev2 is not None and z_now < z_prev2:
            score += 1
    look = candles[max(0, i - 20):i]
    vol_avg = (sum(c["v"] for c in look) / len(look)) if look else 0
    if not vol_avg or candles[i]["v"] <= 2 * vol_avg:
        score += 1
    score += 1  # news/event risk — pa feed të integruar, pikë default
    return score


# ----------------------------------------------------------------------
# AGENT 4: RISK + DEFENSE (state machine)
# ----------------------------------------------------------------------

class DefenseAgent:
    """Port Python i DefenseAgent të JS-së."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.state = "NORMAL"
        self.consecutiveLosses = 0
        self.candlesSinceLastTrade = 0
        self.dailyPnlPct = 0.0
        self.equity = cfg["startingCapital"]
        self.peakEquity = cfg["startingCapital"]
        self._currentDay = None

    def on_new_candle(self, ts_ms):
        self.candlesSinceLastTrade += 1
        day = __import__("datetime").datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d")
        if self._currentDay is None:
            self._currentDay = day
        elif day != self._currentDay:
            self._currentDay = day
            self.dailyPnlPct = 0.0
            if self.state not in ("DEFENSE", "KILL_SWITCH"):
                self.state = "NORMAL" if self.consecutiveLosses < self.cfg["lossesToCaution"] else "CAUTION"
        if self.state == "DEFENSE" and self.candlesSinceLastTrade >= self.cfg["recoveryWaitCandles"]:
            self.state = "RECOVERY"

    def on_trade_closed(self, pnl_abs):
        pnl_pct = pnl_abs / self.equity if self.equity else 0.0
        self.equity += pnl_abs
        self.peakEquity = max(self.peakEquity, self.equity)
        self.dailyPnlPct += pnl_pct
        self.consecutiveLosses = self.consecutiveLosses + 1 if pnl_abs < 0 else 0
        self.candlesSinceLastTrade = 0
        self._update_state()

    def _update_state(self):
        dd = (self.peakEquity - self.equity) / self.peakEquity if self.peakEquity > 0 else 0.0
        if dd >= self.cfg["killSwitchDrawdownPct"]:
            self.state = "KILL_SWITCH"
            return
        if self.dailyPnlPct <= -self.cfg["dailyDrawdownStopPct"]:
            self.state = "DEFENSE"
            return
        if self.consecutiveLosses >= self.cfg["lossesToDefense"]:
            self.state = "DEFENSE"
        elif self.consecutiveLosses >= self.cfg["lossesToCaution"]:
            self.state = "CAUTION"
        elif self.state != "DEFENSE":
            self.state = "CAUTION" if self.state == "RECOVERY" else "NORMAL"

    def can_trade(self):
        return self.state in ("NORMAL", "CAUTION", "RECOVERY")

    def risk_pct(self):
        return self.cfg["riskPctNormal"] if self.state == "NORMAL" else self.cfg["riskPctCaution"]

    def confirmation_needed(self):
        return self.cfg["confirmationMinNormal"] if self.state == "NORMAL" else self.cfg["confirmationMinCaution"]


# ----------------------------------------------------------------------
# AGENT 5: PORTFOLIO + AGENT 6: EXECUTION
# ----------------------------------------------------------------------

def _portfolio(open_positions, cfg):
    return False if len(open_positions) >= cfg["maxOpenTrades"] else True


def _execution(side, entry, atr_val, risk_amount, cfg):
    sl_dist = cfg["slAtrMult"] * atr_val
    tp_dist = cfg["tpAtrMult"] * atr_val
    size = (risk_amount / sl_dist) if sl_dist > 0 else 0.0
    sl = entry - sl_dist if side == "LONG" else entry + sl_dist
    tp = entry + tp_dist if side == "LONG" else entry - tp_dist
    return {"entry": entry, "sl": sl, "tp": tp, "size": size}


# ----------------------------------------------------------------------
# PIPELINE — orchestron të 6 agjentët (port i Pipeline të JS-së)
# ----------------------------------------------------------------------

class Pipeline:
    def __init__(self, cfg=None):
        self.cfg = dict(DEFAULT_CONFIG)
        if cfg:
            self.cfg.update(cfg)
        self.defense = DefenseAgent(self.cfg)
        self.open_positions = []

    def on_candle(self, candle_history):
        """Kthen: {action, state, trade?, reason?}"""
        cfg = self.cfg
        i = len(candle_history) - 1
        closes = [c["c"] for c in candle_history]
        current = candle_history[i]

        self.defense.on_new_candle(current["t"])

        # --- menaxho pozicionin e hapur ---
        if self.open_positions:
            pos = self.open_positions[0]
            hit_sl = (current["l"] <= pos["sl"]) if pos["side"] == "LONG" else (current["h"] >= pos["sl"])
            hit_tp = (current["h"] >= pos["tp"]) if pos["side"] == "LONG" else (current["l"] <= pos["tp"])
            if hit_sl or hit_tp:
                exit_px = pos["sl"] if hit_sl else pos["tp"]
                pnl = ((exit_px - pos["entry"]) * pos["size"]) if pos["side"] == "LONG" \
                    else ((pos["entry"] - exit_px) * pos["size"])
                fee = (pos["entry"] + exit_px) * pos["size"] * cfg["takerFeePct"]
                self.open_positions.pop(0)
                self.defense.on_trade_closed(pnl - fee)
                return {"action": "CLOSE", "state": self.defense.state,
                        "exitPrice": exit_px, "pnl": pnl - fee}
            if len(self.open_positions) >= cfg["maxOpenTrades"]:
                return {"action": "WAIT", "state": self.defense.state, "reason": "Position open"}

        if self.defense.state == "KILL_SWITCH":
            return {"action": "WAIT", "state": "KILL_SWITCH",
                    "reason": "Kill switch aktiv — review manual"}
        if not self.defense.can_trade():
            return {"action": "WAIT", "state": self.defense.state,
                    "reason": "Defense mode nuk lejon trade"}
        if len(candle_history) < max(cfg["emaSlow"], cfg["bbPeriod"], cfg["zscorePeriod"], cfg["atrPeriod"]) + 5:
            return {"action": "WAIT", "state": self.defense.state,
                    "reason": "Jo mjaftueshëm histori për indikatorët"}

        # --- indikatorë ---
        ind = {
            "rsi": _rsi_series(closes, cfg["rsiPeriod"]),
            "atr": _atr_series(candle_history, cfg["atrPeriod"]),
            "adx": _adx_series(candle_history, cfg["adxPeriod"]),
            "emaFast": _ema(closes, cfg["emaFast"]),
            "emaSlow": _ema(closes, cfg["emaSlow"]),
            "zscore": _zscore_series(closes, cfg["zscorePeriod"]),
        }
        bb_u, _, bb_l = _bollinger_series(closes, cfg["bbPeriod"], cfg["bbStdDev"])
        ind["bbUpper"] = bb_u
        ind["bbLower"] = bb_l
        ind["atrAvg50"] = _sma(ind["atr"], 50)

        # Agent 1: Regime
        ok, reason = _regime(ind, i, cfg)
        if not ok:
            return {"action": "WAIT", "state": self.defense.state, "reason": reason}
        # Agent 2: MR signal
        side = _mr_signal(candle_history, ind, i, cfg)
        if not side:
            return {"action": "WAIT", "state": self.defense.state, "reason": "Nuk ka sinjal MR"}
        # Agent 3: Confirmation
        score = _confirmation(candle_history, ind, i, side)
        need = self.defense.confirmation_needed()
        if score < need:
            return {"action": "WAIT", "state": self.defense.state,
                    "reason": "Confirmation %d/%d" % (score, need)}
        # Agent 5: Portfolio
        if not _portfolio(self.open_positions, cfg):
            return {"action": "WAIT", "state": self.defense.state, "reason": "Max open trades reached"}
        # Agent 4: Risk sizing
        atr_v = ind["atr"][i]
        if not atr_v or atr_v <= 0:
            return {"action": "WAIT", "state": self.defense.state, "reason": "ATR i pavlefshëm"}
        risk_amount = self.defense.equity * self.defense.risk_pct()
        # Agent 6: Execution
        order = _execution(side, current["c"], atr_v, risk_amount, cfg)
        if order["size"] <= 0:
            return {"action": "WAIT", "state": self.defense.state, "reason": "Size 0"}
        self.open_positions.append({"side": side, "entry": order["entry"],
                                    "sl": order["sl"], "tp": order["tp"],
                                    "size": order["size"], "entryIdx": i})
        return {"action": side, "state": self.defense.state, "trade": order}


# ----------------------------------------------------------------------
# FUNKSION STRATEGJIE — i pajtueshëm me strategjitë e botit
# (merr k = listë candlesh {t,o,h,l,c,v}, kthen direction + confidence)
# ----------------------------------------------------------------------

def analyze_signal(candles, cfg=None):
    """Kthen {'direction', 'confidence'} ose None — logjika e pipeline-së
    (Regime + MR signal + Confirmation) pa gjendjen e hapur të pozicioneve."""
    cfg = cfg or DEFAULT_CONFIG
    if len(candles) < max(cfg["emaSlow"], cfg["bbPeriod"], cfg["zscorePeriod"]) + 5:
        return None
    closes = [c["c"] for c in candles]
    i = len(candles) - 1
    ind = {
        "rsi": _rsi_series(closes, cfg["rsiPeriod"]),
        "atr": _atr_series(candles, cfg["atrPeriod"]),
        "adx": _adx_series(candles, cfg["adxPeriod"]),
        "emaFast": _ema(closes, cfg["emaFast"]),
        "emaSlow": _ema(closes, cfg["emaSlow"]),
        "zscore": _zscore_series(closes, cfg["zscorePeriod"]),
    }
    bb_u, _, bb_l = _bollinger_series(closes, cfg["bbPeriod"], cfg["bbStdDev"])
    ind["bbUpper"] = bb_u
    ind["bbLower"] = bb_l
    ind["atrAvg50"] = _sma(ind["atr"], 50)

    ok, _ = _regime(ind, i, cfg)
    if not ok:
        return None
    side = _mr_signal(candles, ind, i, cfg)
    if not side:
        return None
    score = _confirmation(candles, ind, i, side)
    if score < cfg["confirmationMinNormal"]:
        return None
    # confidence 58..88 nga forca e konfirmimit (2..5)
    conf = min(88.0, 58.0 + (score - 2) * 7.5)
    return {"direction": side, "confidence": conf}


def atr_sl_tp(candles, entry, cfg=None):
    """Kthen {'sl': x, 'tp': y} me distancat ATR 1.0× / 1.3× — si Execution-i i JS."""
    cfg = cfg or DEFAULT_CONFIG
    atr_v = _atr_series(candles, cfg["atrPeriod"])[-1]
    if not atr_v or atr_v <= 0:
        return None
    sl_dist = cfg["slAtrMult"] * atr_v
    tp_dist = cfg["tpAtrMult"] * atr_v
    return {"sl_dist": sl_dist, "tp_dist": tp_dist, "atr": atr_v}
