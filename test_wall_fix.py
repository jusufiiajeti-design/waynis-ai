"""Test i shpejte i MURIT te ri — skenare: rikuperim, mikro-fitore, kufiri minimal."""
import os, sys, asyncio, tempfile, sqlite3
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

TICKERS = {}  # kontrollohet per cdo skenar

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
        closed.append((pos["symbol"], pos["pnl"], reason))
    e._close_trade = fake_close

    fails = []

    # ===== A: eq nen fillestar => RIPERDORIM, asgje nuk preket
    closed.clear(); TICKERS.clear()
    e.wall_floor = STARTING_BALANCE
    seed(STARTING_BALANCE - 12.0, [(1, "XLM-USDT", "SHORT", 0.1610, 564.0, 0.156, 0.164)])
    TICKERS["XLM-USDT"] = {"price": 0.16091}   # +$0.05 mikro
    await e.check_wall()
    ok = len(closed) == 0
    print(f"A) eq 9988 < fillestar: asnje mbyllje? {'OK' if ok else 'DEFEKT: '+str(closed)}")
    if not ok: fails.append("A")

    # ===== B: eq mbi fillestar, nen mur => kyç vetem FITIME REALE (>= $0.50)
    closed.clear(); TICKERS.clear()
    e.wall_floor = 10034.0
    seed(10020.0, [
        (1, "XLM-USDT", "SHORT", 0.1610, 564.0, 0.156, 0.164),   # mikro +$0.08
        (2, "BNB-USDT",  "LONG",  609.0,  0.15,  627.0, 596.0),  # real  +$1.50
        (3, "BTC-USDT",  "LONG", 64000.0, 0.01, 66000.0, 63000.0),# humbje -$10
    ])
    TICKERS["XLM-USDT"] = {"price": 0.16115}   # (0.1610-0.16115)*564 = -$0.084 ?? 
    # per +$0.08 mikro duhet SHORT me price 0.16086:
    TICKERS["XLM-USDT"] = {"price": 0.16086}   # (0.1610-0.16086)*564 = +$0.079
    TICKERS["BNB-USDT"] = {"price": 619.0}     # (619-609)*0.15 = +$1.50
    TICKERS["BTC-USDT"] = {"price": 63000.0}   # -$10
    await e.check_wall()
    got = sorted((s, p) for s, p, r in closed)
    exp = [("BNB-USDT", 1.5)]
    ok = got == exp
    print(f"B) kyçet vetem BNB +$1.50; XLM +$0.08 dhe BTC -$10 jo? {'OK' if ok else 'DEFEKT: '+str(got)}")
    if not ok: fails.append("B")

    # ===== C: kufiri minimal — +$0.49 nuk preket, +$0.51 kyçet (notional $100 -> min $0.50)
    closed.clear(); TICKERS.clear()
    e.wall_floor = 10010.0
    seed(10005.0, [
        (1, "XLM-USDT", "LONG", 1.00, 100.0, 1.03, 0.98),   # +$0.49 (0.49% e $100)
        (2, "XLM-USDT", "LONG", 0.99, 100.0, 1.02, 0.97),   # +$0.51 (0.52% e $99)
    ])
    TICKERS["XLM-USDT"] = {"price": 1.0049}   # pos1: +$0.49; pos2: (1.0049-0.99)*100=+$1.49
    # per pos2 +$0.51 duhet price 1.0049? (1.0049-0.99)*100 = 1.49 -> per +$0.51: price 0.9951
    TICKERS["XLM-USDT"] = {"price": 0.9951}   # pos1: (0.9951-1.00)*100=-$0.49 humbje! 
    # e ndryshoj: pos1 LONG entry 0.99, pos2 LONG entry 0.9900 te dyja ne 0.9951:
    with e._conn() as c:
        c.execute("UPDATE trades SET entry=0.99 WHERE id=1")
        c.execute("UPDATE trades SET entry=0.9900 WHERE id=2")
    # tani: pos1 (0.9951-0.99)*100 = +$0.51, pos2 (0.9951-0.99)*100 = +$0.51 -> te dyja mbi 0.50
    # dua njeren nen 0.50: pos2 me qty 90: (0.9951-0.99)*90 = +$0.459
    with e._conn() as c:
        c.execute("UPDATE trades SET qty=90 WHERE id=2")
    await e.check_wall()
    got = sorted((p) for s, p, r in closed)
    ok = len(got) == 1 and abs(got[0] - 0.51) < 0.01
    print(f"C) kufiri $0.50: +$0.459 jo, +$0.51 po? {'OK' if ok else 'DEFEKT: '+str(closed)}")
    if not ok: fails.append("C")

    # ===== D: muri ngrihet VETËM nga bilanci (jo nga kulmi i equity)
    closed.clear(); TICKERS.clear()
    e.wall_floor = 10000.0
    seed(9999.0, [(1, "BTC-USDT", "LONG", 64000.0, 0.01, 66000.0, 63000.0)])
    TICKERS["BTC-USDT"] = {"price": 66099.0}   # +$10.99 unreal, eq 10009.99
    await e.check_wall()
    ok = e.wall_floor == 10000.0
    print(f"D) bilanci 9999 (eq 10010 me unreal): muri qendron 10000? {'OK' if ok else 'DEFEKT: '+str(e.wall_floor)}")
    if not ok: fails.append("D")
    # D2: bilanci kalon 10002 -> ngrihet
    seed(10002.0, []); TICKERS.clear()
    await e.check_wall()
    ok = e.wall_floor == 10002.0
    print(f"D2) bilanci 10002 -> muri 10002? {'OK' if ok else 'DEFEKT: '+str(e.wall_floor)}")
    if not ok: fails.append("D2")

    # ===== E: pa churn — vetem mikro-fitime nen mur => asgje
    closed.clear(); TICKERS.clear()
    e.wall_floor = 10010.0
    seed(10005.0, [(1, "XLM-USDT", "LONG", 1.00, 100.0, 1.03, 0.98)])
    TICKERS["XLM-USDT"] = {"price": 1.0049}   # +$0.49 mikro
    await e.check_wall()
    ok = len(closed) == 0
    print(f"E) pa churn: +$0.49 nuk mbyll? {'OK' if ok else 'DEFEKT: '+str(closed)}")
    if not ok: fails.append("E")

    # ===== F: eq 9985 nen fillestar, me fitime te medha -> GJITHESESI RIPERDORIM (asgje)
    closed.clear(); TICKERS.clear()
    e.wall_floor = 10020.0
    seed(9980.0, [(1, "BNB-USDT", "LONG", 609.0, 0.15, 627.0, 596.0)])
    TICKERS["BNB-USDT"] = {"price": 619.0}   # +$1.50 por eq 9981.5 < 10000
    await e.check_wall()
    ok = len(closed) == 0
    print(f"F) eq nen fillestar me +$1.50 open: s'preket (rikuperim)? {'OK' if ok else 'DEFEKT: '+str(closed)}")
    if not ok: fails.append("F")

    print("\n" + ("✅ TË GJITHA TESTET KALUAN" if not fails else f"❌ DEFEKT në: {fails}"))
    sys.exit(0 if not fails else 1)

asyncio.run(main())
