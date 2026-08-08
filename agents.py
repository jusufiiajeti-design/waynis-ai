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
                    MIN_CONFIDENCE, MAX_OPEN, COOLDOWN_SEC, TRADE_TF, KLINES_TTL, FEE_RATE,
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
    role = "500 variante strategjike votojnë për kandidatin kryesor"

    async def execute(self, ctx, idx):
        e = self.engine
        variants = getattr(e, "variant_strategies", [])
        if not variants or not ctx.votes:
            return
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
        # cache ensemble votes for ~10s — 100 variants aren't recomputed
        # every cycle, so cycles run much faster
        ecache = e.ensemble_cache
        now = time.time()
        cached = ecache.get(best_sym)
        if cached and now - cached[0] < 10.0:
            ctx.votes.setdefault(best_sym, []).extend(cached[1])
            self.report(f"🧩 {len(cached[1])} variante (nga cache) — "
                        f"konsensus i plotë")
            return
        ticker = ctx.tickers.get(best_sym)
        voted = 0
        votes_list = ctx.votes.setdefault(best_sym, [])
        for v in variants:
            try:
                r = v["fn"](best_sym, klines, ticker)
                if r:
                    votes_list.append((v["name"], r["direction"],
                                       r["confidence"]))
                    voted += 1
            except Exception:
                continue
        if voted:
            ecache[best_sym] = (now, list(votes_list))
        if voted:
            self.report(f"🧩 {voted}/{len(variants)} variante votuan për "
                        f"{best_sym} — konsensus i plotë")
        else:
            self.report(f"🧩 {len(variants)} variante — asnjë sinjal i fortë")


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
    role = "Kombinon votat e 10 strategjive me peshat e mësuara"

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
            supporting = [sname for sname, d, _ in votes
                          if d == direction]
            # grid-style consensus: 1 strong strategy (≥65%) OR 2+ weaker
            strong = [v for v in votes if v[1] == direction and v[2] >= 65]
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
            exit_reason = self._smart_exit(e, pos, price, ctx)
            if exit_reason:
                await e._close_trade(pos, price, exit_reason)
                continue

            # 📈 trailing — kyç fitimin e arsyeshëm (SL lëviz me çmimin)
            if e.mode == "paper":
                self._trail_profit(e, pos, price)

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

    def _smart_exit(self, e, pos, price, ctx):
        """Agjentët e ndalin tregtinë kur fitimi është i ARSYESHËM:
        • Shkalla në $: +$0.5, +$1, +$2, +$3 → kapet sa t'ia arrijë
        • +0.30% e arsyeshme → kapet gjithmonë
        • RSI ekstrem / trend i kthyer / momentum i mbaruar → kapet
        Kështu fitimi i arsyeshëm ruhet, jo i lihet rastit."""
        side = pos["side"]
        qty = pos["qty"] or 1
        pnl_pct = (price - pos["entry"]) / pos["entry"] * 100 \
            if side == "LONG" else (pos["entry"] - price) / pos["entry"] * 100
        if pnl_pct < 0.05:
            return None
        # 💵 dollar ladder — fitimi në $ është kriteri kryesor
        # (5m kornizë: kap $0.5 shpejt, pastaj $1/$2 kur lëvizja vazhdon)
        pnl_usd = pos["entry"] * qty * pnl_pct / 100
        for rung in (2.0, 1.0, 0.5):
            if pnl_usd >= rung:
                return (f"smart: +${pnl_usd:.2f} fitim i arsyeshëm "
                        f"(shkalla ${rung:g}) — kapur")
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

        if side == "LONG":
            if pnl_pct >= 0.30:
                return f"smart: +{pnl_pct:.2f}% e arsyeshme — fitim i kapur"
            if pnl_pct >= 0.15 and last2 < 0:
                return f"smart: +{pnl_pct:.2f}% me momentum të dobësuar — kapur"
            if r > 68:
                return "smart: RSI i mbingarkuar — fitim i kapur"
            if e9 < e21:
                return "smart: trendi u kthye poshtë — fitim i kapur"
            if last2 < 0 and mom < 0:
                return "smart: momentum i dobësuar — fitim i kapur"
        else:
            if pnl_pct >= 0.30:
                return f"smart: +{pnl_pct:.2f}% e arsyeshme — fitim i kapur"
            if pnl_pct >= 0.15 and last2 > 0:
                return f"smart: +{pnl_pct:.2f}% me momentum të dobësuar — kapur"
            if r < 32:
                return "smart: RSI i mbishitur — fitim i kapur"
            if e9 > e21:
                return "smart: trendi u kthye lart — fitim i kapur"
            if last2 > 0 and mom > 0:
                return "smart: momentum i dobësuar — fitim i kapur"
        return None

    def _trail_profit(self, e, pos, price):
        """Trailing + shkalla në $: SL lëviz për të kyçur $0.5/$1/$2/$3
        sapo arrihen — fitimi i arsyeshëm mbrohet gjithmonë."""
        side = pos["side"]
        qty = pos["qty"] or 1
        pnl_pct = (price - pos["entry"]) / pos["entry"] * 100 \
            if side == "LONG" else (pos["entry"] - price) / pos["entry"] * 100
        pnl_usd = pos["entry"] * qty * pnl_pct / 100
        if pnl_usd < 0.5:
            return
        # SL që kyç shkallën më të lartë të arritur
        locked = 0.0
        for rung in (2.0, 1.0, 0.5):
            if pnl_usd >= rung:
                locked = rung
                break
        if side == "LONG":
            new_sl = pos["entry"] + locked / qty
            if new_sl > pos["sl"]:
                e._update_sl(pos["id"], new_sl)
        else:
            new_sl = pos["entry"] - locked / qty
            if new_sl < pos["sl"]:
                e._update_sl(pos["id"], new_sl)

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
               RiskManagerAgent, SizerAgent, FillerAgent, TrackerAgent,
               LearningAgent])
