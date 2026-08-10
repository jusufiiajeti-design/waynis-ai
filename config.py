"""Waynis AI — central configuration (shared by engine and agents)."""

STARTING_BALANCE = 10_000.0     # USDT, paper account
CYCLE_SECONDS = 2               # cikël më i shpejtë (2s) — qarkullim më i shpejtë
SCAN_BATCH = 60                 # skanon të GJITHA monedhat çdo cikël (52+ → 60)
TRADE_RISK = 0.0002             # ~$2 risk SL/tregti me $10k (0.02%) — humbja $2 (kërkesa)
                                 # Tarifat (~$0.30) → humbje totale ~$2.30/tregti
TAKE_PROFIT = 0.020             # +2.0% TP — fitim më i madh (testuar: WR 67%, +$6.33/tregti)
STOP_LOSS = 0.015               # -1.5% SL — breakeven 49% (WR 67% e kalon)
                                 # 🎯 MEAN REVERSION: fitim më i madh + më shumë tregti
BREAKEVEN_AT = 0.0020           # move SL to breakeven after +0.20 %
MIN_CONFIDENCE = 58.0           # % required to fire a trade
MAX_OPEN = 60                   # max 60 pozicione njëkohësisht (kërkesa e përdoruesit)

# ---- real money (spot, LONG-only) ----
FEE_RATE = 0.001                # 0.1% per side (taker) — also simulated in paper
REAL_MIN_NOTIONAL = 5.0         # min order size USDT
REAL_MAX_NOTIONAL_PCT = 0.15    # max % of real balance per trade
REAL_MAX_POSITIONS = 2          # max concurrent real positions
REAL_TP = 0.0045                # +0.45%
REAL_SL = 0.0035                # -0.35%

# ---- asymmetric payoff: wins > losses ("arbitrage-like" edge) ----
# NOTE: disabled by request — the bot uses classic symmetric TP/SL.
ENABLE_PARTIAL_TP = False       # partial take-profit + trailing runner (paper)
TP1_PARTIAL = 0.005             # take half of the position at +0.5%
PARTIAL_FRACTION = 0.5          # fraction sold at TP1
TRAIL_PCT = 0.004               # runner trails 0.4% below its peak
RUNNER_BE = 0.0005              # runner SL floor = entry + 0.05% (never loses)
REL_STRENGTH_BOOST = False      # cross-symbol relative-strength filter

# ---- 🔒 equity profit lock (protect account gains) ----
# Once the account grows to a peak, never let it give back more than
# EQUITY_LOCK_PCT from that peak — when triggered, ALL positions close
# and new entries pause for EQUITY_LOCK_PAUSE_MIN minutes.
EQUITY_LOCK_ENABLED = True
EQUITY_LOCK_PCT = 0.02           # give back max 2% from peak (0.02 = 2%)
EQUITY_LOCK_PAUSE_MIN = 10       # pause new entries after a lock

# ---- 💰 KYÇJA E FITIMIT NË SHKALLË $60 (kërkesa e përdoruesit) ----
# Çdo herë që fitimi arrin +$60 (bilanci 10,060 → 10,120 → 10,180...), ai
# nivel bëhet DYSHEME: nëse equity bie nën të, mbyllen të gjitha pozicionet
# për të mbrojtur fitimin e kyçur. Dyshemeja ngrihet vetëm lart, kurrë poshtë.
PROFIT_LOCK_STEP_USD = 60.0      # +$60 çdo herë
PROFIT_LOCK_PAUSE_MIN = 10       # push pas mbylljes mbrojtëse

# ---- 📈 DCA (dollar-cost averaging) mode ----
DCA_ENABLED = False              # off until user turns it on
DCA_AMOUNT = 5.0                 # USDT per buy
DCA_INTERVAL_MIN = 60            # buy every N minutes
DCA_SYMBOL = "BTC-USDT"

# ---- 🎯 Multi-timeframe confirmation ----
MTF_ENABLED = True               # confirm 1m signal with 15m trend
MTF_BAR = "15m"
MTF_FAST = 20                    # EMA fast period on MTF
MTF_SLOW = 50                    # EMA slow period on MTF
MTF_CACHE_TTL = 120              # seconds to cache MTF closes per symbol


