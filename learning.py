"""
Waynis AI — ENHANCED LEARNING SYSTEM for the 20 agents.

After every closed trade we attribute its PnL to the strategies that voted
for it (trade.votes) and recompute, per strategy:
    * trades, wins, losses, win rate
    * profit factor      (gross wins / gross losses)
    * expectancy         (average net PnL per trade)
    * recency            (recent PnL matters more than old trades)

Each strategy weight in [0.35, 1.7] blends:
    base           0.50
    win-rate edge  (wins - losses) / trades
    profit-factor  (PF - 1) * factor
    recency        recent avg PnL
    EXPLORE bonus  strategies with few trades get a nudge so the system
                   keeps trying them while it learns (exploration)

META-LEARNING (the system adapts itself):
    * rolling system win rate over the last N closed trades
    * if winning  -> consensus threshold loosens (exploit more)
    * if losing   -> consensus threshold tightens (be conservative)
    * the current threshold is used by the Consensus agent each cycle.
"""
import json
import os
import time

WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "data", "strategy_weights.json")
HISTORY_PATH = os.path.join(os.path.dirname(__file__), "data", "learning_history.json")

DEFAULT_STATS = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0,
                 "gross_win": 0.0, "gross_loss": 0.0, "recent": [],
                 "weight": 1.0, "updated_at": None}

EXPLORE_MIN_TRADES = 5      # strategies with fewer trades get a boost
RECENT_WINDOW = 20          # recent-PnL window
WEIGHT_MIN, WEIGHT_MAX = 0.35, 1.7
BASE_THRESHOLD = 0.05       # consensus threshold baseline
META_WINDOW = 30            # rolling system performance window
HISTORY_MAX = 240           # learning-curve points kept


# ---------------------------------------------------------------------------
# Weight computation
# ---------------------------------------------------------------------------
def compute_weight(st, explore_min=EXPLORE_MIN_TRADES):
    t = st["trades"]
    if t == 0:
        return 1.0
    wr = (st["wins"] - st["losses"]) / t                  # -1 .. 1
    if st["gross_loss"] > 0:
        pf = st["gross_win"] / st["gross_loss"]
    else:
        pf = 3.0 if st["gross_win"] > 0 else 0.0
    rec = sum(st["recent"]) / max(len(st["recent"]), 1)   # avg recent pnl

    w = 0.5
    w += max(-0.40, min(0.40, wr * 0.50))                 # win-rate edge
    w += max(-0.20, min(0.25, (pf - 1.0) * 0.15))         # profit-factor edge
    w += max(-0.25, min(0.30, rec / 40.0))                # recency
    if t < explore_min:                                   # exploration bonus
        w += (explore_min - t) / explore_min * 0.25
    return max(WEIGHT_MIN, min(WEIGHT_MAX, round(w, 3)))


# ---------------------------------------------------------------------------
# Aggregate per-strategy stats from the trades table
# ---------------------------------------------------------------------------
def aggregate_from_trades(conn, last_id=0, explore_min=EXPLORE_MIN_TRADES):
    """Returns (stats dict keyed by strategy name, max trade id processed)."""
    rows = conn.execute(
        "SELECT id, votes, status, pnl FROM trades "
        "WHERE status!='open' AND id>? ORDER BY id", (last_id,)).fetchall()
    stats = {}
    max_id = last_id
    for tid, votes_json, status, pnl in rows:
        max_id = max(max_id, tid)
        if not votes_json:
            continue
        try:
            names = json.loads(votes_json)
        except Exception:
            continue
        for name in names:
            st = stats.setdefault(name, dict(DEFAULT_STATS))
            st["trades"] += 1
            p = pnl or 0.0
            if status == "win":
                st["wins"] += 1
                st["gross_win"] += max(p, 0.0)
            else:
                st["losses"] += 1
                st["gross_loss"] += max(-p, 0.0)
            st["pnl"] = round(st["pnl"] + p, 2)
            st["recent"].append(p)
            if len(st["recent"]) > RECENT_WINDOW:
                st["recent"] = st["recent"][-RECENT_WINDOW:]
    for name, st in stats.items():
        st["weight"] = compute_weight(st, explore_min)
        st["updated_at"] = time.time()
        # keep the dict clean for JSON
        st["recent"] = [round(x, 2) for x in st["recent"][-10:]]
    return stats, max_id


def enrich(stats):
    """Add derived fields (win rate, profit factor, expectancy) for the UI."""
    out = {}
    for name, st in stats.items():
        d = dict(st)
        t = d["trades"]
        d["win_rate"] = round(100.0 * d["wins"] / t, 1) if t else 0.0
        d["profit_factor"] = round(
            d["gross_win"] / d["gross_loss"], 2) if d["gross_loss"] > 0 else (
            9.99 if d["gross_win"] > 0 else 0.0)
        d["expectancy"] = round(d["pnl"] / t, 3) if t else 0.0
        out[name] = d
    return out


# ---------------------------------------------------------------------------
# Meta-learning: adaptive consensus threshold from rolling system results
# ---------------------------------------------------------------------------
def meta_threshold(recent_results, base=BASE_THRESHOLD):
    """base = user preference (default 0.05). The system nudges it:
    winning → looser (0.8×), losing → stricter (1.6×), clamped 0.03..0.12."""
    if not recent_results:
        return round(base, 3)
    wins = sum(1 for r in recent_results if r > 0)
    wr = wins / len(recent_results)
    if wr >= 0.55:
        return round(max(0.03, base * 0.8), 3)      # exploit — looser
    if wr <= 0.42:
        return round(min(0.12, base * 1.6), 3)      # conserve — stricter
    return round(base, 3)


def system_win_rate(recent_results):
    if not recent_results:
        return None
    return round(100.0 * sum(1 for r in recent_results if r > 0) /
                 len(recent_results), 1)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def load_weights():
    try:
        with open(WEIGHTS_PATH) as f:
            d = json.load(f)
        for name in d:
            d[name] = {**DEFAULT_STATS, **d[name]}
        return d
    except Exception:
        return {}


def save_weights(stats):
    try:
        os.makedirs(os.path.dirname(WEIGHTS_PATH), exist_ok=True)
        with open(WEIGHTS_PATH, "w") as f:
            json.dump(stats, f, indent=2)
    except Exception:
        pass


def load_history():
    try:
        with open(HISTORY_PATH) as f:
            return json.load(f)
    except Exception:
        return []


def save_history(history):
    try:
        os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
        with open(HISTORY_PATH, "w") as f:
            json.dump(history[-HISTORY_MAX:], f)
    except Exception:
        pass
