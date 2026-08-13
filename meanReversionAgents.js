/**
 * Mean Reversion Multi-Agent Pipeline — V1
 * ==========================================
 * Për Waynis AI (github.com/jusufiiajeti-design/Wayn.ai)
 *
 * 6 agjentë: Regime -> MeanReversion -> Confirmation -> Risk+Defense
 *            -> Portfolio -> Execution
 *
 * Pa varësi të jashtme (nuk kërkon npm install shtesë) — vetëm math bazë.
 *
 * PËRDORIM (skelet):
 *
 *   const { Pipeline, defaultConfig } = require('./meanReversionAgents');
 *   const pipeline = new Pipeline(defaultConfig);
 *
 *   // për çdo candle 15m të re nga exchange-i:
 *   const decision = pipeline.onCandle(candle, candleHistory);
 *   // decision.action: 'LONG' | 'SHORT' | 'CLOSE' | 'WAIT'
 *   // decision.state: NORMAL | CAUTION | DEFENSE | RECOVERY | KILL_SWITCH
 *   // decision.trade: { entry, sl, tp, size } nëse action !== 'WAIT'
 *
 * candleHistory pritet si array objektesh { timestamp, open, high, low, close, volume }
 * në rend kronologjik, me candle-in aktual si elementi i fundit.
 */

'use strict';

// ----------------------------------------------------------------------
// CONFIG
// ----------------------------------------------------------------------

const defaultConfig = {
  // Regime
  adxPeriod: 14,
  adxTrendThreshold: 25.0,
  emaFast: 50,
  emaSlow: 200,
  emaSlopeMaxPct: 0.05,

  // Mean reversion
  bbPeriod: 20,
  bbStdDev: 2.0,
  zscorePeriod: 20,
  rsiPeriod: 14,
  rsiLongMax: 35.0,
  rsiShortMin: 65.0,
  atrPeriod: 14,
  atrSpikeMult: 1.5,

  // Confirmation
  confirmationMinNormal: 3,
  confirmationMinCaution: 4,

  // Risk
  riskPctNormal: 0.0025,
  riskPctCaution: 0.0010,
  slAtrMult: 1.0,
  tpAtrMult: 1.3,

  // Defense state machine
  lossesToCaution: 2,
  lossesToDefense: 3,
  recoveryWaitCandles: 240,
  dailyDrawdownStopPct: 0.015,
  killSwitchDrawdownPct: 0.08,

  // Portfolio
  maxOpenTrades: 2,

  // Capital
  startingCapital: 50,
  takerFeePct: 0.001,
};

// ----------------------------------------------------------------------
// INDICATORS — implementim manual (array-based, e fundit = candle aktual)
// ----------------------------------------------------------------------

function ema(values, period) {
  const k = 2 / (period + 1);
  const out = new Array(values.length).fill(null);
  let prev = values[0];
  out[0] = prev;
  for (let i = 1; i < values.length; i++) {
    prev = values[i] * k + prev * (1 - k);
    out[i] = prev;
  }
  return out;
}

function sma(values, period) {
  const out = new Array(values.length).fill(null);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= period) sum -= values[i - period];
    if (i >= period - 1) out[i] = sum / period;
  }
  return out;
}

function stdDev(values, period, means) {
  const out = new Array(values.length).fill(null);
  for (let i = period - 1; i < values.length; i++) {
    const m = means[i];
    if (m === null) continue;
    let sumSq = 0;
    for (let j = i - period + 1; j <= i; j++) {
      sumSq += (values[j] - m) ** 2;
    }
    out[i] = Math.sqrt(sumSq / period);
  }
  return out;
}

function rsi(closes, period) {
  const out = new Array(closes.length).fill(50);
  let avgGain = 0, avgLoss = 0;
  for (let i = 1; i < closes.length; i++) {
    const delta = closes[i] - closes[i - 1];
    const gain = Math.max(delta, 0);
    const loss = Math.max(-delta, 0);
    if (i <= period) {
      avgGain += gain / period;
      avgLoss += loss / period;
      out[i] = 50;
    } else {
      avgGain = (avgGain * (period - 1) + gain) / period;
      avgLoss = (avgLoss * (period - 1) + loss) / period;
      const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
      out[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + rs);
    }
  }
  return out;
}

function trueRange(candles) {
  const out = new Array(candles.length).fill(0);
  for (let i = 0; i < candles.length; i++) {
    const { high, low } = candles[i];
    if (i === 0) {
      out[i] = high - low;
    } else {
      const prevClose = candles[i - 1].close;
      out[i] = Math.max(high - low, Math.abs(high - prevClose), Math.abs(low - prevClose));
    }
  }
  return out;
}

function atr(candles, period) {
  const tr = trueRange(candles);
  return ema(tr, period);
}

function adx(candles, period) {
  const plusDM = [0], minusDM = [0];
  for (let i = 1; i < candles.length; i++) {
    const upMove = candles[i].high - candles[i - 1].high;
    const downMove = candles[i - 1].low - candles[i].low;
    plusDM.push(upMove > downMove && upMove > 0 ? upMove : 0);
    minusDM.push(downMove > upMove && downMove > 0 ? downMove : 0);
  }
  const tr = ema(trueRange(candles), period);
  const plusDI = ema(plusDM, period).map((v, i) => (tr[i] ? (100 * v) / tr[i] : 0));
  const minusDI = ema(minusDM, period).map((v, i) => (tr[i] ? (100 * v) / tr[i] : 0));
  const dx = plusDI.map((v, i) => {
    const sum = v + minusDI[i];
    return sum ? (100 * Math.abs(v - minusDI[i])) / sum : 0;
  });
  return ema(dx, period);
}

function bollinger(closes, period, stdMult) {
  const mid = sma(closes, period);
  const sd = stdDev(closes, period, mid);
  const upper = mid.map((m, i) => (m === null ? null : m + stdMult * sd[i]));
  const lower = mid.map((m, i) => (m === null ? null : m - stdMult * sd[i]));
  return { upper, mid, lower };
}

function zscoreSeries(closes, period) {
  const mean = sma(closes, period);
  const sd = stdDev(closes, period, mean);
  return closes.map((c, i) => {
    if (mean[i] === null || !sd[i]) return null;
    return (c - mean[i]) / sd[i];
  });
}

// ----------------------------------------------------------------------
// AGENT 1: REGIME
// ----------------------------------------------------------------------

function regimeAgent(indicators, i, cfg) {
  const adxVal = indicators.adx[i];
  if (adxVal === null || adxVal >= cfg.adxTrendThreshold) {
    return { ok: false, reason: 'TREND (ADX high)' };
  }
  const fastNow = indicators.emaFast[i];
  const fastPrev = indicators.emaFast[i - 1];
  if (fastPrev) {
    const slopePct = Math.abs((fastNow - fastPrev) / fastPrev) * 100;
    if (slopePct >= cfg.emaSlopeMaxPct) {
      return { ok: false, reason: 'EMA slope too steep' };
    }
  }
  return { ok: true };
}

// ----------------------------------------------------------------------
// AGENT 2: MEAN REVERSION SIGNAL
// ----------------------------------------------------------------------

function meanReversionAgent(candles, indicators, i, cfg) {
  const z = indicators.zscore[i];
  const bbLower = indicators.bbLower[i];
  const bbUpper = indicators.bbUpper[i];
  const rsiVal = indicators.rsi[i];
  const atrVal = indicators.atr[i];
  const atrAvg50 = indicators.atrAvg50[i];
  const close = candles[i].close;

  if (z === null || bbLower === null || !atrAvg50) return null;
  if (atrVal > cfg.atrSpikeMult * atrAvg50) return null; // volatility spike

  if (z <= -2.0 && close <= bbLower && rsiVal <= cfg.rsiLongMax) return 'LONG';
  if (z >= 2.0 && close >= bbUpper && rsiVal >= cfg.rsiShortMin) return 'SHORT';
  return null;
}

// ----------------------------------------------------------------------
// AGENT 3: CONFIRMATION (0-5)
// ----------------------------------------------------------------------

function confirmationAgent(candles, indicators, i, side) {
  if (i < 2) return 0;
  let score = 0;
  const rsiNow = indicators.rsi[i];
  const rsiPrev = indicators.rsi[i - 1];
  const zNow = indicators.zscore[i];
  const zPrev2 = indicators.zscore[i - 2];
  const close = candles[i].close;

  if (side === 'LONG') {
    if (rsiNow > rsiPrev) score++;
    if (close > indicators.bbLower[i]) score++;
    if (zNow !== null && zPrev2 !== null && zNow > zPrev2) score++;
  } else {
    if (rsiNow < rsiPrev) score++;
    if (close < indicators.bbUpper[i]) score++;
    if (zNow !== null && zPrev2 !== null && zNow < zPrev2) score++;
  }

  const lookback = candles.slice(Math.max(0, i - 20), i);
  const volAvg = lookback.length ? lookback.reduce((s, c) => s + c.volume, 0) / lookback.length : 0;
  if (!volAvg || candles[i].volume <= 2 * volAvg) score++;

  // 5-ti kusht: news/event risk — nuk ka feed të integruar, pikë default.
  // Nëse lidh një news-feed, zëvendëso këtë me kontroll real.
  score++;

  return score;
}

// ----------------------------------------------------------------------
// AGENT 4: RISK + DEFENSE (state machine)
// ----------------------------------------------------------------------

class DefenseAgent {
  constructor(cfg) {
    this.cfg = cfg;
    this.state = 'NORMAL';
    this.consecutiveLosses = 0;
    this.candlesSinceLastTrade = 0;
    this.dailyPnlPct = 0;
    this.equity = cfg.startingCapital;
    this.peakEquity = cfg.startingCapital;
    this._currentDay = null;
  }

  onNewCandle(timestamp) {
    this.candlesSinceLastTrade++;
    const day = new Date(timestamp).toISOString().slice(0, 10);
    if (this._currentDay === null) this._currentDay = day;
    else if (day !== this._currentDay) {
      this._currentDay = day;
      this.dailyPnlPct = 0;
      if (this.state !== 'DEFENSE' && this.state !== 'KILL_SWITCH') {
        this.state = this.consecutiveLosses < this.cfg.lossesToCaution ? 'NORMAL' : 'CAUTION';
      }
    }
    if (this.state === 'DEFENSE' && this.candlesSinceLastTrade >= this.cfg.recoveryWaitCandles) {
      this.state = 'RECOVERY';
    }
  }

  onTradeClosed(pnlAbs) {
    const pnlPct = pnlAbs / this.equity;
    this.equity += pnlAbs;
    this.peakEquity = Math.max(this.peakEquity, this.equity);
    this.dailyPnlPct += pnlPct;
    this.consecutiveLosses = pnlAbs < 0 ? this.consecutiveLosses + 1 : 0;
    this.candlesSinceLastTrade = 0;
    this._updateState();
  }

  _updateState() {
    const ddFromPeak = this.peakEquity > 0 ? (this.peakEquity - this.equity) / this.peakEquity : 0;
    if (ddFromPeak >= this.cfg.killSwitchDrawdownPct) {
      this.state = 'KILL_SWITCH';
      return;
    }
    if (this.dailyPnlPct <= -this.cfg.dailyDrawdownStopPct) {
      this.state = 'DEFENSE';
      return;
    }
    if (this.consecutiveLosses >= this.cfg.lossesToDefense) {
      this.state = 'DEFENSE';
    } else if (this.consecutiveLosses >= this.cfg.lossesToCaution) {
      this.state = 'CAUTION';
    } else if (this.state !== 'DEFENSE') {
      this.state = this.state === 'RECOVERY' ? 'CAUTION' : 'NORMAL';
    }
  }

  canTrade() {
    return ['NORMAL', 'CAUTION', 'RECOVERY'].includes(this.state);
  }

  riskPct() {
    return this.state === 'NORMAL' ? this.cfg.riskPctNormal : this.cfg.riskPctCaution;
  }

  confirmationNeeded() {
    return this.state === 'NORMAL' ? this.cfg.confirmationMinNormal : this.cfg.confirmationMinCaution;
  }
}

// ----------------------------------------------------------------------
// AGENT 5: PORTFOLIO
// ----------------------------------------------------------------------

function portfolioAgent(openPositions, cfg) {
  if (openPositions.length >= cfg.maxOpenTrades) {
    return { ok: false, reason: 'Max open trades reached' };
  }
  return { ok: true };
}

// ----------------------------------------------------------------------
// AGENT 6: EXECUTION — vetëm ndërton urdhrin, nuk vendos
// ----------------------------------------------------------------------

function executionAgent(side, entryPrice, atrVal, riskAmount, cfg) {
  const slDist = cfg.slAtrMult * atrVal;
  const tpDist = cfg.tpAtrMult * atrVal;
  const size = slDist > 0 ? riskAmount / slDist : 0;
  const sl = side === 'LONG' ? entryPrice - slDist : entryPrice + slDist;
  const tp = side === 'LONG' ? entryPrice + tpDist : entryPrice - tpDist;
  return { entry: entryPrice, sl, tp, size };
}

// ----------------------------------------------------------------------
// PIPELINE — orchestron të 6 agjentët
// ----------------------------------------------------------------------

class Pipeline {
  constructor(cfg = defaultConfig) {
    this.cfg = cfg;
    this.defense = new DefenseAgent(cfg);
    this.openPositions = []; // { side, entry, sl, tp, size, entryIdx }
  }

  /**
   * candleHistory: array kronologjik i candle-ve deri te ai aktual (inclusive).
   * Kthen: { action, state, trade?, reason? }
   */
  onCandle(candleHistory) {
    const cfg = this.cfg;
    const i = candleHistory.length - 1;
    const closes = candleHistory.map((c) => c.close);
    const current = candleHistory[i];

    this.defense.onNewCandle(current.timestamp);

    // --- manage open position (max 1 modeluar këtu për thjeshtësi; për >1
    //     përsërit të njëjtën logjikë për secilën pozicion të hapur) ---
    if (this.openPositions.length > 0) {
      const pos = this.openPositions[0];
      const hitSl = pos.side === 'LONG' ? current.low <= pos.sl : current.high >= pos.sl;
      const hitTp = pos.side === 'LONG' ? current.high >= pos.tp : current.low <= pos.tp;

      if (hitSl || hitTp) {
        const exitPrice = hitSl ? pos.sl : pos.tp;
        const pnl =
          pos.side === 'LONG'
            ? (exitPrice - pos.entry) * pos.size
            : (pos.entry - exitPrice) * pos.size;
        const fee = (pos.entry + exitPrice) * pos.size * cfg.takerFeePct;
        this.openPositions.shift();
        this.defense.onTradeClosed(pnl - fee);
        return { action: 'CLOSE', state: this.defense.state, exitPrice, pnl: pnl - fee };
      }
      // pozicion i hapur, mos kërko entry të re nëse maxOpenTrades=1
      if (this.openPositions.length >= cfg.maxOpenTrades) {
        return { action: 'WAIT', state: this.defense.state, reason: 'Position open' };
      }
    }

    if (this.defense.state === 'KILL_SWITCH') {
      return { action: 'WAIT', state: 'KILL_SWITCH', reason: 'Kill switch aktiv — review manual' };
    }
    if (!this.defense.canTrade()) {
      return { action: 'WAIT', state: this.defense.state, reason: 'Defense mode nuk lejon trade' };
    }

    if (candleHistory.length < Math.max(cfg.emaSlow, cfg.bbPeriod, cfg.zscorePeriod, cfg.atrPeriod) + 5) {
      return { action: 'WAIT', state: this.defense.state, reason: 'Jo mjaftueshëm histori për indikatorët' };
    }

    // --- indikatorë ---
    const indicators = {
      rsi: rsi(closes, cfg.rsiPeriod),
      atr: atr(candleHistory, cfg.atrPeriod),
      adx: adx(candleHistory, cfg.adxPeriod),
      emaFast: ema(closes, cfg.emaFast),
      emaSlow: ema(closes, cfg.emaSlow),
      zscore: zscoreSeries(closes, cfg.zscorePeriod),
    };
    const bb = bollinger(closes, cfg.bbPeriod, cfg.bbStdDev);
    indicators.bbUpper = bb.upper;
    indicators.bbLower = bb.lower;
    indicators.atrAvg50 = sma(indicators.atr, 50);

    // --- Agent 1: Regime ---
    const regime = regimeAgent(indicators, i, cfg);
    if (!regime.ok) {
      return { action: 'WAIT', state: this.defense.state, reason: regime.reason };
    }

    // --- Agent 2: Mean Reversion signal ---
    const side = meanReversionAgent(candleHistory, indicators, i, cfg);
    if (!side) {
      return { action: 'WAIT', state: this.defense.state, reason: 'Nuk ka sinjal MR' };
    }

    // --- Agent 3: Confirmation ---
    const confScore = confirmationAgent(candleHistory, indicators, i, side);
    const confNeeded = this.defense.confirmationNeeded();
    if (confScore < confNeeded) {
      return { action: 'WAIT', state: this.defense.state, reason: `Confirmation ${confScore}/${confNeeded}` };
    }

    // --- Agent 5: Portfolio (kontrollohet para Risk pasi është filtër i shpejtë) ---
    const portfolioCheck = portfolioAgent(this.openPositions, cfg);
    if (!portfolioCheck.ok) {
      return { action: 'WAIT', state: this.defense.state, reason: portfolioCheck.reason };
    }

    // --- Agent 4: Risk sizing ---
    const atrVal = indicators.atr[i];
    if (!atrVal || atrVal <= 0) {
      return { action: 'WAIT', state: this.defense.state, reason: 'ATR i pavlefshëm' };
    }
    const riskAmount = this.defense.equity * this.defense.riskPct();

    // --- Agent 6: Execution ---
    const order = executionAgent(side, current.close, atrVal, riskAmount, cfg);
    if (order.size <= 0) {
      return { action: 'WAIT', state: this.defense.state, reason: 'Size 0' };
    }

    this.openPositions.push({
      side,
      entry: order.entry,
      sl: order.sl,
      tp: order.tp,
      size: order.size,
      entryIdx: i,
    });

    return { action: side, state: this.defense.state, trade: order };
  }
}

module.exports = {
  Pipeline,
  DefenseAgent,
  defaultConfig,
  // indikatorët eksportohen edhe veças, për debug/testim
  indicators: { ema, sma, stdDev, rsi, atr, adx, bollinger, zscoreSeries },
};
