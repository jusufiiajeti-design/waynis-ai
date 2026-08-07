"""
Waynis AI — 20-AGENT collaborative control system.

The bot is run by TWENTY specialised agents that work together and LEARN:

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
import json
import os
import time

from config import (STARTING_BALANCE, SCAN_BATCH, TRADE_RISK,
                    TAKE_PROFIT, STOP_LOSS, BREAKEVEN_AT,
                    MIN_CONFIDENCE, MAX_OPEN, FEE_RATE,
                    REAL_MIN_NOTIONAL, REAL_MAX_NOTIONAL_PCT,
                    REAL_MAX_POSITIONS)
from providers import WATCHLIST
from strategies import STRATEGIES, vol_ratio as _vol_ratio, rsi as _rsi

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
        open_syms = {p["symbol"] for p in e.open_positions()}
        now = time.time()
        batch = (syms[idx % len(syms):] + syms[:idx % len(syms)])[:SCAN_BATCH]

        scanned = []
        for sym in batch:
            if sym in open_syms:
                continue
            if sym in e.cooldown and now - e.cooldown[sym] < 300:
                continue
            klines = await ctx.market.fetch_klines(sym, "1m", 60)
            if len(klines) >= 30:
                ctx.candles[sym] = klines
                scanned.append(sym)
            await asyncio.sleep(0.04)

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
# 🗳️ 12 — CONSENSUS (combines votes with learning weights)
# ======================================================================
class ConsensusAgent(Agent):
    step, name, icon = 1, "Consensus", "🗳️"
    role = "Kombinon votat e 10 strategjive me peshat e mësuara"

    async def execute(self, ctx, idx):
        e = self.engine
        weights = e.strategy_stats
        candidates = []

        for sym, votes in ctx.votes.items():
            net = 0.0
            tw = 0.0
            for sname, d, conf in votes:
                w = weights.get(sname, {}).get("weight", 1.0)
                net += (1.0 if d == "LONG" else -1.0) * w * (conf / 100.0)
                tw += w
            if tw <= 0:
                continue
            score = net / tw                     # -1 .. 1
            if score > 0.12:
                direction = "LONG"
            elif score < -0.12:
                direction = "SHORT"
            else:
                continue
            confidence = min(94.0, 50.0 + abs(score) * 140.0)
            supporting = [sname for sname, d, _ in votes
                          if d == direction]
            candidates.append({
                "symbol": sym, "direction": direction,
                "confidence": confidence, "score": score,
                "supporting": supporting,
                "n_votes": len(votes),
            })

        if not candidates:
            self.report("Pa konsensus mes strategjive — asnjë tregti e sigurt")
            ctx.stop = True
            return

        candidates.sort(key=lambda c: c["confidence"], reverse=True)
        best = candidates[0]
        ctx.chosen = best
        ctx.votes_for_trade = best["supporting"]
        self.report(
            f"{best['symbol']} {best['direction']} — konsensus "
            f"{best['confidence']:.0f}% · {best['n_votes']} strategji "
            f"(net {best['score']:+.2f}) · mbështesin: "
            f"{', '.join(best['supporting'][:4])}",
            best["symbol"], best["direction"], best["confidence"])


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

        # per-symbol volume check from candles
        klines = ctx.candles.get(best["symbol"])
        if klines:
            vols = [c["v"] for c in klines]
            vr = _vol_ratio(vols)
            closes = [c["c"] for c in klines]
            r = _rsi(closes)
            if vr < 1.02:
                self.report(f"{best['symbol']}: volumi i ulët — setup i hedhur",
                            best["symbol"], best["direction"], best["confidence"])
                ctx.stop = True
                return
            if r > 80 or r < 20:
                self.report(f"{best['symbol']}: RSI ekstrem ({r:.0f}) — i mbingarkuar",
                            best["symbol"], best["direction"], best["confidence"])
                ctx.stop = True
                return
            mom = (closes[-1] - closes[-2]) / closes[-2] if closes[-2] else 0
            if abs(mom) > 0.004:
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

        self.report(f"{best['symbol']}: validuar ✓ — volumi dhe RSI në rregull",
                    best["symbol"], best["direction"], best["confidence"])


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
        if e.mode == "real":
            bal = e.real_balance()
            notional = ctx.qty * ctx.chosen.get("entry", 0)
            if notional > bal * REAL_MAX_NOTIONAL_PCT:
                ctx.qty = bal * REAL_MAX_NOTIONAL_PCT / ctx.chosen.get("entry", 1)
            self.report(f"💰 Risk: balanca ${bal:.2f}, ekspozim ≤ "
                        f"{REAL_MAX_NOTIONAL_PCT*100:.0f}%",
                        ctx.chosen["symbol"], ctx.chosen["direction"],
                        ctx.chosen["confidence"])
        else:
            self.report("Risk: ≤4 pozicione, drawdown ≤10%, ekspozim ≤35%",
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

        if e.mode == "real":
            bal = e.real_balance()
            notional = bal * REAL_MAX_NOTIONAL_PCT
            ctx.qty = notional / entry if entry else 0
            self.report(f"💰 REAL {ctx.qty:.6f} @ {entry:.6g} (~${notional:.2f}, "
                        f"maks {REAL_MAX_NOTIONAL_PCT*100:.0f}% e balancës)",
                        sig["symbol"], sig["direction"], sig["confidence"])
            return

        equity = e.account()["equity"]
        base = equity if e.compound else STARTING_BALANCE
        mode = "KOMPONIM" if e.compound else "FIKS"
        stop_dist = abs(entry - sig.get("sl", entry * 0.9965))
        risk_amount = base * TRADE_RISK
        qty = risk_amount / stop_dist if stop_dist > 0 else 0.0
        if qty * entry > equity * 0.35:
            qty = equity * 0.35 / entry
        ctx.qty = qty
        self.report(f"{qty:.4f} @ {entry:.6g} — risk ${risk_amount:.2f} ({mode})",
                    sig["symbol"], sig["direction"], sig["confidence"])


# ======================================================================
# 🚦 18 — FILLER
# ======================================================================
class FillerAgent(Agent):
    step, name, icon = 4, "Filler", "🚦"
    role = "Ekzekuton urdhrin (paper ose real)"

    async def execute(self, ctx, idx):
        e = self.engine
        sig = ctx.chosen
        if ctx.qty <= 0:
            self.report("Madhësi zero — urdhri anulohet",
                        sig["symbol"], sig["direction"], sig["confidence"])
            ctx.stop = True
            return

        tp = sig.get("entry", 0) * (1 + TAKE_PROFIT)
        sl = sig.get("entry", 0) * (1 - STOP_LOSS)
        sig["tp"] = tp
        sig["sl"] = sl

        if e.mode == "real":
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

        ctx.trade_id = e._open_trade(sig, ctx.qty, votes=ctx.votes_for_trade)
        self.report(f"{sig['direction']} {sig['symbol']} {ctx.qty:.4f} @ "
                    f"{sig['entry']:.6g} — nga {len(ctx.votes_for_trade)} strategji",
                    sig["symbol"], sig["direction"], sig["confidence"])
        if ctx.trade_id:
            e._event("fill",
                     f"{sig['direction']} {sig['symbol']} {ctx.qty:.4f} @ "
                     f"{sig['entry']:.6g} · konsensus {sig['confidence']:.0f}% · "
                     f"{len(ctx.votes_for_trade)} strategji",
                     sig["symbol"])
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
                    await e.real_close(pos, price, "tp" if hit_tp else "sl")
                else:
                    await e._close_trade(pos, price, "tp" if hit_tp else "sl")

        if positions:
            p = positions[0]
            self.report(f"{len(positions)} pozicion(e) aktive — duke monitoruar TP/SL",
                        p["symbol"], p["side"])
        else:
            self.report("Asnjë pozicion aktiv — cikli u përfundua")


# ======================================================================
# 🎓 20 — LEARNING AGENT (updates strategy weights after every trade)
# ======================================================================
class LearningAgent(Agent):
    step, name, icon = 5, "Learning", "🎓"
    role = "Mëson: rregullon peshat e strategjive pas çdo tregtie"

    async def execute(self, ctx, idx):
        e = self.engine
        stats = e.strategy_stats
        last_id = e.learning_last_id
        updated = set()

        try:
            with e._conn() as c:
                rows = c.execute(
                    "SELECT id, votes, status, pnl FROM trades "
                    "WHERE status!='open' AND id>? ORDER BY id",
                    (last_id,)).fetchall()
            max_id = last_id
            for tid, votes_json, status, pnl in rows:
                max_id = max(max_id, tid)
                if not votes_json:
                    continue
                try:
                    names = json.loads(votes_json)
                except Exception:
                    continue
                if not names:
                    continue
                for sname in names:
                    st = stats.setdefault(sname, dict(DEFAULT_STATS))
                    st["trades"] += 1
                    if status == "win":
                        st["wins"] += 1
                    else:
                        st["losses"] += 1
                    st["pnl"] = round(st["pnl"] + (pnl or 0.0), 2)
                    wr = (st["wins"] - st["losses"]) / max(st["trades"], 1)
                    pnl_adj = max(-0.5, min(0.5, st["pnl"] / 40.0))
                    st["weight"] = round(
                        max(0.4, min(1.8, 0.5 + wr * 0.35 + pnl_adj * 0.3)), 3)
                    updated.add(sname)
            if max_id > last_id:
                e.learning_last_id = max_id
                e.persist_learning()
        except Exception:
            pass

        if updated:
            top = sorted(updated,
                         key=lambda n: stats[n].get("weight", 1.0),
                         reverse=True)[:4]
            self.report(f"🎓 Mësova nga {len(updated)} strategji — "
                        f"më të forta tani: {', '.join(top)}")
        else:
            self.report("🎓 Në pritje të tregtive për të mësuar")


# ======================================================================
# ALL 20 AGENTS (order = execution order)
# ======================================================================
ALL_AGENTS = ([ScannerAgent] + STRATEGY_AGENTS +
              [ConsensusAgent, AIPredictorAgent, RegimeFilterAgent,
               ValidatorAgent, RiskManagerAgent, SizerAgent,
               FillerAgent, TrackerAgent, LearningAgent])
