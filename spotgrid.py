"""
Waynis AI — SPOT PYRAMIDING (paper).

Sistem i veçantë spot (LONG-only) me rregullat e sakta të strategjisë:
  • Filtri i trendit (4H): çmimi > EMA200, EMA50 > EMA200, RSI(4H) > 50
  • Hyrja (1H): çmimi > EMA20 & EMA50, RSI 55–68, volum >= 1.2×SMA20(vol),
    qiriu mbyllet mbi swing-high të fundit (breakout)
  • Pyramiding: BUY1 = 40% → BUY2 = 30% (higher-high) → BUY3 = 30% (higher-high)
    — max 3 hyrje, KURRË averaging-down
  • SL poshtë swing-low (jo % e rastit), ngrihet pas shtesave, kurrë nën
    hyrjen mesatare pas BUY2
  • Dalje graduale: +6% → shet 25%, +12% → shet 25%, pjesa → trailing 4%
  • Mbyllje e plotë: SL i prekur, ose filtri i trendit prishet (nën EMA200/EMA50<EMA200)

Kapitali: 100€ për aset (në demo 108 USDT ≈ 100€) · BTC, ETH, SOL, BNB, XRP.
Gjendja ruhet lokalisht + sinkronizohet në Turso (mbijeton rindezjet).
"""
import json
import os
import time

from strategies import ema, rsi
from config import SPOT_ENTRY_USD
import turso

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BASE_DIR, "data", "spot_state.json")

ASSETS = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT", "XRP-USDT"]

# parametra të strategjisë
TREND_BAR = "4h"          # filtër trendi
ENTRY_BAR = "1h"          # hyrje
EMA_FAST, EMA_MID, EMA_SLOW = 20, 50, 200
RSI_PERIOD = 14
VOL_SMA = 20
VOL_MULT = 1.2            # volum breakout >= 1.2 × mesatarja
RSI_LO, RSI_HI = 55.0, 68.0
SWING_LOOKBACK = 20       # qirinj për swing-high/low
BREAKOUT_BUF = 0.001      # 0.1% tampon mbi swing-high
# Kapitali $45 për aset (kërkesa e përdoruesit), hyrja $5 për shtesë
# (përdoruesi: $3–$5). $45 / $5 = deri në 9 shtesa për aset, por me rregullin
# e artë: shtohet VETËM në fitim me higher-high — kurrë averaging-down.
CAPITAL_PER_ASSET = 45.0
MAX_ENTRIES = max(1, int(CAPITAL_PER_ASSET // SPOT_ENTRY_USD)) if SPOT_ENTRY_USD else 3
SL_MAX_DIST = 0.06        # SL max 6% nga hyrja (nëse swing-low është më larg)
TP1_PCT, TP2_PCT = 6.0, 12.0
SELL_PCT = 0.25           # 25% në çdo shkallë
TRAIL_PCT = 0.04          # trailing 4%

FEE_RATE = 0.001          # 0.1% për anë (si kudo në bot)


def _new_asset_state(symbol):
    return {
        "symbol": symbol,
        "capital": CAPITAL_PER_ASSET,
        "invested": 0.0,
        "qty": 0.0,
        "avg_entry": 0.0,
        "entries": 0,
        "sl": 0.0,
        "peak": 0.0,
        "sold": 0.0,             # 0.0 | 0.25 | 0.5 (fraksion i shitur)
        "realized": 0.0,
        "fees": 0.0,
        "last_entry_high": 0.0,  # swing-high i fundit në momentin e hyrjes
        "status": "duke pritur",  # pritje | BUY1 | BUY2 | BUY3 | mbyllur
        "opened_at": None,
        "last_signal": "",
        "updated_at": None,
    }


class SpotPyramid:
    def __init__(self, market):
        self.market = market
        self.state = {}
        self.trades = []          # historiku i mbylljeve (dict)
        self._load()

    # ------------------------------------------------------------------
    # Persistence (lokal + Turso)
    # ------------------------------------------------------------------
    def _load(self):
        st = {}
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                st = json.load(f)
        except Exception:
            pass
        # Turso (cloud) ka përparësi nëse ka gjendje më të freskët
        try:
            rows = turso.query(
                "SELECT val FROM kv WHERE key='spot_state'")
            if rows and rows[0][0]:
                cloud = json.loads(rows[0][0])
                if cloud.get("_t", 0) >= st.get("_t", 0):
                    st = cloud
        except Exception:
            pass
        for sym in ASSETS:
            self.state[sym] = _new_asset_state(sym)
            if sym in st and isinstance(st[sym], dict):
                # nëse ndryshoi hyrja (p.sh. 108→45), fillo i freskët për atë aset
                if abs(st[sym].get("capital", 0) - CAPITAL_PER_ASSET) > 0.01:
                    continue
                self.state[sym].update({k: v for k, v in st[sym].items()})
        try:
            rows = turso.query("SELECT val FROM kv WHERE key='spot_trades'")
            if rows and rows[0][0]:
                self.trades = json.loads(rows[0][0])
        except Exception:
            pass

    def _save(self):
        try:
            os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
            data = {sym: s for sym, s in self.state.items()}
            data["_t"] = time.time()
            with open(STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass
        # sinkronizo në Turso (mbijeton rindezjet e Render-it)
        try:
            if turso.enabled():
                turso.exec_sql(
                    "CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, val TEXT)")
                turso.exec_sql(
                    "INSERT INTO kv(key,val) VALUES('spot_state',?) "
                    "ON CONFLICT(key) DO UPDATE SET val=excluded.val",
                    [json.dumps(data, ensure_ascii=False)])
                turso.exec_sql(
                    "INSERT INTO kv(key,val) VALUES('spot_trades',?) "
                    "ON CONFLICT(key) DO UPDATE SET val=excluded.val",
                    [json.dumps(self.trades, ensure_ascii=False)])
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Indikatorë
    # ------------------------------------------------------------------
    def _trend_ok(self, k4h, price):
        """Filtri i trendit 4H: mbi EMA200, EMA50>EMA200, RSI>50."""
        closes = [c["c"] for c in k4h]
        if len(closes) < EMA_SLOW + 5:
            return False, "jo mjaft të dhëna 4H"
        e200 = ema(closes, EMA_SLOW)[-1]
        e50 = ema(closes, EMA_MID)[-1]
        r = rsi(closes, RSI_PERIOD)
        if price <= e200:
            return False, "çmimi nën EMA200 (4H) — NO TRADE"
        if e50 <= e200:
            return False, "EMA50 nën EMA200 (4H) — NO TRADE"
        if r <= 50:
            return False, f"RSI 4H {r:.0f} ≤ 50 — NO TRADE"
        return True, f"trend OK (mbi EMA200, EMA50>EMA200, RSI {r:.0f})"

    def _entry_signal(self, k1h):
        """Sinjali 1H: mbi EMA20/50, RSI 55–68, volum ≥1.2×, breakout."""
        if len(k1h) < 30:
            return False, "jo mjaft të dhëna 1H"
        closes = [c["c"] for c in k1h]
        price = closes[-1]
        e20 = ema(closes, EMA_FAST)[-1]
        e50 = ema(closes, EMA_MID)[-1]
        r = rsi(closes, RSI_PERIOD)
        vols = [c["v"] for c in k1h]
        vol_sma = sum(vols[-VOL_SMA:]) / VOL_SMA if len(vols) >= VOL_SMA else 1
        vol_last = vols[-1]
        prior_high = max(c["h"] for c in k1h[-SWING_LOOKBACK - 1:-1]) \
            if len(k1h) > SWING_LOOKBACK else price
        if price <= e20:
            return False, "çmimi nën EMA20 (1H)"
        if price <= e50:
            return False, "çmimi nën EMA50 (1H)"
        if not (RSI_LO <= r <= RSI_HI):
            return False, f"RSI {r:.0f} jashtë 55–68"
        if vol_sma <= 0 or vol_last < VOL_MULT * vol_sma:
            return False, "volum pa konfirmim (<1.2×)"
        if price <= prior_high * (1 + BREAKOUT_BUF):
            return False, "pa breakout (nën swing-high)"
        return True, f"BUY sinjal (breakout, RSI {r:.0f}, volum {vol_last/vol_sma:.1f}×)"

    def _swing_low(self, k1h):
        lows = [c["l"] for c in k1h[-SWING_LOOKBACK:]]
        return min(lows) if lows else 0.0

    # ------------------------------------------------------------------
    # Cikli
    # ------------------------------------------------------------------
    async def cycle(self, event=None):
        for sym in ASSETS:
            try:
                await self._tick(sym, event)
            except Exception as e:
                if event:
                    event("spot", f"⚠️ {sym}: {str(e)[:80]}")
        self._save()

    async def _tick(self, sym, event):
        st = self.state[sym]
        k1h = await self.market.fetch_klines(sym, ENTRY_BAR, limit=100)
        if not k1h:
            return
        k4h = await self.market.fetch_klines(sym, TREND_BAR, limit=250)
        if not k4h:
            return
        price = k1h[-1]["c"]
        st["updated_at"] = time.time()

        trend_ok, why = self._trend_ok(k4h, price)

        # ---- Mbyllje e plotë nëse filtri i trendit prishet ----
        if st["qty"] > 0 and not trend_ok:
            self._close_all(st, price, f"trend i kthyer: {why}", event)
            return

        # ---- SL i prekur → mbyllje e plotë ----
        if st["qty"] > 0 and st["sl"] > 0 and price <= st["sl"]:
            self._close_all(st, price, "SL i prekur (nën swing-low)", event)
            return

        # ---- Trailing (pjesa e mbetur pas daljeve graduale) ----
        if st["qty"] > 0 and st["sold"] >= 0.5:
            st["peak"] = max(st["peak"], price)
            new_sl = st["peak"] * (1 - TRAIL_PCT)
            if new_sl > st["sl"]:
                st["sl"] = new_sl
                st["last_signal"] = f"trailing SL {st['sl']:.6g}"
            if price <= st["sl"]:
                self._close_all(st, price, "trailing stop", event)
                return

        # ---- Dalje graduale (TP1 +6%, TP2 +12%) ----
        if st["qty"] > 0 and st["avg_entry"] > 0:
            pnl_pct = (price / st["avg_entry"] - 1.0) * 100
            if st["sold"] < 0.25 and pnl_pct >= TP1_PCT:
                self._sell_part(st, price, "TP1 +6% — shita 25%", event)
            elif st["sold"] < 0.5 and pnl_pct >= TP2_PCT:
                self._sell_part(st, price, "TP2 +12% — shita 25%", event)

        # ---- Nëse s'ka pozicion: kërko BUY 1 ----
        if st["qty"] == 0:
            if not trend_ok:
                st["last_signal"] = f"NO TRADE ({why})"
                st["status"] = "duke pritur"
                return
            ok, sig = self._entry_signal(k1h)
            if ok:
                self._buy(st, price, 0.40, "BUY 1 (40%)", k1h, event)
            else:
                st["last_signal"] = sig
                st["status"] = "duke pritur"
            return

        # ---- Pyramiding: BUY 2 / BUY 3 vetëm me higher-high ----
        if st["entries"] < MAX_ENTRIES and st["sold"] < 0.5:
            # kërkon higher-high: çmimi mbi swing-high e regjistruar në hyrje
            if st["last_entry_high"] > 0 and \
                    price > st["last_entry_high"] * (1 + BREAKOUT_BUF):
                frac = 0.30
                label = f"BUY {st['entries'] + 1} (30%) — higher-high"
                self._buy(st, price, frac, label, k1h, event)

    # ------------------------------------------------------------------
    # Veprimet
    # ------------------------------------------------------------------
    def _buy(self, st, price, frac, label, k1h, event):
        if st["entries"] >= MAX_ENTRIES:          # max 3 hyrje — kurrë më shumë
            return
        amt = SPOT_ENTRY_USD * (1 - FEE_RATE)     # $15 fiks për çdo shtesë
        if amt <= 0 or st["invested"] + amt > st["capital"] * 1.001:
            return
        qty_add = amt / price
        old_cost = st["avg_entry"] * st["qty"]
        st["qty"] += qty_add
        st["invested"] += amt
        st["avg_entry"] = (old_cost + amt) / st["qty"]
        st["entries"] += 1
        st["fees"] += amt * FEE_RATE / (1 - FEE_RATE)
        # SL poshtë swing-low (max 6% larg nga hyrja)
        sl = self._swing_low(k1h)
        if sl <= 0 or st["avg_entry"] - sl > SL_MAX_DIST * st["avg_entry"]:
            sl = st["avg_entry"] * (1 - SL_MAX_DIST)
        if st["entries"] >= 2:
            # pas BUY2 e lart: SL kurrë nën hyrjen mesatare
            sl = max(sl, st["avg_entry"])
        st["sl"] = sl
        st["last_entry_high"] = max(c["h"] for c in k1h[-SWING_LOOKBACK:])
        st["status"] = f"BUY{st['entries']}"
        st["opened_at"] = st["opened_at"] or time.time()
        st["peak"] = max(st["peak"], price)
        st["last_signal"] = f"{label} @ {price:.6g} (avg {st['avg_entry']:.6g}, SL {sl:.6g})"
        if event:
            event("spot",
                  f"🪜 {st['symbol']} {label}: {amt:.2f} USDT @ {price:.6g} "
                  f"(avg {st['avg_entry']:.6g}, SL {sl:.6g})")

    def _sell_part(self, st, price, label, event):
        qty_sell = st["qty"] * SELL_PCT
        gross = qty_sell * price
        fee = (st["avg_entry"] + price) * qty_sell * FEE_RATE
        net = gross - fee
        # kosto e pjesës së shitur
        cost = st["avg_entry"] * qty_sell
        st["realized"] += net - cost
        st["fees"] += fee
        st["qty"] -= qty_sell
        st["invested"] -= cost
        st["sold"] += SELL_PCT
        st["last_signal"] = f"{label} @ {price:.6g} (+{(price/st['avg_entry']-1)*100:.1f}%)"
        if event:
            event("spot", f"🪜 {st['symbol']} {label}: +{(net-cost):.2f} USDT @ {price:.6g}")

    def _close_all(self, st, price, reason, event):
        qty = st["qty"]
        if qty <= 0:
            return
        gross = qty * price
        fee = (st["avg_entry"] + price) * qty * FEE_RATE
        net = gross - fee
        cost = st["avg_entry"] * qty
        pnl = net - cost
        st["realized"] += pnl
        st["fees"] += fee
        self.trades.append({
            "symbol": st["symbol"], "closed_at": time.time(),
            "pnl": round(pnl, 2), "reason": reason,
            "entries": st["entries"], "sold_pct": st["sold"],
        })
        self.trades = self.trades[-200:]
        st["qty"] = 0.0
        st["invested"] = 0.0
        st["avg_entry"] = 0.0
        st["entries"] = 0
        st["sl"] = 0.0
        st["peak"] = 0.0
        st["sold"] = 0.0
        st["status"] = "mbyllur"
        st["last_signal"] = f"{reason} @ {price:.6g}"
        if event:
            event("spot",
                  f"🪜 {st['symbol']} u mbyll — {reason}: "
                  f"{'+' if pnl >= 0 else ''}{pnl:.2f} USDT")

    def reset(self):
        """Rivendos spot pyramiding nga e para (kapital i freskët $45/aset)."""
        self.state = {}
        self.trades = []
        for sym in ASSETS:
            self.state[sym] = _new_asset_state(sym)
        self._save()

    # ------------------------------------------------------------------
    # Për API / panel
    # ------------------------------------------------------------------
    def summary(self):
        out = []
        for sym in ASSETS:
            st = self.state[sym]
            out.append({
                "symbol": sym,
                "capital": st["capital"],
                "invested": round(st["invested"], 2),
                "qty": round(st["qty"], 8),
                "avg_entry": round(st["avg_entry"], 8),
                "entries": st["entries"],
                "sl": round(st["sl"], 8),
                "sold": st["sold"],
                "realized": round(st["realized"], 2),
                "fees": round(st["fees"], 3),
                "status": st["status"],
                "last_signal": st["last_signal"],
            })
        return {
            "assets": out,
            "entry_per_add": SPOT_ENTRY_USD,
            "total_capital": CAPITAL_PER_ASSET * len(ASSETS),
            "total_realized": round(sum(s["realized"] for s in self.state.values()), 2),
            "closed_trades": len(self.trades),
            "recent": self.trades[-10:][::-1],
            "rules": {
                "trend": f"EMA{EMA_SLOW} + EMA{EMA_MID}>{EMA_SLOW} + RSI>{RSI_PERIOD}>50 (4H)",
                "entry": f"EMA{EMA_FAST}/EMA{EMA_MID} + RSI {RSI_LO:.0f}-{RSI_HI:.0f} + volum {VOL_MULT}× + breakout (1H)",
                "pyramid": f"${SPOT_ENTRY_USD:g}/hyrje max {MAX_ENTRIES} (=$45/aset), KURRË averaging-down",
                "sl": f"poshtë swing-low (max {SL_MAX_DIST*100:.0f}%), pas BUY2 kurrë nën mesataren",
                "tp": f"+{TP1_PCT:.0f}% shet 25%, +{TP2_PCT:.0f}% shet 25%, pjesa trailing {TRAIL_PCT*100:.0f}%",
            },
        }
