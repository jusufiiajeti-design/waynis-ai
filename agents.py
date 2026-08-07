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

from config import (STARTING_BALANCE, SCAN_BATCH, TRADE_RISK,
                    TAKE_PROFIT, STOP_LOSS, BREAKEVEN_AT,
                    MIN_CONFIDENCE, MAX_OPEN, FEE_RATE,
                    REAL_MIN_NOTIONAL, REAL_MAX_NOTIONAL_PCT,
                    REAL_MAX_POSITIONS)
from providers import WATCHLIST


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

        if e.mode == "real":
            # Real mode = SPOT, LONG-only, smaller max positions
            if not e.exchange.configured:
                self.report("💰 REAL: çelësat e Binance-ut nuk janë konfiguruar "
                            "(BINANCE_API_KEY/SECRET te Render → Environment)",
                            best["symbol"], best["direction"], best["confidence"])
                ctx.stop = True
                return
            max_pos = REAL_MAX_POSITIONS
            if len(e.open_positions()) >= max_pos:
                self.report(f"💰 REAL: portofoli i plotë ({max_pos}/{max_pos})",
                            best["symbol"], best["direction"], best["confidence"])
                ctx.stop = True
                return
            if best["direction"] != "LONG":
                self.report("💰 REAL: spot = vetëm LONG — SHORT anashkalohet",
                            best["symbol"], best["direction"], best["confidence"])
                ctx.stop = True
                return
        else:
            if len(e.open_positions()) >= MAX_OPEN:
                self.report(f"Portofoli i plotë ({MAX_OPEN}/{MAX_OPEN}) — duke pritur hapësirë",
                            best["symbol"], best["direction"], best["confidence"])
                ctx.stop = True
                return

        for cand in ctx.signals:
            ok, msg = self._validate(cand)
            if not ok:
                continue
            if e.mode == "real" and cand["direction"] != "LONG":
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

        if e.mode == "real":
            # REAL mode sizing: LONG-only, min notional, % of real balance
            bal = e.real_balance()
            max_notional = bal * REAL_MAX_NOTIONAL_PCT
            notional = max_notional
            qty = notional / sig["entry"]
            ctx.qty = qty
            self.report(
                f"💰 REAL {qty:.6f} @ {sig['entry']:.6g} (~${notional:.2f}, "
                f"maks {REAL_MAX_NOTIONAL_PCT*100:.0f}% e balancës)",
                sig["symbol"], sig["direction"], sig["confidence"])
            return

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

        if e.mode == "real":
            # REAL: execute on the exchange (spot, LONG)
            ctx.trade_id = await e.real_open(sig, ctx.qty)
            if not ctx.trade_id:
                self.report(f"💰 REAL: urdhri dështoi për {sig['symbol']}",
                            sig["symbol"], sig["direction"], sig["confidence"])
                ctx.stop = True
                return
            self.report(f"💰 REAL {sig['direction']} {sig['symbol']} "
                        f"{ctx.qty:.6f} @ {sig['entry']:.6g} — TP/SL në exchange",
                        sig["symbol"], sig["direction"], sig["confidence"])
            await asyncio.sleep(1.0)
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
                if e.mode == "real":
                    # REAL: close on the exchange (cancels bracket, market sell)
                    await e.real_close(pos, price, "tp" if hit_tp else "sl")
                else:
                    await e._close_trade(pos, price, "tp" if hit_tp else "sl")

        if positions:
            p = positions[0]
            self.report(f"{len(positions)} pozicion(e) aktive — duke monitoruar TP/SL",
                        p["symbol"], p["side"])
        else:
            self.report("Asnjë pozicion aktiv — cikli u përfundua")
