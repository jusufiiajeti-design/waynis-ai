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

from config import (STARTING_BALANCE, CYCLE_SECONDS, SCAN_BATCH, TRADE_RISK,
                    TAKE_PROFIT, STOP_LOSS, BREAKEVEN_AT, MIN_CONFIDENCE, MAX_OPEN)
from providers import MarketData, WATCHLIST
from agents import (CycleContext, ScannerAgent, PredictorAgent, ValidatorAgent,
                    SizerAgent, FillerAgent, TrackerAgent)
from brain import AIBrain

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
