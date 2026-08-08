"""Waynis AI — central configuration (shared by engine and agents)."""

STARTING_BALANCE = 10_000.0     # USDT, paper account
CYCLE_SECONDS = 3               # coordinator cycle period (cache = faster)
SCAN_BATCH = 32                 # symbols scanned per cycle (all watchlist)
TRADE_TF = "15m"                # ⏱️ korniza 15-minutëshe — lëvizje të mëdha = fitime $1+ më shpesh
KLINES_TTL = 20.0               # cache klines (15m qirinj) — cikle më të shpejta
TRADE_RISK = 0.0075             # fraction of (base) equity risked per trade
TAKE_PROFIT = 0.20             # TP 20% = $3 me $15 — NUK ndërhyn para shkallës $1/$2 (mbyll Smart Exit)
STOP_LOSS = 0.0035              # -0.35 %
BREAKEVEN_AT = 0.0020           # move SL to breakeven after +0.20 %
MIN_CONFIDENCE = 58.0           # % required to fire a trade
MAX_OPEN = 20                   # max concurrent open positions (many slots → non-stop trading)
COOLDOWN_SEC = 20               # cooldown pas mbylljes — më shumë tregti për $60/ditë
MAX_HOLD_MIN = 40               # time-stop: close a position after 40 min if it hasn't hit TP
TIME_STOP_SL = 0.0015           # time-stop closes at -0.15% (small, frees the slot fast)

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
COMPOUND_MULT_MAX = 5.0         # max compound multiplier (×1..×5 user)

# ---- 🛡️ adaptive risk (protects against ×2 losses) ----
RISK_ADAPTIVE_ENABLED = True    # risk manager watches recent performance
RISK_LOOKBACK = 10              # last N closed trades evaluated
RISK_BAD_WR = 0.45              # if win rate below this → de-risk
RISK_BAD_NET = 0.0              # if net pnl over lookback below this → de-risk
RISK_DELEVERAGE_TO = 1.0        # auto-reduce multiplier to ×1 when losing
RISK_PAUSE_MIN = 15             # pause new trades for N minutes when losing
RISK_RESUME_MIN = 3             # re-evaluate after N minutes

# ---- 💵 fixed dollar risk (entry e fiksuar, humbje maksimale e fiksuar) ----
# Hyrja $10–15 (sipas përdoruesit) · fitime të arsyeshme $1–$3+ të kapura
# nga agjentët me shkallë fitimi. Përdoruesi i ndryshon nga Cilësimet.
FIXED_RISK_ENABLED = True         # ON by default: entry fixed, loss capped
FIXED_ENTRY_USD = 15.0           # hyrja për tregti në USDT (min 10, max 15)
FIXED_MAX_LOSS_USD = 2.0         # kufiri i humbjes për tregti (i arsyeshëm)

# ---- 💵 profit ladder (shkallët e fitimit që agjenti i kap) ----
PROFIT_LADDER = [3.0, 2.0, 1.0, 0.5]   # fitime $0.5, $1, $2, $3+ të arsyeshme

# ---- 🧩 ensemble (hundreds of strategy variants) ----
ENSEMBLE_ENABLED = True          # strategy variants vote with the core
AGENT_TARGET = 100               # how many variants to generate (100)



# ---- 🔒 equity profit lock (protect account gains) ----
# Once the account grows to a peak, never let it give back more than
# EQUITY_LOCK_PCT from that peak — when triggered, ALL positions close
# and new entries pause for EQUITY_LOCK_PAUSE_MIN minutes.
EQUITY_LOCK_ENABLED = True
EQUITY_LOCK_PCT = 0.02           # give back max 2% from peak (0.02 = 2%)
EQUITY_LOCK_PAUSE_MIN = 10       # pause new entries after a lock

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


