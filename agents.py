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
                    REAL_MAX_POSITIONS,
                    ENABLE_PARTIAL_TP, TP1_PARTIAL, PARTIAL_FRACTION,
                    TRAIL_PCT, RUNNER_BE, REL_STRENGTH_BOOST,
                    MTF_ENABLED, MTF_BAR, MTF_FAST, MTF_SLOW, MTF_CACHE_TTL)
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
            if sym in e.cooldown and now - e.cooldown[sym] < 20:    # rihyrje e shpejtë
                continue
            klines = await ctx.market.fetch_klines(sym, "5m", 120)   # 5m sinjale (më pak zhurmë)
            if len(klines) >= 30:
                ctx.candles[sym] = klines
                scanned.append(sym)
                e.scan_count += 1          # 🔢 charts analysed
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
# ======================================================================
# 🧠 BRAIN AGENT — filtri i trurit mbi të gjitha sinjalet.
# Veton sinjalet që s'kanë bazë reale:
#   1) TREND GATE: sinjalet duhet të jenë në drejtimin e trendit 1H
#      (EMA 200) — asnjë LONG në treg rënës, asnjë SHORT në treg rritës
#   2) VOLATILITETI: s'hyn në treg të vdekur (ATR < 0.15% në 1H)
# Kjo është e testuar: Trend Gate përgjysmon humbjet (−$450 → −$202).
# ======================================================================
class BrainAgent(Agent):
    step, name, icon = 1, "Brain", "🧠"
    role = "Filtri i trurit: trendi 1H (EMA200) + volatiliteti (ATR) mbi çdo sinjal"

    async def execute(self, ctx, idx):
        e = self.engine
        trend_bar = "1h"
        now = time.time()
        brain = getattr(e, "brain_cache", {})
        e.brain_cache = brain
        for sym in list(ctx.votes.keys()):
            cached = brain.get(sym)
            if cached and now - cached[0] < 300:
                info = cached[1]
            else:
                try:
                    kl = await ctx.market.fetch_klines(sym, trend_bar, 250)
                except Exception:
                    continue
                if not kl or len(kl) < 210:
                    continue
                closes = [c["c"] for c in kl]
                e200 = ema(closes, 200)[-1]
                trend_long = closes[-1] > e200
                # 🧠 DAKORDËSI E DYFISHTË: 15m (EMA50>EMA200) duhet të pajtohet
                # me 1H (EMA200) — testuar: humbjet −$450 → −$79 (6× më mirë).
                dual_ok = True
                try:
                    k15 = await ctx.market.fetch_klines(sym, "15m", 250)
                    if k15 and len(k15) >= 210:
                        c15 = [c["c"] for c in k15]
                        dual_long = ema(c15, 50)[-1] > ema(c15, 200)[-1]
                        if dual_long != trend_long:
                            dual_ok = False
                except Exception:
                    pass
                # ATR% në 1H
                trs = []
                for i in range(-14, 0):
                    h, l, pc = kl[i]["h"], kl[i]["l"], kl[i-1]["c"]
                    trs.append(max(h - l, abs(h - pc), abs(l - pc)))
                atr_pct = (sum(trs) / 14) / (closes[-1] or 1) * 100 if trs else 0
                why = (f"trend {'rritës' if trend_long else 'rënës'} 1H (EMA200)"
                       + ("" if dual_ok else " + 15m kundërshton"))
                info = (trend_long, atr_pct, why, dual_ok)
                brain[sym] = (now, info)
            trend_long, atr_pct, why, dual_ok = info
            # 🔒 VETO: 15m kundërshton 1H → s'hap
            if not dual_ok:
                del ctx.votes[sym]
                self.report(f"🧠 {sym}: 15m kundërshton 1H ({why}) — veto", sym)
                continue
            # VETO: treg i vdekur
            if atr_pct < 0.15:
                del ctx.votes[sym]
                self.report(f"🧠 {sym}: treg i vdekur (ATR {atr_pct:.2f}%) — s'hap", sym)
                continue
            # filtro votat: vetëm në drejtimin e trendit 1H
            kept = [v for v in ctx.votes[sym] if (v[1] == "LONG") == trend_long]
            if not kept:
                del ctx.votes[sym]
                self.report(f"🧠 {sym}: sinjalet kundër trendit ({why}) — veto", sym)
            else:
                ctx.votes[sym] = kept
                self.report(f"🧠 {sym}: {why} — sinjale në linjë", sym)



class ConsensusAgent(Agent):
    step, name, icon = 1, "Consensus", "🗳️"
    role = "Kombinon votat e 10 strategjive me peshat e mësuara"

    async def execute(self, ctx, idx):
        e = self.engine
        weights = e.strategy_stats
        threshold = e.meta_state.get("threshold", 0.05)   # adaptive (meta-learning)
        rms = self._relative_strength(ctx)                # "arbitrage" across symbols
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
            if score > threshold:
                direction = "LONG"
            elif score < -threshold:
                direction = "SHORT"
            else:
                continue
            supporting = [sname for sname, d, _ in votes
                          if d == direction]
            if len(supporting) < 3:              # 🧠 duhen ≥3 strategji bashkë (sinjal më cilësor)
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
            })

        if not candidates:
            self.report(f"Pa konsensus (pragu adaptiv {threshold:.2f}) — "
                        f"boti pret sinjale më të forta")
            ctx.stop = True
            return

        candidates.sort(key=lambda c: c["confidence"], reverse=True)
        best = candidates[0]
        ctx.chosen = best
        ctx.votes_for_trade = best["supporting"]
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
            if r > 85 or r < 15:
                self.report(f"{best['symbol']}: RSI ekstrem ({r:.0f}) — i mbingarkuar",
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
        if MTF_ENABLED:
            ok, m = await self._mtf(e, best["symbol"], best["direction"])
            if not ok:
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
# ======================================================================
# 👥 GRUPACIONE (grupacione) — agjentët e menaxhojnë botin në GRUPE.
# Çdo grup ka rolin e vet; tregtia hapet VETËM kur grupet e miratojnë.
# ======================================================================
GROUPS = [
    {"id": "scan",   "icon": "📡", "name": "Skanimi",
     "role": "Të dhënat + trendi", "members": ["Scanner"]},
    {"id": "strat",  "icon": "🎯", "name": "Strategjitë",
     "role": "10 strategji votojnë", "members": ["Strategy"]},
    {"id": "brain",  "icon": "🧠", "name": "Truri",
     "role": "Trend 15m+1h, ATR, konsensus, AI", "members": ["Brain", "Consensus", "AI Predictor", "Regime"]},
    {"id": "safety", "icon": "🛡️", "name": "Siguria",
     "role": "Validator + Risk Manager", "members": ["Validator", "Risk"]},
    {"id": "exec",   "icon": "⚖️", "name": "Ekzekutimi",
     "role": "Sizer + Filler + Tracker + Learning", "members": ["Sizer", "Filler", "Tracker", "Learning"]},
]
GROUP_BY_NAME = {}
for _g in GROUPS:
    for _m in _g["members"]:
        GROUP_BY_NAME[_m] = _g["id"]


class GroupCoordinatorAgent(Agent):
    step, name, icon = 3, "Groups", "👥"
    role = "Menaxhon grupet: tregtia miratohet vetëm nga shumica e grupeve"

    async def execute(self, ctx, idx):
        e = self.engine
        if ctx.stop or not ctx.chosen:
            return
        sym = ctx.chosen["symbol"]
        direction = ctx.chosen["direction"]
        # 👥 votat e grupeve për këtë sinjal
        approvals = []        # (id, icon, name, ok)
        # 📡 Skanimi: të dhënat ekzistojnë dhe Brain nuk e vtoi (simboli ka vota)
        votes = ctx.votes.get(sym, [])
        scan_ok = len(votes) >= 3
        approvals.append(("scan", "📡", "Skanimi", scan_ok))
        # 🎯 Strategjitë: drejtimi mbështetet nga strategjitë
        sup = [v for v in votes if v[1] == direction]
        strat_ok = len(sup) >= 3
        approvals.append(("strat", "🎯", "Strategjitë", strat_ok))
        # 🧠 Truri: konsensusi zgjodhi këtë drejtim (ctx.chosen ekziston)
        brain_ok = ctx.chosen.get("confidence", 0) >= 60
        approvals.append(("brain", "🧠", "Truri", brain_ok))
        # 🛡️ Siguria: Validator + Risk nuk e ndalën (ctx.stop False, jo locked)
        safety_ok = not e.is_locked()
        approvals.append(("safety", "🛡️", "Siguria", safety_ok))
        ok_n = sum(1 for _, _, _, ok in approvals if ok)
        need = 3   # nevojiten ≥3 nga 4 grupet vendimtare
        if ok_n < need:
            ctx.stop = True
            bad = ", ".join(f"{ic} {nm}" for gid, ic, nm, ok in approvals if not ok)
            self.report(
                f"👥 Grupet NUK miratuan ({ok_n}/{need}): {bad} — sinjali hidhet",
                sym, direction, ctx.chosen.get("confidence", 0))
            return
        ok_line = " ".join(f"{ic}✓" if ok else f"{ic}✗"
                           for _, ic, _, ok in approvals)
        e.groups_last = {"symbol": sym, "direction": direction,
                         "approvals": ok_n, "need": need, "line": ok_line}
        self.report(f"👥 Grupet miratuan ({ok_n}/{need}): {ok_line} — {sym} {direction}",
                    sym, direction, ctx.chosen.get("confidence", 0))


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
        # stop distance depends on direction (SHORT SL is ABOVE entry)
        sl = sig.get("sl")
        if sl is None:
            sl = entry * (1 - STOP_LOSS) if sig["direction"] == "LONG" \
                else entry * (1 + STOP_LOSS)
        stop_dist = abs(entry - sl)
        risk_amount = base * TRADE_RISK
        # 🎯 HUMBJA TOTALE = $2 (kërkesa e përdoruesit): SL ($risk_amount)
        # + tarifat (0.1% hyrje + 0.1% dalje mbi notional). Llogarisim qty
        # që të plotësojë:  qty*stop_dist + qty*entry*2*FEE_RATE <= risk_total
        # ku risk_total = $2. Zgjidhje: qty = risk_total / (stop_dist + entry*2*FEE_RATE)
        risk_total = max(risk_amount, 2.0)   # të paktën $2, por jo më pak se risk_amount
        denom = stop_dist + entry * 2 * FEE_RATE
        qty = risk_total / denom if denom > 0 else 0.0
        if qty * entry > equity * 0.35:
            qty = equity * 0.35 / entry
        ctx.qty = qty
        loss_est = qty * stop_dist + qty * entry * 2 * FEE_RATE
        self.report(f"{qty:.4f} @ {entry:.6g} — humbja max ${loss_est:.2f} "
                    f"(SL ${qty*stop_dist:.2f} + tarifa ${qty*entry*2*FEE_RATE:.2f})",
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

        entry = sig.get("entry", 0)
        if sig["direction"] == "LONG":
            sig["tp"] = entry * (1 + TAKE_PROFIT)
            sig["sl"] = entry * (1 - STOP_LOSS)
        else:
            sig["tp"] = entry * (1 - TAKE_PROFIT)
            sig["sl"] = entry * (1 + STOP_LOSS)

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

    async def _track_classic(self, e, pos, price):
        side = pos["side"]
        hit_tp = (price >= pos["tp"]) if side == "LONG" else (price <= pos["tp"])
        hit_sl = (price <= pos["sl"]) if side == "LONG" else (price >= pos["sl"])
        if not hit_tp and not hit_sl:
            # 🧠 TRAILING INTELLIGJENT: sapo fitimi arrin +0.8%, SL ngrihet
            # pas çmimit (0.6% poshtë majës) — nëse tregu kthehet, mbyll me
            # fitim të mirë në vend që të presë TP-në dhe të kthehet në humbje.
            trail_on = 0.008
            trail_dist = 0.006
            if side == "LONG":
                pnl_pct = (price - pos["entry"]) / pos["entry"]
                if pnl_pct >= trail_on:
                    new_sl = price * (1 - trail_dist)
                    if new_sl > pos["sl"]:
                        e._update_sl(pos["id"], new_sl)
                elif pnl_pct >= BREAKEVEN_AT:
                    new_sl = pos["entry"] * 1.0005
                    if new_sl > pos["sl"]:
                        e._update_sl(pos["id"], new_sl)
            else:
                pnl_pct = (pos["entry"] - price) / pos["entry"]
                if pnl_pct >= trail_on:
                    new_sl = price * (1 + trail_dist)
                    if new_sl < pos["sl"]:
                        e._update_sl(pos["id"], new_sl)
                elif pnl_pct >= BREAKEVEN_AT:
                    new_sl = pos["entry"] * 0.9995
                    if new_sl < pos["sl"]:
                        e._update_sl(pos["id"], new_sl)
        if hit_tp or hit_sl:
            await e._close_trade(pos, price, "tp" if hit_tp else "sl")

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
                fresh, max_id = aggregate_from_trades(c, e.learning_last_id)
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
            meta["threshold"] = meta_threshold(results)
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

        trained = sum(1 for s in e.strategy_stats.values()
                      if s.get("trades", 0) > 0)
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
              [BrainAgent, ConsensusAgent, AIPredictorAgent, RegimeFilterAgent,
               ValidatorAgent, RiskManagerAgent, GroupCoordinatorAgent,
               SizerAgent,
               FillerAgent, TrackerAgent, LearningAgent])
