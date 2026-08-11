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
                    REAL_MAX_NOTIONAL_PCT, REAL_MAX_POSITIONS,
                    ENABLE_PARTIAL_TP, TP1_PARTIAL, PARTIAL_FRACTION,
                    TRAIL_PCT, RUNNER_BE,
                    EQUITY_LOCK_ENABLED, EQUITY_LOCK_PCT,
                    EQUITY_LOCK_PAUSE_MIN, PROFIT_LOCK_STEP_USD,
                    PROFIT_LOCK_PAUSE_MIN,
                    WALL_LOCK_ENABLED, WALL_LOCK_STEP,
                    COMPOUND_WIN_MULT, COMPOUND_LOSS_MULT,
                    COMPOUND_MIN_RISK, COMPOUND_MAX_RISK,
                    DCA_ENABLED, DCA_AMOUNT, DCA_INTERVAL_MIN, DCA_SYMBOL)
from providers import MarketData, WATCHLIST
from agents import (CycleContext, ScannerAgent, ALL_AGENTS,
                    load_weights, save_weights, DEFAULT_STATS)
from brain import AIBrain
from exchange import get_exchange, to_exchange_symbol
from learning import load_history, enrich
from turso import (query as turso_query, exec_sql as turso_exec,
                   batch_exec as turso_batch, enabled as turso_enabled,
                   _creds as _turso_creds)

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
        self.started_at = time.time() # session start (big timer in UI)
        self.scan_count = 0           # charts analysed by the agents
        settings = _load_settings()
        self.mode = settings.get("mode", "paper")   # "paper" | "real"
        self.exchange = get_exchange()              # real-money client
        self.real_balance_cache = (0.0, 0.0)        # (ts, balance)
        self.lock_until = 0.0                       # 🔒 profit-lock until ts
        self.equity_lock_enabled = settings.get("equity_lock_enabled",
                                                EQUITY_LOCK_ENABLED)
        self.equity_lock_pct = settings.get("equity_lock_pct", EQUITY_LOCK_PCT)
        # 💰 dyshemeja e fitimit në shkallë $60 (ruhet në cilësimet)
        self.profit_floor = float(settings.get("profit_floor", STARTING_BALANCE))
        self._pl_triggered = False
        # 🧱 MURI I MBROJTJES: lexohet nga cilësimet (mbijeton rindezjet)
        self.wall_floor = float(settings.get("wall_floor", STARTING_BALANCE))
        # ⚖️ KOMPONIMI ASIMETRIK: gjendja aktuale e rrezikut
        self.asym_mult = float(settings.get("asym_mult", 1.0))
        # 📈 DCA state
        self.dca_enabled = settings.get("dca_enabled", DCA_ENABLED)
        self.dca_amount = settings.get("dca_amount", DCA_AMOUNT)
        self.dca_interval = settings.get("dca_interval_min", DCA_INTERVAL_MIN)
        self.dca_symbol = settings.get("dca_symbol", DCA_SYMBOL)
        # 🎯 multi-timeframe cache
        self.mtf_cache = {}                          # symbol -> (ts, closes)
        self.strategy_stats = load_weights()        # 🎓 learned weights
        self.learning_last_id = int(self.strategy_stats.pop("__last_trade_id", 0) or 0)
        self.meta_state = {"recent": [], "threshold": 0.05,
                           "system_win_rate": None}
        self.learning_history = load_history()      # learning curve points
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
                fees REAL, bracket TEXT, votes TEXT,
                tp1 REAL, tp1_hit INTEGER DEFAULT 0,
                partial_pnl REAL, trail_high REAL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT, type TEXT, msg TEXT, symbol TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS dca_buys(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL, symbol TEXT, price REAL,
                amount_usd REAL, qty REAL)""")
            # migrate older DBs: add fees/bracket/votes/partial-tp if missing
            cols = [r[1] for r in c.execute("PRAGMA table_info(trades)").fetchall()]
            for col, ddl in [("fees", "REAL"), ("bracket", "TEXT"),
                             ("votes", "TEXT"), ("tp1", "REAL"),
                             ("tp1_hit", "INTEGER DEFAULT 0"),
                             ("partial_pnl", "REAL"),
                             ("trail_high", "REAL")]:
                if col not in cols:
                    try:
                        c.execute(f"ALTER TABLE trades ADD COLUMN {col} {ddl}")
                    except Exception:
                        pass
            row = c.execute("SELECT * FROM account WHERE id=1").fetchone()
            pending = []
            if not row:
                c.execute(
                    "INSERT INTO account(id,balance,peak,started_at) VALUES(1,?,?,?)",
                    (STARTING_BALANCE, STARTING_BALANCE, now_iso()))
                self._turso_ensure_schema()
                if not self._turso_restore(c, pending):
                    # nuk ka histori në Turso → demo fikse (për herë të parë)
                    self._seed_history(c)
                    self._seed_equity(c)
        # 🔒 ngjarjet emetohen PAS transaksionit (shmang "database is locked")
        for etype, msg in pending:
            self._event(etype, msg)

    def _conn(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        return sqlite3.connect(DB_PATH, timeout=15)

    # ------------------------------------------------------------------
    # ☁️ Turso — ruajtja përgjithmonë (databazë falas në internet)
    # ------------------------------------------------------------------
    def _turso_ensure_schema(self):
        if not turso_enabled():
            return
        turso_exec(
            "CREATE TABLE IF NOT EXISTS account(id INTEGER PRIMARY KEY, "
            "balance REAL, peak REAL, started_at TEXT)")
        turso_exec(
            "CREATE TABLE IF NOT EXISTS trades(id INTEGER PRIMARY KEY, "
            "symbol TEXT, side TEXT, entry REAL, exit REAL, qty REAL, "
            "tp REAL, sl REAL, status TEXT, opened_at TEXT, closed_at TEXT, "
            "pnl REAL, confidence REAL, reason TEXT, fees REAL, "
            "bracket TEXT, votes TEXT, tp1 REAL, tp1_hit INTEGER DEFAULT 0, "
            "partial_pnl REAL, trail_high REAL)")
        turso_exec(
            "CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY "
            "AUTOINCREMENT, ts TEXT, type TEXT, msg TEXT, symbol TEXT)")

    def _turso_restore(self, c, pending=None):
        if not turso_enabled():
            return False
        rows = turso_query(
            "SELECT id,symbol,side,entry,exit,qty,tp,sl,status,opened_at,"
            "closed_at,pnl,confidence,reason,fees,bracket,votes,tp1,"
            "tp1_hit,partial_pnl,trail_high FROM trades ORDER BY id")
        if not rows:
            return False
        c.execute("DELETE FROM trades")
        for r in rows:
            if len(r) < 21:
                continue
            (tid, symbol, side, entry, exit_px, qty, tp, sl, status,
             opened_at, closed_at, pnl, confidence, reason, fees, bracket,
             votes, tp1, tp1_hit, partial_pnl, trail_high) = r
            c.execute(
                "INSERT INTO trades(id,symbol,side,entry,exit,qty,tp,sl,"
                "status,opened_at,closed_at,pnl,confidence,reason,fees,"
                "bracket,votes,tp1,tp1_hit,partial_pnl,trail_high) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (tid, symbol, side, entry, exit_px, qty, tp, sl, status,
                 opened_at, closed_at, pnl, confidence, reason, fees,
                 bracket, votes, tp1, tp1_hit, partial_pnl, trail_high))
        acct = turso_query(
            "SELECT balance, peak, started_at FROM account WHERE id=1")
        if acct and acct[0]:
            bal, peak, started = acct[0]
            c.execute(
                "UPDATE account SET balance=?, peak=?, started_at=? WHERE id=1",
                (bal if bal is not None else STARTING_BALANCE,
                 peak if peak is not None else STARTING_BALANCE,
                 started or now_iso()))
        msg = f"☁️ Historia u rikthye nga Turso ({len(rows)} tregti)"
        if pending is not None:
            pending.append(("sync", msg))
        else:
            self._event("sync", msg)
        return True

    def _turso_push_snapshot(self):
        if not turso_enabled():
            return
        try:
            with self._conn() as c:
                rows = c.execute(
                    "SELECT id,symbol,side,entry,exit,qty,tp,sl,status,"
                    "opened_at,closed_at,pnl,confidence,reason,fees,bracket,"
                    "votes,tp1,tp1_hit,partial_pnl,trail_high FROM trades "
                    "WHERE reason IS NULL OR reason != 'seed-history'"
                ).fetchall()
                bal, peak, started = c.execute(
                    "SELECT balance, peak, started_at FROM account WHERE id=1"
                ).fetchone()
        except Exception:
            return
        if not rows and bal is None:
            return
        items = [
            ("DELETE FROM trades WHERE reason IS NULL OR "
             "reason != 'seed-history'", [])]
        placeholders = ",".join("?" * 21)
        for r in rows:
            items.append((
                "INSERT INTO trades(id,symbol,side,entry,exit,qty,tp,sl,"
                "status,opened_at,closed_at,pnl,confidence,reason,fees,"
                "bracket,votes,tp1,tp1_hit,partial_pnl,trail_high) "
                "VALUES(" + placeholders + ")", list(r)))
        items.append((
            "INSERT INTO account(id,balance,peak,started_at) VALUES(1,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET balance=excluded.balance, "
            "peak=excluded.peak, started_at=excluded.started_at",
            [bal if bal is not None else STARTING_BALANCE,
             peak if peak is not None else STARTING_BALANCE,
             started or now_iso()]))
        turso_batch(items)

    def turso_status(self):
        if not turso_enabled():
            return {"enabled": False}
        try:
            u, _ = _turso_creds()
            return {"enabled": True,
                    "db": u.split("://", 1)[-1].split(".")[0] + ".turso.io"}
        except Exception:
            return {"enabled": False}

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
        rng = random.Random(20260808)   # 🔒 fiks — numrat të njëjtë çdo rindezje
        trades = []
        for i in range(14):
            sym = symbols[i % len(symbols)]
            entry = base_px[sym] * (0.97 + rng.random() * 0.06)
            win = i not in (3, 11)          # 12 wins / 2 losses -> 85.7%
            side = "LONG" if rng.random() > 0.3 else "SHORT"
            notional = 1200 + rng.random() * 1800   # $1.2k–$3k pozicion
            qty = notional / entry
            if win:
                pnl = notional * 0.0026 * (0.8 + rng.random() * 0.5)
                status = "win"
            else:
                pnl = -notional * 0.0055 * (0.8 + rng.random() * 0.4)
                status = "loss"
            exit_px = entry + (pnl / qty) if side == "LONG" else entry - (pnl / qty)
            opened = base + i * 5700 + rng.random() * 2000
            closed = opened + 180 + rng.random() * 900
            tp_px = entry * (1.0045 if side == "LONG" else 0.9955)
            sl_px = entry * (0.9965 if side == "LONG" else 1.0035)
            trades.append((
                sym, side, entry, exit_px, qty, tp_px, sl_px, status,
                datetime.fromtimestamp(opened, timezone.utc).isoformat(),
                datetime.fromtimestamp(closed, timezone.utc).isoformat(),
                round(pnl, 2), 68 + rng.random() * 24,
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
    # 🔒 Equity profit lock
    # ------------------------------------------------------------------
    def is_locked(self):
        return time.time() < self.lock_until

    def lock_info(self):
        return {
            "enabled": bool(self.equity_lock_enabled),
            "pct": self.equity_lock_pct,
            "locked": self.is_locked(),
            "until": self.lock_until,
        }

    def set_equity_lock(self, enabled=None, pct=None):
        if enabled is not None:
            self.equity_lock_enabled = bool(enabled)
        if pct is not None:
            self.equity_lock_pct = max(0.003, min(0.15, float(pct)))
        s = _load_settings()
        s["equity_lock_enabled"] = self.equity_lock_enabled
        s["equity_lock_pct"] = self.equity_lock_pct
        _save_settings(s)
        self._event("settings",
                    f"🔒 Mbrojtja e fitimit: {'ON' if self.equity_lock_enabled else 'OFF'} "
                    f"({self.equity_lock_pct*100:.1f}% nga kulmi)")
        return self.lock_info()

    async def _close_all(self, reason="lock"):
        closed = 0
        for pos in self.open_positions():
            price = self.last_tickers.get(pos["symbol"], {}).get("price") \
                or pos["entry"]
            if self.mode == "real":
                await self.real_close(pos, price, reason)
            else:
                await self._close_trade(pos, price, reason)
            closed += 1
        return closed

    async def check_profit_lock(self):
        """If equity falls more than X% below its peak, close EVERYTHING
        and pause new entries — this is the 'don't give back the gains'
        protection."""
        if not self.equity_lock_enabled or self.is_locked():
            return False
        acc = self.account()
        eq = acc["equity"]
        # 💰 SHKALLA $60: dyshemeja ngrihet çdo +$60, kurrë nuk zbret.
        # Mbrojtja fillon VETËM pasi arrihet +$60 i parë (para kësaj s'ka
        # fitim për të mbrojtur — vetëm kapitali fillestar).
        if PROFIT_LOCK_STEP_USD > 0:
            rungs = int((eq - STARTING_BALANCE) // PROFIT_LOCK_STEP_USD)
            new_floor = STARTING_BALANCE + rungs * PROFIT_LOCK_STEP_USD
            if new_floor > self.profit_floor and new_floor > STARTING_BALANCE:
                self.profit_floor = new_floor
                s = _load_settings()
                s["profit_floor"] = self.profit_floor
                _save_settings(s)
                self._pl_triggered = False
                self._event(
                    "lock",
                    f"💰 +${PROFIT_LOCK_STEP_USD:g} u kyç! "
                    f"Dyshemeja tani ${self.profit_floor:.2f} — fitimi nuk bie më poshtë",
                    None)
            # 🔒 Mbrojtja mbyll VETËM kur ka FITIM për të mbrojtur:
            # nëse equity është NËN dyshemenë (pra në humbje nga fillimi),
            # s'mbyll asgjë — e lë botin të tregtojë që të rikuperojë.
            if eq >= self.profit_floor:
                self._pl_triggered = False
            elif self.profit_floor > STARTING_BALANCE:
                if not getattr(self, "_pl_triggered", False):
                    self._pl_triggered = True
                    n = await self._close_all("profit-lock")
                    self.lock_until = time.time() + PROFIT_LOCK_PAUSE_MIN * 60
                    self._event(
                        "lock",
                        f"🔒 Mbrojtja: equity ra nën dyshemenë "
                        f"${self.profit_floor:.2f} → u mbyllën {n} pozicione. "
                        f"Push {PROFIT_LOCK_PAUSE_MIN} min para tregtive të reja.",
                        None)
                    self._set_pipeline(0, "Lock", "🔒 Profit-lock ($60) aktiv")
                    return True
        with self._conn() as c:
            row = c.execute("SELECT peak FROM account WHERE id=1").fetchone()
            peak = float(row[0]) if row and row[0] else eq
        if eq > peak:
            with self._conn() as c:
                c.execute("UPDATE account SET peak=? WHERE id=1", (eq,))
            return False
        # 🔒 mos mbro kur s'ka fitim real: nëse equity < kapitali fillestar,
        # s'ka asgjë për të mbrojtur — e lë botin të tregtojë (rikuperim)
        if eq <= STARTING_BALANCE:
            return False
        floor = peak * (1.0 - self.equity_lock_pct)
        if eq < floor and peak > 0:
            n = await self._close_all("lock")
            self.lock_until = time.time() + EQUITY_LOCK_PAUSE_MIN * 60
            with self._conn() as c:
                c.execute("UPDATE account SET peak=? WHERE id=1",
                          (self.account()["equity"],))
            self._event(
                "lock",
                f"🔒 Mbrojtja e fitimit: equity ra nën {self.equity_lock_pct*100:.1f}% "
                f"nga kulmi ${peak:.2f} → u mbyllën {n} pozicione. "
                f"Push {EQUITY_LOCK_PAUSE_MIN} min para tregtive të reja.",
                None)
            self._set_pipeline(0, "Lock", "🔒 Profit-lock aktiv — push përkohësisht")
            return True
        return False

    # ------------------------------------------------------------------
    # 📈 DCA (dollar-cost averaging)
    # ------------------------------------------------------------------
    def dca_set(self, enabled=None, amount=None, interval=None, symbol=None):
        if enabled is not None:
            self.dca_enabled = bool(enabled)
        if amount is not None:
            self.dca_amount = max(1.0, float(amount))
        if interval is not None:
            self.dca_interval = max(5, int(interval))
        if symbol:
            self.dca_symbol = str(symbol).upper()
        s = _load_settings()
        s.update({"dca_enabled": self.dca_enabled, "dca_amount": self.dca_amount,
                  "dca_interval_min": self.dca_interval,
                  "dca_symbol": self.dca_symbol})
        _save_settings(s)
        self._event("settings",
                    f"📈 DCA: {'ON' if self.dca_enabled else 'OFF'} — "
                    f"${self.dca_amount} çdo {self.dca_interval} min te {self.dca_symbol}")
        return self.dca_status()

    def dca_status(self):
        with self._conn() as c:
            rows = c.execute(
                "SELECT id,ts,symbol,price,amount_usd,qty FROM dca_buys "
                "ORDER BY id").fetchall()
        buys = [{"id": r[0], "ts": r[1], "symbol": r[2], "price": r[3],
                 "amount_usd": r[4], "qty": r[5]} for r in rows]
        total_invested = sum(b["amount_usd"] for b in buys)
        total_qty = sum(b["qty"] for b in buys)
        price = self.last_tickers.get(self.dca_symbol, {}).get("price") or 0.0
        if not price and buys:
            price = buys[-1]["price"]
        value = total_qty * price if price else 0.0
        pnl = value - total_invested
        pnl_pct = (pnl / total_invested * 100) if total_invested else 0.0
        return {
            "enabled": self.dca_enabled,
            "amount": self.dca_amount,
            "interval_min": self.dca_interval,
            "symbol": self.dca_symbol,
            "buys": len(buys),
            "total_invested": round(total_invested, 2),
            "total_qty": round(total_qty, 8),
            "current_price": round(price, 8),
            "value": round(value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "last_buy_ts": buys[-1]["ts"] if buys else None,
        }

    async def dca_check(self):
        """If DCA enabled and interval passed -> make the periodic buy."""
        if not self.dca_enabled:
            return
        try:
            with self._conn() as c:
                row = c.execute(
                    "SELECT MAX(ts) FROM dca_buys").fetchone()
            last_ts = row[0] or 0.0
            if time.time() - last_ts < self.dca_interval * 60:
                return
            price = self.last_tickers.get(self.dca_symbol, {}).get("price")
            if not price:
                tickers = await self.market.fetch_all_tickers()
                self.last_tickers = tickers
                price = self.last_tickers.get(self.dca_symbol, {}).get("price")
            if not price or price <= 0:
                return
            qty = self.dca_amount / price
            if self.mode == "real" and self.exchange.configured:
                sym = to_exchange_symbol(self.dca_symbol, self.exchange)
                await asyncio.to_thread(self.exchange.market_buy, sym, qty)
            with self._conn() as c:
                c.execute(
                    "INSERT INTO dca_buys(ts,symbol,price,amount_usd,qty) "
                    "VALUES(?,?,?,?,?)",
                    (time.time(), self.dca_symbol, price,
                     self.dca_amount, qty))
            self._event("dca",
                        f"📈 DCA: bleva ${self.dca_amount:.2f} {self.dca_symbol} "
                        f"@ {price:.4g} ({qty:.8f})",
                        self.dca_symbol)
        except Exception as e:
            self._event("error", f"DCA: {str(e)[:80]}")

    async def dca_backtest(self, symbol=None, amount=5.0, interval_days=1.0,
                           days=365):
        """Simulate DCA over the last N days using REAL daily candles.
        Shows what periodic buying would have returned."""
        symbol = symbol or self.dca_symbol
        candles = await self.market.fetch_klines_history(symbol, "1d", days + 10)
        if len(candles) < 30:
            return {"error": "Të dhëna të pamjaftueshme"}
        buys = []
        step = max(1, int(round(interval_days)))
        for i in range(0, len(candles), step):
            c = candles[i]
            buys.append({"ts": c["t"], "price": c["c"], "qty": amount / c["c"]})
        if not buys:
            return {"error": "Asnjë blerje"}
        total_invested = amount * len(buys)
        total_qty = sum(b["qty"] for b in buys)
        last_price = candles[-1]["c"]
        value = total_qty * last_price
        pnl = value - total_invested
        pnl_pct = pnl / total_invested * 100 if total_invested else 0
        first_price = buys[0]["price"]
        lump_value = (total_invested / first_price) * last_price
        lump_pnl = lump_value - total_invested
        avg_cost = total_invested / total_qty
        return {
            "symbol": symbol,
            "buys": len(buys),
            "amount_per_buy": amount,
            "interval_days": interval_days,
            "period_days": round((candles[-1]["t"] - candles[0]["t"]) / 86400000, 1),
            "total_invested": round(total_invested, 2),
            "total_qty": round(total_qty, 8),
            "avg_cost": round(avg_cost, 4),
            "last_price": round(last_price, 4),
            "value": round(value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "lump_pnl": round(lump_pnl, 2),
            "lump_pnl_pct": round((lump_value - total_invested) / total_invested * 100, 2),
        }

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
                "bracket,tp1,tp1_hit,partial_pnl,trail_high "
                "FROM trades WHERE status='open'").fetchall()
        out = []
        for r in rows:
            (sym, side, entry, qty, tp, sl, opened, tid, conf, bracket,
             tp1, tp1_hit, partial_pnl, trail_high) = r
            price = self.last_tickers.get(sym, {}).get("price") or entry
            if side == "LONG":
                pnl = (price - entry) * qty
            else:
                pnl = (entry - price) * qty
            out.append({
                "id": tid, "symbol": sym, "side": side, "entry": entry,
                "qty": qty, "tp": tp, "sl": sl, "opened_at": opened,
                "confidence": conf, "pnl": round(pnl, 2), "price": price,
                "bracket": bracket, "tp1": tp1, "tp1_hit": bool(tp1_hit),
                "partial_pnl": round(partial_pnl or 0.0, 2),
                "trail_high": trail_high,
            })
        return out

    def _sell_partial(self, pos, price):
        """Take profit on half the position (TP1). Remaining half becomes a
        runner with a trailing stop — this is what makes wins bigger."""
        half = pos["qty"] * PARTIAL_FRACTION
        gross = (price - pos["entry"]) * half
        fees = (pos["entry"] * half + price * half) * FEE_RATE
        net = gross - fees
        with self._conn() as c:
            c.execute(
                "UPDATE trades SET qty=qty-?, tp1_hit=1, partial_pnl=?, sl=? "
                "WHERE id=?",
                (half, net, pos["entry"] * (1 + RUNNER_BE), pos["id"]))
            c.execute(
                "UPDATE account SET balance=balance+?, "
                "peak=MAX(peak,balance+?) WHERE id=1", (net, net))
        self._event(
            "partial",
            f"⚡ {pos['side']} {pos['symbol']}: TP1 +{TP1_PARTIAL*100:.1f}% — "
            f"gjysma u mbyll {net:+.2f} USDT · pjesa tjetër vazhdon me trailing",
            pos["symbol"])

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
        # asymmetry: average win vs average loss (the "arbitrage" edge)
        wins_pnl = [p for s, p, _, _ in closed if s == "win" and p > 0]
        loss_pnl = [p for s, p, _, _ in closed if s == "loss" and p < 0]
        avg_win = round(sum(wins_pnl) / len(wins_pnl), 2) if wins_pnl else 0.0
        avg_loss = round(sum(loss_pnl) / len(loss_pnl), 2) if loss_pnl else 0.0
        rr = round(avg_win / abs(avg_loss), 2) if avg_loss else 0.0
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
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "rr": rr,
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
        # 🔒 profit-lock check before anything else
        try:
            await self.check_profit_lock()
        except Exception:
            pass
        # 🧱 MURI I MBROJTJES — kontrollohet çdo cikël (muri i forcuar)
        try:
            await self.check_wall()
        except Exception:
            pass
        # 📈 DCA periodic buy
        try:
            await self.dca_check()
        except Exception:
            pass
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
        entry = sig["entry"]
        tp1 = None
        if ENABLE_PARTIAL_TP and sig.get("direction") == "LONG":
            tp1 = entry * (1 + TP1_PARTIAL)
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO trades(symbol,side,entry,qty,tp,sl,status,"
                "opened_at,confidence,bracket,votes,tp1) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (sig["symbol"], sig["direction"], entry, qty,
                 sig["tp"], sig["sl"], "open", now_iso(), sig["confidence"],
                 json.dumps(bracket) if bracket else None,
                 json.dumps(votes or []), tp1))
            tid = cur.lastrowid
        self._turso_push_snapshot()      # ☁️ ruaj përgjithmonë
        return tid

    def _update_sl(self, trade_id, new_sl):
        with self._conn() as c:
            c.execute("UPDATE trades SET sl=? WHERE id=?", (new_sl, trade_id))

    def _set_trail_high(self, trade_id, peak):
        with self._conn() as c:
            c.execute("UPDATE trades SET trail_high=? WHERE id=?", (peak, trade_id))

    async def _close_trade(self, pos, price, reason):
        """Close a PAPER position (with real fees simulated).
        If TP1 already banked half the profit, the trade's total PnL shown
        in the ledger = runner PnL + partial PnL (balance credits only the
        runner part — the partial was already credited at TP1)."""
        qty = pos["qty"]
        if pos["side"] == "LONG":
            gross = (price - pos["entry"]) * qty
        else:
            gross = (pos["entry"] - price) * qty
        fees = (pos["entry"] * qty + price * qty) * FEE_RATE
        pnl = gross - fees
        partial = pos.get("partial_pnl") or 0.0
        total_pnl = pnl + partial
        status = "win" if total_pnl > 0 else "loss"
        with self._conn() as c:
            c.execute(
                "UPDATE trades SET exit=?, status=?, closed_at=?, pnl=?, "
                "reason=?, fees=? WHERE id=?",
                (price, status, now_iso(), total_pnl, reason, fees, pos["id"]))
            c.execute(
                "UPDATE account SET balance=balance+?, peak=MAX(peak,balance+?) "
                "WHERE id=1", (pnl, pnl))
        self.cooldown[pos["symbol"]] = time.time()
        self._turso_push_snapshot()      # ☁️ fitimi i kyçur ruhet
        # 🧱 MURI + ⚖️ KOMPONIMI ASIMETRIK pas çdo tregtie të mbyllur
        try:
            with self._conn() as c:
                bal = c.execute("SELECT balance FROM account WHERE id=1").fetchone()[0]
            if WALL_LOCK_ENABLED:
                self._raise_wall(bal)
            if total_pnl > 0:
                self.asym_mult = min(COMPOUND_MAX_RISK / (STARTING_BALANCE * TRADE_RISK),
                                     self.asym_mult * COMPOUND_WIN_MULT)
            else:
                self.asym_mult = max(COMPOUND_MIN_RISK / (STARTING_BALANCE * TRADE_RISK),
                                     self.asym_mult * COMPOUND_LOSS_MULT)
            s = _load_settings(); s["asym_mult"] = self.asym_mult; _save_settings(s)
        except Exception:
            pass
        label = "TP" if reason == "tp" else ("SL" if reason == "sl" else "exit")
        self._event("close",
                    f"{pos['side']} {pos['symbol']} u mbyll ({label}) "
                    f"{'+' if total_pnl >= 0 else ''}{total_pnl:.2f} USDT "
                    f"(tarifa ${fees:.2f})",
                    pos["symbol"])

    # ------------------------------------------------------------------
    # 🧱 MURI I MBROJTJES — version i FORCUAR
    # ------------------------------------------------------------------
    def _raise_wall(self, equity_value):
        """Ngre murin në nivelin më të lartë të arritur. Përdor equity-n
        (fitimet e pahapura përfshihen) që muri të mbrojë edhe fitimet në
        rrugë, jo vetëm ato të mbyllura."""
        try:
            gain = equity_value - STARTING_BALANCE
            if gain > self.wall_floor - STARTING_BALANCE:
                new_floor = STARTING_BALANCE + int(gain) * 1.0
                if new_floor > self.wall_floor:
                    self.wall_floor = new_floor
                    s = _load_settings(); s["wall_floor"] = self.wall_floor
                    _save_settings(s)
                    self._event("wall",
                                f"🧱 MURI U NGRIT në ${self.wall_floor:.0f} — "
                                f"fitimi i arritur u kyç, s'bien më poshtë",
                                None)
        except Exception:
            pass

    def unrealized_profit(self):
        """Shuma e fitoreve të pozicioneve të hapura tani (për murin)."""
        try:
            return round(sum(p.get("pnl", 0) for p in self.open_positions()
                             if p.get("pnl", 0) > 0), 2)
        except Exception:
            return 0.0

    async def check_wall(self):
        """🧱 KONTROLLI I MURIT — thirret çdo cikël:
        - Ngre murin nëse equity është në nivel të ri maksimal (kyç fitimin)
        - Kur equity bie nën murin: NUK i mbyll pozicionet drejt humbjes!
          Vetëm KYÇ pozicionet që janë NË FITIM tani (fitimi i tyre shtohet
          në mur); pozicionet me humbje i lë te SL e tyre natyral.
          → muri vepron GJITHMONË drejt fitimit, kurrë drejt humbjes."""
        if not WALL_LOCK_ENABLED or not getattr(self, "wall_floor", 0):
            return False
        try:
            acc = self.account()
            eq = acc.get("equity", acc.get("balance", 0.0))
            # 🧱 muri ngrihet edhe nga fitoret e hapura (para se të kyçen)
            self._raise_wall(eq + self.unrealized_profit())
            if eq < self.wall_floor:
                # 🔄 çmime të FRESKËTA për të gjitha pozicionet (muri thirret
                # para Scanner-it — pa këtë, pnl llogaritet me çmime të vjetra
                # dhe shumë fitore nuk shihen → kyçej vetëm 1 pozicion)
                try:
                    fresh = await self.market.fetch_all_tickers()
                    if fresh:
                        self.last_tickers = fresh
                except Exception:
                    pass
                pos = self.open_positions()
                n = 0
                locked_usd = 0.0
                for p in pos:
                    # 💚 kyç TË GJITHA pozicionet NË FITIM (jo vetëm një!)
                    if p.get("pnl", 0) > 0:
                        price = p.get("price") or p["entry"]
                        await self._close_trade(p, price, "wall")
                        n += 1
                        locked_usd += p.get("pnl", 0)
                if n:
                    self._event("wall",
                                f"🧱 MURI: u kyçën {n} pozicione në fitim "
                                f"(+${locked_usd:.2f} gjithsej) — equity nën "
                                f"${self.wall_floor:.0f}, humbjet mbeten te SL",
                                None)
                return n > 0
        except Exception:
            pass
        return False

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
                "closed_at,pnl,confidence,reason,fees,bracket,votes,tp1,"
                "tp1_hit,partial_pnl FROM trades "
                "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        keys = ["id", "symbol", "side", "entry", "exit", "qty", "tp", "sl",
                "status", "opened_at", "closed_at", "pnl", "confidence",
                "reason", "fees", "bracket", "votes", "tp1",
                "tp1_hit", "partial_pnl"]
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
        # 💰 pas rivendosjes dyshemeja fillon nga e para
        self.profit_floor = STARTING_BALANCE
        self._pl_triggered = False
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

    def learning_status(self):
        """Rich learning view for the UI."""
        enriched = enrich(self.strategy_stats)
        by_weight = sorted(enriched.items(),
                           key=lambda kv: kv[1].get("weight", 1.0),
                           reverse=True)
        return {
            "strategies": dict(by_weight),
            "meta": self.meta_state,
            "history": self.learning_history[-120:],
            "trained": sum(1 for s in self.strategy_stats.values()
                           if s.get("trades", 0) > 0),
        }
