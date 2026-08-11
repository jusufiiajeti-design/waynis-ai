"""Test i ASHENSORIT — zëvendëson murin:
- Dyshemeja ngjitet VETËM me bilancin e realizuar (kat më kat, kurrë nuk zbret)
- Kur equity < dyshemeja (mbi fillestar): push VETËM për tregtitë e reja
- ASNJË pozicion i hapur NUK mbyllët nga ashensori — fituesit shkojnë te TP"""
import os, sys, asyncio, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import engine as eng
from providers import MarketData
from config import STARTING_BALANCE

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

    # ===== A: ashensori NUK mbyll kurrë pozicione (thelbësor!)
    closed.clear(); TICKERS.clear()
    e.elevator_floor = 10005.0
    e._elev_paused_until = 0.0
    seed(10002.0, [
        (1, "BNB-USDT", "LONG", 609.0, 0.15, 627.0, 596.0),   # +$1.50 fitim
        (2, "BTC-USDT", "LONG", 64000.0, 0.01, 66000.0, 63000.0), # -$10 humbje
    ])
    TICKERS["BNB-USDT"] = {"price": 619.0}
    TICKERS["BTC-USDT"] = {"price": 63000.0}
    await e.check_elevator()
    ok = len(closed) == 0
    print(f"A) ashensori s'mbyll asnjë pozicion (fitues e humbës)? {'OK' if ok else 'DEFEKT: '+str(closed)}")
    if not ok: fails.append("A")

    # ===== B: equity < dyshemeja (mbi fillestar) -> pause i tregtive te reja
    e._elev_paused_until = 0.0
    TICKERS.clear()
    seed(10002.0, [])
    TICKERS["BNB-USDT"] = {"price": 619.0}   # eq = 10002 (s'ka pozicione) < 10005
    await e.check_elevator()
    ok = e.is_locked() and e._elev_paused_until > 0
    print(f"B) eq 10002 < dyshemeja 10005: pause i hyrjeve? {'OK' if ok else 'DEFEKT'}")
    if not ok: fails.append("B")

    # ===== C: pasi equity rikthehet >= dyshemeja -> lirohet (por vetem pas pause-it)
    # eq >= dyshemeja -> ashensori nuk e mban paused
    e._elev_paused_until = 0.0
    TICKERS.clear()
    seed(10006.0, [])
    await e.check_elevator()
    ok = not e.is_locked()
    print(f"C) eq 10006 >= dyshemeja: s'ka pause? {'OK' if ok else 'DEFEKT'}")
    if not ok: fails.append("C")

    # ===== D: dyshemeja ngrihet VETËM nga bilanci i realizuar (jo nga kulmi i equity)
    e.elevator_floor = 10000.0
    e._elev_paused_until = 0.0
    TICKERS.clear()
    seed(9999.0, [(1, "BTC-USDT", "LONG", 64000.0, 0.01, 66000.0, 63000.0)])
    TICKERS["BTC-USDT"] = {"price": 66099.0}   # +$10.99 unreal, eq 10009.99
    await e.check_elevator()
    ok = e.elevator_floor == 10000.0
    print(f"D) bilanci 9999 (eq 10010 me unreal): dyshemeja qendron 10000? {'OK' if ok else 'DEFEKT: '+str(e.elevator_floor)}")
    if not ok: fails.append("D")
    # D2: pasi bilanci kalon 10001 -> dyshemeja ngrihet
    seed(10002.0, []); TICKERS.clear()
    await e.check_elevator()
    ok = e.elevator_floor == 10002.0
    print(f"D2) bilanci 10002 -> dyshemeja 10002? {'OK' if ok else 'DEFEKT: '+str(e.elevator_floor)}")
    if not ok: fails.append("D2")

    # ===== E: eq < fillestar -> asnjë pause (rikuperim i plotë)
    e.elevator_floor = 10000.0
    e._elev_paused_until = 0.0
    TICKERS.clear()
    seed(9988.0, [(1, "XLM-USDT", "SHORT", 0.1610, 564.0, 0.156, 0.164)])
    TICKERS["XLM-USDT"] = {"price": 0.16086}   # +$0.08, eq 9988.08 < 10000
    await e.check_elevator()
    ok = not e.is_locked()
    print(f"E) eq 9988 < fillestar: s'ka pause (rikuperim)? {'OK' if ok else 'DEFEKT'}")
    if not ok: fails.append("E")

    # ===== F: dyshemeja ngjitet "kat më kat" — bllokohet vetëm në hapat $1
    e.elevator_floor = 10000.0
    e._elev_paused_until = 0.0
    seed(10000.4, [])   # +$0.40 fitim — ende nën hapin $1
    TICKERS.clear()
    await e.check_elevator()
    ok = e.elevator_floor == 10000.0
    print(f"F) bilanci 10000.40 (< +$1): dyshemeja qendron 10000? {'OK' if ok else 'DEFEKT: '+str(e.elevator_floor)}")
    if not ok: fails.append("F")

    print("\n" + ("✅ TË GJITHA TESTET KALUAN" if not fails else f"❌ DEFEKT në: {fails}"))
    sys.exit(0 if not fails else 1)

asyncio.run(main())
