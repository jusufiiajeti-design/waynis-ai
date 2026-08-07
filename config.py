"""Waynis AI — central configuration (shared by engine and agents)."""

STARTING_BALANCE = 10_000.0     # USDT, paper account
CYCLE_SECONDS = 4               # coordinator cycle period
SCAN_BATCH = 6                  # symbols scanned per cycle
TRADE_RISK = 0.0075             # fraction of (base) equity risked per trade
TAKE_PROFIT = 0.0045            # +0.45 %
STOP_LOSS = 0.0035              # -0.35 %
BREAKEVEN_AT = 0.0020           # move SL to breakeven after +0.20 %
MIN_CONFIDENCE = 58.0           # % required to fire a trade
MAX_OPEN = 4                    # max concurrent open positions
