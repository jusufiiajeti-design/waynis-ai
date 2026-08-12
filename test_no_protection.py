"""Test: pa asnjë sistem mbrojtës — asnjë mekanizëm nuk mbyll pozicione,
asnjë pause, tregtimi i lirë TP 3% / SL 2%."""
import os, sys, asyncio, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import engine as eng
from providers import MarketData
from config import (STARTING_BALANCE, EQUITY_LOCK_ENABLED,
                    PROFIT_LOCK_STEP_USD)
import config

tmpdir = tempfile.mkdtemp()
eng.DB_PATH = os.path.join(tmpdir, "test.db")
eng.BASE_DIR = tmpdir
os.environ.setdefault("TURSO_URL", "")
os.environ.setdefault("TURSO_TOKEN", "")

TICKERS = {}

async def main():
    mkt = MarketData()
    e = eng.PaperEngine(mkt)

    with e._conn() as c:
        c.execute("INSERT OR REPLACE INTO account(id,balance,peak,started_at) VALUES(1,?,?,datetime('now'))",
                  (STARTING_BALANCE, STARTING_BALANCE))

    def seed(balance, trades):
        with e._conn() as c:
            c.execute("DELETE FROM trades")
            c.execute("UPDATE account SET balance=?, peak=MAX(peak,?) WHERE id=1", (balance, balance))
            for t in trades:
                c.execute("""INSERT INTO trades(id,symbol,side,entry,qty,tp,sl,opened_at,status,confidence)
                             VALUES(?,?,?,?,?,?,?,datetime('now'),'open',94)""", t)

    async def fake_tickers():
        return dict(TICKERS)
    mkt.fetch_all_tickers = fake_tickers
    closed = []
    async def fake_close(pos, price, reason):
        closed.append((pos["symbol"], reason))
    e._close_trade = fake_close

    fails = []

    # 0. Konfigurimi: mbrojtjet OFF
    print(f"EQUITY_LOCK_ENABLED = {EQUITY_LOCK_ENABLED} | PROFIT_LOCK_STEP_USD = {PROFIT_LOCK_STEP_USD}")
    ok = EQUITY_LOCK_ENABLED == False and PROFIT_LOCK_STEP_USD == 0.0
    print(f"0) mbrojtjet çaktivizuar? {'OK' if ok else 'DEFEKT'}")
    if not ok: fails.append("0")

    # 1. check_profit_lock nuk mbyll asgjë (edhe me eq nën kulm)
    closed.clear(); TICKERS.clear()
    seed(9980.0, [(1, "BTC-USDT", "LONG", 64000.0, 0.01, 66000.0, 63000.0)])
    TICKERS["BTC-USDT"] = {"price": 66099.0}   # +$10.99, eq 9990.99 < peak
    await e.check_profit_lock()
    ok = len(closed) == 0 and not e.is_locked()
    print(f"1) profit-lock s'mbyll asgjë, s'ka pause? {'OK' if ok else 'DEFEKT: '+str(closed)}")
    if not ok: fails.append("1")

    # 2. asnjë check_elevator/check_wall nuk ekziston (u hoqën)
    ok = not hasattr(e, "check_elevator") and not hasattr(e, "check_wall") \
         and not hasattr(e, "wall_floor") and not hasattr(e, "elevator_floor")
    print(f"2) muri/ashensori s'ekzistojnë më? {'OK' if ok else 'DEFEKT'}")
    if not ok: fails.append("2")

    # 3. is_locked = False (asnjë bllokim)
    ok = not e.is_locked()
    print(f"3) is_locked False? {'OK' if ok else 'DEFEKT'}")
    if not ok: fails.append("3")

    # 4. cikli kryesor nuk ka asnjë thirrje mbrojtjeje (funksionon vetëm Scanner)
    #    verifikojmë që asnjë pozicion s'mbyllët nga ndonjë mekanizëm
    closed.clear(); TICKERS.clear()
    seed(10020.0, [(1, "BNB-USDT", "LONG", 609.0, 0.15, 627.0, 596.0)])  # +$1.50
    TICKERS["BNB-USDT"] = {"price": 619.0}
    # simuloj nje cikel te plote te pjesshem: vetem ato qe ekzistojne
    await e.check_profit_lock()
    ok = len(closed) == 0
    print(f"4) pozicioni +$1.50 nuk preket nga asnjë mbrojtje? {'OK' if ok else 'DEFEKT: '+str(closed)}")
    if not ok: fails.append("4")

    # 5. _close_trade nuk thirr _raise_elevator (nuk ekziston)
    ok = not hasattr(e, "_raise_elevator") and not hasattr(e, "_raise_wall")
    print(f"5) metodat e murit/ashensorit s'ekzistojnë? {'OK' if ok else 'DEFEKT'}")
    if not ok: fails.append("5")

    print("\n" + ("✅ TË GJITHA TESTET KALUAN" if not fails else f"❌ DEFEKT në: {fails}"))
    sys.exit(0 if not fails else 1)

asyncio.run(main())
