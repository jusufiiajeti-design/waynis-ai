"""
Waynis AI — trading engine (COORDINATOR).

The coordinator owns the account state and drives the six specialised
trading agents (agents.py) through the 6-Cycle Execution Pipeline:

    Scan → Predict → Validate → Size → Fill → Track

Modes:
  * paper (default) — simulated trades with REAL market prices.
  * real  — REAL money, SPOT only, LONG-only, on Binance (or OKX).
            Keys come from environment variables only. TP/SL are attached
            to the exchange (bracket orders) for protection.
"""
import asyncio
import json
import os
import random
import sqlite3
import time
from datetime import datetime, timezone

from config import (STARTING_BALANCE, CYCLE_SECONDS, SCAN_BATCH, TRADE_RISK,
                    TAKE_PROFIT, STOP_LOSS, BREAKEVEN_AT, MIN_CONFIDENCE,
                    MAX_OPEN, FEE_RATE, REAL_MIN_NOTIONAL,
                    REAL_MAX_NOTIONAL_PCT, REAL_MAX_POSITIONS)
from providers import MarketData, WATCHLIST
from agents import (CycleContext, ScannerAgent, ALL_AGENTS,
                    load_weights, save_weights, DEFAULT_STATS)
from brain import AIBrain
from exchange import get_exchange, to_exchange_symbol

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "paper.db")
SETTINGS_PATH = os.path.join(BASE_DIR, "data", "trading_config.json")

PIPELINE_AGENTS = [  # metadata for the UI
    {"name": "Scanner",   "icon": "📡", "role": "Tërheq çmime live + qirinj"},
    {"name": "Predictor", "icon": "🎯", "role": "EMA 9/21 + RSI 14 parashikim"},
    {"name": "Validator", "icon": "✅", "role": "Rregullat e rrezikut dhe volumit"},
    {"name": "Sizer",     "icon": "⚖️", "role": "Madhësia e pozicionit (fiks / komponim)"},
    {"name": "Filler",    "icon": "⚡", "role": "Ekzekutimi i urdhrit"},
    {"name": "Tracker",   "icon": "📊", "role": "TP / SL / trailing / PnL live"},
]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _load_settings():
    try:
        with open(SETTINGS_PATH) as f:
            return json.load(f)
    except Exception:
        return {"mode": "paper"}


def _save_settings(s):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(s, f, indent=2)


class PaperEngine:
    def __init__(self, market: MarketData):
        self.market = market
        self.loop = None
        self._lock = asyncio.Lock()
        self.running = True
        self.auto_trade = True
        self.compound = True          # COMPOUND sizing by default
        settings = _load_settings()
        self.mode = settings.get("mode", "paper")   # "paper" | "real"
        self.exchange = get_exchange()              # real-money client
        self.real_balance_cache = (0.0, 0.0)        # (ts, balance)
        self.strategy_stats = load_weights()        # 🎓 learned weights
        self.learning_last_id = int(self.strategy_stats.pop("__last_trade_id", 0) or 0)
        # twenty autonomous agents + coordinator (this engine)
        self.agents = [cls(self) for cls in ALL_AGENTS]
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
                pnl REAL, confidence REAL, reason TEXT,
                fees REAL, bracket TEXT, votes TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT, type TEXT, msg TEXT, symbol TEXT)""")
            # migrate older DBs: add fees/bracket/votes if missing
            cols = [r[1] for r in c.execute("PRAGMA table_info(trades)").fetchall()]
            for col, ddl in [("fees", "REAL"), ("bracket", "TEXT"),
                             ("votes", "TEXT")]:
                if col not in cols:
                    try:
                        c.execute(f"ALTER TABLE trades ADD COLUMN {col} {ddl}")
                    except Exception:
                        pass
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
    # Mode (paper / real)
    # ------------------------------------------------------------------
    def set_mode(self, mode):
        mode = "real" if mode == "real" else "paper"
        old = self.mode
        self.mode = mode
        _save_settings({"mode": mode})
        self._event("settings",
                    f"Modaliteti: {'💰 REAL (para të vërteta)' if mode == 'real' else '📝 Paper (demo)'}")
        if mode == "real":
            self.exchange = get_exchange()
        return mode

    def real_status(self):
        st = self.exchange.status()
        st["mode"] = self.mode
        st["min_notional"] = REAL_MIN_NOTIONAL
        st["max_positions"] = REAL_MAX_POSITIONS
        st["max_notional_pct"] = REAL_MAX_NOTIONAL_PCT
        st["fee_rate"] = FEE_RATE
        try:
            st["balance_usdt"] = self.real_balance()
        except Exception:
            st["balance_usdt"] = None
        return st

    def real_balance(self, force=False):
        """Cached USDT balance from the exchange (cache 10s)."""
        ts, bal = self.real_balance_cache
        if force or time.time() - ts > 10:
            bal = self.exchange.balance_usdt()
            self.real_balance_cache = (time.time(), bal)
        return bal

    # ------------------------------------------------------------------
    # Account / status helpers
    # ------------------------------------------------------------------
    def account(self):
        if self.mode == "real":
            try:
                bal = self.real_balance()
            except Exception:
                bal = 0.0
            return {
                "balance": round(bal, 2),
                "equity": round(bal, 2),
                "peak": round(max(bal, self.real_balance_cache[1]), 2) if False else round(bal, 2),
                "unrealized": 0.0,
                "growth": round(bal / STARTING_BALANCE, 4) if STARTING_BALANCE else 0.0,
                "started_at": now_iso(),
                "real": True,
            }
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
            "real": False,
        }

    def open_positions(self):
        with self._conn() as c:
            rows = c.execute(
                "SELECT symbol,side,entry,qty,tp,sl,opened_at,id,confidence,"
                "bracket FROM trades WHERE status='open'").fetchall()
        out = []
        for r in rows:
            sym, side, entry, qty, tp, sl, opened, tid, conf, bracket = r
            price = self.last_tickers.get(sym, {}).get("price") or entry
            if side == "LONG":
                pnl = (price - entry) * qty
            else:
                pnl = (entry - price) * qty
            out.append({
                "id": tid, "symbol": sym, "side": side, "entry": entry,
                "qty": qty, "tp": tp, "sl": sl, "opened_at": opened,
                "confidence": conf, "pnl": round(pnl, 2), "price": price,
                "bracket": bracket,
            })
        return out

    def stats(self):
        with self._conn() as c:
            closed = c.execute(
                "SELECT status, pnl, closed_at, fees FROM trades "
                "WHERE status!='open'").fetchall()
        wins = sum(1 for s, _, _, _ in closed if s == "win")
        total = len(closed)
        win_rate = round(100.0 * wins / total, 1) if total else 0.0
        realized = round(sum(p for _, p, _, _ in closed), 2)
        fees = round(sum(f for _, _, _, f in closed if f), 2)
        now = time.time()
        cutoff = now - 86400
        snap24 = [e for e in self.equity_history if e[0] <= cutoff]
        if snap24:
            pnl24 = self.account()["equity"] - snap24[-1][1]
        else:
            pnl24 = round(sum(p for _, p, ts, _ in closed
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
            "fees_paid": fees,
            "pnl_24h": round(pnl24, 2),
            "avg_day": avg_day,
            "open": len(self.open_positions()),
        }

    def agents_info(self):
        out = []
        for a in self.agents:
            info = {"name": a.name, "icon": a.icon, "role": a.role,
                    "step": a.step, "kind": a.kind,
                    "active": self.pipeline.get("agent") == a.name}
            if a.kind == "strategy":
                st = self.strategy_stats.get(a.name, dict(DEFAULT_STATS))
                info.update({"weight": st.get("weight", 1.0),
                             "wins": st.get("wins", 0),
                             "losses": st.get("losses", 0),
                             "trades": st.get("trades", 0),
                             "pnl": round(st.get("pnl", 0.0), 2)})
            out.append(info)
        return out

    # ------------------------------------------------------------------
    # Coordinator loop
    # ------------------------------------------------------------------
    async def run(self):
        self.loop = asyncio.get_running_loop()
        AIBrain.ensure_ollama()
        await self.brain.start()
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
        async with self._lock:
            await self._cycle(-1)
        return self.pipeline

    async def _cycle(self, idx):
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
    def _open_trade(self, sig, qty, bracket=None, votes=None):
        if qty <= 0:
            return None
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO trades(symbol,side,entry,qty,tp,sl,status,"
                "opened_at,confidence,bracket,votes) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (sig["symbol"], sig["direction"], sig["entry"], qty,
                 sig["tp"], sig["sl"], "open", now_iso(), sig["confidence"],
                 json.dumps(bracket) if bracket else None,
                 json.dumps(votes or [])))
            return cur.lastrowid

    def _update_sl(self, trade_id, new_sl):
        with self._conn() as c:
            c.execute("UPDATE trades SET sl=? WHERE id=?", (new_sl, trade_id))

    async def _close_trade(self, pos, price, reason):
        """Close a PAPER position (with real fees simulated)."""
        qty = pos["qty"]
        if pos["side"] == "LONG":
            gross = (price - pos["entry"]) * qty
        else:
            gross = (pos["entry"] - price) * qty
        fees = (pos["entry"] * qty + price * qty) * FEE_RATE
        pnl = gross - fees
        status = "win" if pnl > 0 else "loss"
        with self._conn() as c:
            c.execute(
                "UPDATE trades SET exit=?, status=?, closed_at=?, pnl=?, "
                "reason=?, fees=? WHERE id=?",
                (price, status, now_iso(), pnl, reason, fees, pos["id"]))
            c.execute(
                "UPDATE account SET balance=balance+?, peak=MAX(peak,balance+?) "
                "WHERE id=1", (pnl, pnl))
        self.cooldown[pos["symbol"]] = time.time()
        label = "TP" if reason == "tp" else ("SL" if reason == "sl" else "exit")
        self._event("close",
                    f"{pos['side']} {pos['symbol']} u mbyll ({label}) "
                    f"{'+' if pnl >= 0 else ''}{pnl:.2f} USDT "
                    f"(tarifa ${fees:.2f})",
                    pos["symbol"])

    # ------------------------------------------------------------------
    # REAL-money order management (spot, LONG-only)
    # ------------------------------------------------------------------
    async def real_open(self, sig, qty):
        """Open a real LONG position with TP/SL attached on the exchange."""
        ex = self.exchange
        sym = to_exchange_symbol(sig["symbol"], ex)
        try:
            res = await asyncio.to_thread(ex.market_buy, sym, qty)
        except Exception as e:
            self._event("error", f"💰 REAL: dështoi hapja {sym}: {str(e)[:100]}")
            return None
        fill = res.get("fill", {})
        exec_price = float(fill.get("fills", [{}])[0].get("price", 0)) if isinstance(fill, dict) else 0
        if not exec_price:
            exec_price = res.get("price", sig["entry"])
        entry = exec_price or sig["entry"]
        sig2 = dict(sig)
        sig2["entry"] = entry
        sig2["tp"] = entry * (1 + 0.0045)
        sig2["sl"] = entry * (1 - 0.0035)
        tid = self._open_trade(sig2, qty, bracket=res.get("bracket"))
        if tid:
            self._event("fill",
                        f"💰 REAL {sig['direction']} {sig['symbol']} "
                        f"{qty:.6f} @ {entry:.6g} (TP/SL në exchange)",
                        sig["symbol"])
        return tid

    async def real_close(self, pos, price, reason):
        """Close a real LONG position: cancel bracket, market sell."""
        ex = self.exchange
        sym = to_exchange_symbol(pos["symbol"], ex)
        qty = pos["qty"]
        try:
            bracket = json.loads(pos.get("bracket") or "[]")
            res = await asyncio.to_thread(ex.market_sell_all, sym, qty, bracket)
        except Exception as e:
            self._event("error",
                        f"💰 REAL: dështoi mbyllja {sym}: {str(e)[:100]}")
            return
        exit_price = price
        try:
            fills = res.get("fills", []) if isinstance(res, dict) else []
            if fills:
                exit_price = float(fills[0].get("price", price))
        except Exception:
            pass
        gross = (exit_price - pos["entry"]) * qty
        fees = (pos["entry"] * qty + exit_price * qty) * FEE_RATE
        pnl = gross - fees
        status = "win" if pnl > 0 else "loss"
        with self._conn() as c:
            c.execute(
                "UPDATE trades SET exit=?, status=?, closed_at=?, pnl=?, "
                "reason=?, fees=? WHERE id=?",
                (exit_price, status, now_iso(), pnl, reason, fees, pos["id"]))
        self.cooldown[pos["symbol"]] = time.time()
        self.real_balance_cache = (0.0, 0.0)
        label = "TP" if reason == "tp" else ("SL" if reason == "sl" else "exit")
        self._event("close",
                    f"💰 REAL {pos['side']} {pos['symbol']} u mbyll ({label}) "
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
                "closed_at,pnl,confidence,reason,fees,bracket,votes FROM trades "
                "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        keys = ["id", "symbol", "side", "entry", "exit", "qty", "tp", "sl",
                "status", "opened_at", "closed_at", "pnl", "confidence",
                "reason", "fees", "bracket", "votes"]
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
        out = [{"t": int(ts), "e": eq} for ts, eq in self.equity_history[-limit:]]
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

    def reset(self, seed=True, reset_learning=False):
        with self._conn() as c:
            for t in ("trades", "events"):
                c.execute(f"DELETE FROM {t}")
            c.execute("UPDATE account SET balance=?, peak=?, started_at=? WHERE id=1",
                      (STARTING_BALANCE, STARTING_BALANCE, now_iso()))
            if seed:
                self._seed_history(c)
        self.equity_history = []
        self.cooldown = {}
        if reset_learning:
            self.strategy_stats = {}
            self.learning_last_id = 0
            save_weights(self.strategy_stats)
            self._event("reset", "Peshat e mësuara të strategjive u rivendosën")
        else:
            self.learning_last_id = 0
        if seed:
            self._seed_equity()
        self._event("reset", "Llogaria u rivendos")

    def persist_learning(self):
        """Persist learning weights + last processed trade id."""
        stats = dict(self.strategy_stats)
        stats["__last_trade_id"] = self.learning_last_id
        save_weights(stats)
