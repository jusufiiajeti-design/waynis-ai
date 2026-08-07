"""
Waynis AI — BACKTEST engine.

Runs the 20-agent strategy (10 strategy votes → consensus) on historical
klines with REAL fees (0.1%/side) and reports the honest numbers:
win rate, net PnL, average win/loss, reward:risk, max drawdown,
fee impact. This tells us whether the strategy would actually make
money BEFORE risking real capital.
"""
import time

from config import FEE_RATE, TAKE_PROFIT, STOP_LOSS
from strategies import STRATEGIES

BACKTEST_NOTIONAL = 1000.0      # $ per position in the simulation
WARMUP = 40                     # candles used to warm indicators
MAX_OPEN_PER_SYMBOL = 1


def _votes_for(closes, highs, lows, vols, ticker=None):
    """Run the 10 strategies on a snapshot; return consensus votes list."""
    k = [{"o": o, "h": h, "l": l, "c": c, "v": v}
         for o, h, l, c, v in zip(closes, highs, lows, closes, vols)]
    votes = []
    for s in STRATEGIES:
        try:
            v = s["fn"]("BT", k, ticker)
        except Exception:
            continue
        if v:
            votes.append((s["name"], v["direction"], v["confidence"]))
    return votes


def _consensus(votes, threshold=0.05):
    """Simplified consensus: net weighted score, need >=2 supporters."""
    net = tw = 0.0
    for _, d, conf in votes:
        net += (1.0 if d == "LONG" else -1.0) * (conf / 100.0)
        tw += 1
    if tw < 2:
        return None
    score = net / tw
    if score > threshold:
        return "LONG", score
    if score < -threshold:
        return "SHORT", score
    return None


def backtest_symbol(symbol, candles):
    """Simulate the strategy on one symbol's candles. Returns trade dicts."""
    trades = []
    pos = None
    equity = BACKTEST_NOTIONAL
    peak = equity
    dd_max = 0.0

    for i in range(WARMUP, len(candles)):
        c = candles[i]
        # ---- manage open position (intrabar TP/SL) ----
        if pos:
            if pos["side"] == "LONG":
                if c["h"] >= pos["tp"]:
                    exit_px = pos["tp"]
                elif c["l"] <= pos["sl"]:
                    exit_px = pos["sl"]
                else:
                    exit_px = None
            else:
                if c["l"] <= pos["tp"]:
                    exit_px = pos["tp"]
                elif c["h"] >= pos["sl"]:
                    exit_px = pos["sl"]
                else:
                    exit_px = None
            if exit_px is not None:
                if pos["side"] == "LONG":
                    gross = (exit_px - pos["entry"]) * pos["qty"]
                else:
                    gross = (pos["entry"] - exit_px) * pos["qty"]
                fees = (pos["entry"] * pos["qty"] + exit_px * pos["qty"]) * FEE_RATE
                pnl = gross - fees
                equity += pnl
                peak = max(peak, equity)
                dd = (peak - equity) / peak * 100 if peak else 0
                dd_max = max(dd_max, dd)
                trades.append({
                    "symbol": symbol, "side": pos["side"],
                    "entry": pos["entry"], "exit": exit_px,
                    "pnl": pnl, "fees": fees,
                    "status": "win" if pnl > 0 else "loss",
                })
                pos = None
                continue

        # ---- look for a new entry ----
        if pos or len(trades) > 400:
            continue
        closes = [x["c"] for x in candles[:i + 1]]
        highs = [x["h"] for x in candles[:i + 1]]
        lows = [x["l"] for x in candles[:i + 1]]
        vols = [x["v"] for x in candles[:i + 1]]
        votes = _votes_for(closes, highs, lows, vols)
        cons = _consensus(votes)
        if not cons:
            continue
        direction, score = cons
        entry = c["c"]
        if direction == "LONG":
            tp = entry * (1 + TAKE_PROFIT)
            sl = entry * (1 - STOP_LOSS)
        else:
            tp = entry * (1 - TAKE_PROFIT)
            sl = entry * (1 + STOP_LOSS)
        pos = {"side": direction, "entry": entry, "tp": tp, "sl": sl,
               "qty": BACKTEST_NOTIONAL / entry}

    # close any remaining position at last close
    if pos:
        exit_px = candles[-1]["c"]
        if pos["side"] == "LONG":
            gross = (exit_px - pos["entry"]) * pos["qty"]
        else:
            gross = (pos["entry"] - exit_px) * pos["qty"]
        fees = (pos["entry"] * pos["qty"] + exit_px * pos["qty"]) * FEE_RATE
        pnl = gross - fees
        equity += pnl
        trades.append({"symbol": symbol, "side": pos["side"],
                       "entry": pos["entry"], "exit": exit_px,
                       "pnl": pnl, "fees": fees,
                       "status": "win" if pnl > 0 else "loss"})
    return trades, equity - BACKTEST_NOTIONAL, dd_max


def summarize(results):
    """results: list of (symbol, trades, pnl, dd). Returns report dict."""
    all_trades = []
    for symbol, trades, pnl, dd in results:
        for t in trades:
            t["symbol"] = symbol
        all_trades.extend(trades)
    n = len(all_trades)
    wins = [t for t in all_trades if t["status"] == "win"]
    losses = [t for t in all_trades if t["status"] == "loss"]
    total_pnl = sum(t["pnl"] for t in all_trades)
    fees = sum(t["fees"] for t in all_trades)
    gross_wins = sum(t["pnl"] for t in wins)
    gross_losses = sum(abs(t["pnl"]) for t in losses)
    avg_win = gross_wins / len(wins) if wins else 0.0
    avg_loss = gross_losses / len(losses) if losses else 0.0
    rr = avg_win / avg_loss if avg_loss else 0.0
    max_dd = max((dd for _, _, _, dd in results), default=0.0)
    n_symbols = len([r for r in results if r[1]])
    return {
        "symbols": n_symbols,
        "trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(100.0 * len(wins) / n, 1) if n else 0.0,
        "total_pnl": round(total_pnl, 2),
        "fees_paid": round(fees, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(-avg_loss, 2),
        "rr": round(rr, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "net_per_trade": round(total_pnl / n, 3) if n else 0.0,
        "done_at": time.time(),
    }
