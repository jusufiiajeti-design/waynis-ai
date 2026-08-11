"""Test i MURIT — rregulli i ri: muri kyç VETËM kur fitimi > humbja (tarifat rrethore).
Çdo kyçje e murit duhet të jetë fitim neto, kurrë humbje."""
import os, sys, asyncio, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import engine as eng
from providers import MarketData
from config import STARTING_BALANCE, FEE_RATE

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
        closed.append((pos["symbol"], pos["pnl"], reason))
    e._close_trade = fake_close

    fails = []

    # ===== A: eq nen fillestar => RIPERDORIM, asgje nuk preket
    closed.clear(); TICKERS.clear()
    e.wall_floor = STARTING_BALANCE
    seed(STARTING_BALANCE - 12.0, [(1, "XLM-USDT", "SHORT", 0.1610, 564.0, 0.156, 0.164)])
    TICKERS["XLM-USDT"] = {"price": 0.16086}   # +$0.079 fitim bruto
    await e.check_wall()
    ok = len(closed) == 0
    print(f"A) eq 9988 < fillestar: asnje mbyllje? {'OK' if ok else 'DEFEKT: '+str(closed)}")
    if not ok: fails.append("A")

    # ===== B: eq mbi fillestar, nen mur => kyç vetem kur fitim > tarifa
    closed.clear(); TICKERS.clear()
    e.wall_floor = 10034.0
    # XLM: entry 0.1610, qty 564 -> tarifat = (0.161*564 + price*564)*0.001 ~ $0.182
    # BNB: entry 609, qty 0.15 -> tarifat = (609*0.15 + 619*0.15)*0.001 = $0.184
    seed(10020.0, [
        (1, "XLM-USDT", "SHORT", 0.1610, 564.0, 0.156, 0.164),   # +$0.18 FITIM == tarifa -> JO (jo me i madh)
        (2, "BNB-USDT",  "LONG",  609.0,  0.15,  627.0, 596.0),  # +$1.50 >> $0.184 -> KYÇET
        (3, "BTC-USDT",  "LONG", 64000.0, 0.01, 66000.0, 63000.0),# humbje -> s'preket
    ])
    TICKERS["XLM-USDT"] = {"price": 0.160681}  # (0.1610-0.160681)*564 = +$0.18
    TICKERS["BNB-USDT"] = {"price": 619.0}     # (619-609)*0.15 = +$1.50
    TICKERS["BTC-USDT"] = {"price": 63000.0}   # -$10
    await e.check_wall()
    got = sorted((s, p) for s, p, r in closed)
    exp = [("BNB-USDT", 1.5)]
    ok = got == exp
    print(f"B) +$1.50 kyçet; +$0.18 (== tarifa) jo; -$10 jo? {'OK' if ok else 'DEFEKT: '+str(got)}")
    if not ok: fails.append("B")

    # ===== C: fitim pak mbi tarifa -> kyçet dhe eshte neto pozitiv
    closed.clear(); TICKERS.clear()
    e.wall_floor = 10010.0
    seed(10005.0, [(1, "BNB-USDT", "LONG", 609.0, 0.15, 627.0, 596.0)])
    TICKERS["BNB-USDT"] = {"price": 611.0}   # +$0.30; tarifat=(609*0.15+611*0.15)*0.001=$0.183 -> 0.30 > 0.183 KYÇET
    await e.check_wall()
    ok = len(closed) == 1 and closed[0][1] > 0
    print(f"C) +$0.30 > tarifat $0.183: kyçet, neto +$0.12? {'OK' if ok else 'DEFEKT: '+str(closed)}")
    if not ok: fails.append("C")

    # ===== D: fitim nën tarifa -> NUK kyçet (asnje churn)
    closed.clear(); TICKERS.clear()
    e.wall_floor = 10010.0
    seed(10005.0, [(1, "BNB-USDT", "LONG", 609.0, 0.15, 627.0, 596.0)])
    TICKERS["BNB-USDT"] = {"price": 610.6}   # +$0.24 < $0.183? jo: 0.24 > 0.183... provo 610.0: +$0.15
    TICKERS["BNB-USDT"] = {"price": 610.0}   # +$0.15 < tarifat $0.183 -> JO
    await e.check_wall()
    ok = len(closed) == 0
    print(f"D) +$0.15 < tarifat $0.183: NUK kyçet (pa churn)? {'OK' if ok else 'DEFEKT: '+str(closed)}")
    if not ok: fails.append("D")

    # ===== E: muri ngrihet vetem nga bilanci (jo nga kulmi i equity)
    closed.clear(); TICKERS.clear()
    e.wall_floor = 10000.0
    seed(9999.0, [(1, "BTC-USDT", "LONG", 64000.0, 0.01, 66000.0, 63000.0)])
    TICKERS["BTC-USDT"] = {"price": 66099.0}   # +$10.99 unreal
    await e.check_wall()
    ok = e.wall_floor == 10000.0
    print(f"E) bilanci 9999: muri qendron 10000? {'OK' if ok else 'DEFEKT: '+str(e.wall_floor)}")
    if not ok: fails.append("E")

    # ===== F: fitim i madh me pozicion te vogel => kufiri varet nga madhesia
    closed.clear(); TICKERS.clear()
    e.wall_floor = 10010.0
    # pozicion i vogel: qty 0.02 BTC @ 64000 = $1280 notional, tarifat ~$0.256
    seed(10005.0, [(1, "BTC-USDT", "LONG", 64000.0, 0.02, 66000.0, 63000.0)])
    TICKERS["BTC-USDT"] = {"price": 64008.0}   # +$0.16 < tarifat $0.256 -> JO
    await e.check_wall()
    ok = len(closed) == 0
    print(f"F) +$0.16 < tarifat $0.256 (poz i madh): NUK kyçet? {'OK' if ok else 'DEFEKT: '+str(closed)}")
    if not ok: fails.append("F")

    print("\n" + ("✅ TË GJITHA TESTET KALUAN" if not fails else f"❌ DEFEKT në: {fails}"))
    sys.exit(0 if not fails else 1)

asyncio.run(main())
