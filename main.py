"""
Waynis AI — paper trading bot. FastAPI server.

Serves the mobile-first dashboard (static/index.html) and a JSON/WS API.
"""
import asyncio
import json
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from providers import MarketData, WATCHLIST
from engine import PaperEngine, CYCLE_SECONDS
from config import FEE_RATE, SCAN_BATCH

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = BASE          # files live at project root (flat, phone-friendly deploy)

app = FastAPI(title="Waynis AI", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

market = MarketData()
engine = PaperEngine(market)

clients = set()


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup():
    app.state.task = asyncio.create_task(engine.run())
    # warm the ticker cache so the first page load is instant
    await asyncio.to_thread(_warmup)

def _warmup():
    import urllib.request
    try:
        urllib.request.urlopen(
            "https://www.okx.com/api/v5/market/tickers?instType=SPOT",
            timeout=8)
    except Exception:
        pass

def _serve_file(relpath: str, media_type: str):
    """Read a file from disk and return it as bytes (robust for all hosts,
    unlike FileResponse which can fail on some PaaS setups)."""
    from fastapi.responses import Response
    path = os.path.join(STATIC, relpath)
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return JSONResponse(
            {"error": f"Skedari '{relpath}' nuk u gjet (u provua: {path})"},
            status_code=404)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return Response(content=data, media_type=media_type,
                    headers={"Cache-Control": "no-cache"})


@app.get("/", include_in_schema=False)
async def index():
    return _serve_file("index.html", "text/html; charset=utf-8")


@app.get("/debug", include_in_schema=False)
async def debug():
    """Troubleshooting: where files live and what exists."""
    import glob
    cwd = os.getcwd()
    base = BASE
    here = [f for f in os.listdir(base) if os.path.isfile(os.path.join(base, f))]
    return {
        "cwd": cwd,
        "base": base,
        "files_in_base": here,
        "index_exists": os.path.exists(os.path.join(base, "index.html")),
    }


# Web app assets (flat layout — no /static subfolder needed)
for _name, _path, _mime in [("manifest.webmanifest", "manifest.webmanifest",
                             "application/manifest+json"),
                            ("sw.js", "sw.js", "application/javascript"),
                            ("icon-192.png", "icon-192.png", "image/png"),
                            ("icon-512.png", "icon-512.png", "image/png")]:
    @app.get("/" + _name, include_in_schema=False)
    async def _asset(path=_path, mime=_mime):
        return _serve_file(path, mime)

    # backwards-compatible aliases under /static/
    @app.get("/static/" + _name, include_in_schema=False)
    async def _asset_old(path=_path, mime=_mime):
        return _serve_file(path, mime)


# ---------------------------------------------------------------
# APK downloads + source code zip (for Render deployment)
# ---------------------------------------------------------------
def _find_file(name):
    """Look for a file in the project root or in /home/user."""
    for p in (os.path.join(BASE, name), os.path.join("/home/user", name)):
        if os.path.exists(p):
            return p
    return None


@app.get("/apk", include_in_schema=False)
async def download_apk():
    """Serve the Android APK with the correct MIME + download headers,
    so it downloads as a pristine binary (not mangled by any viewer)."""
    from fastapi.responses import StreamingResponse
    apk = _find_file("WaynisAI.apk")
    if not apk:
        return JSONResponse({"error": "APK nuk gjendet"}, status_code=404)
    with open(apk, "rb") as f:
        data = f.read()
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.android.package-archive",
        headers={
            "Content-Disposition": 'attachment; filename="WaynisAI.apk"',
            "Content-Length": str(len(data)),
            "Cache-Control": "no-store",
        })


@app.get("/apk.zip", include_in_schema=False)
async def download_apk_zip():
    """Serve the APK wrapped in a ZIP (more resilient to transfer
    mangling than a raw APK in some download flows)."""
    from fastapi.responses import StreamingResponse
    z = _find_file("WaynisAI-Instalo.zip")
    if not z:
        return JSONResponse({"error": "ZIP nuk gjendet"}, status_code=404)
    with open(z, "rb") as f:
        data = f.read()
    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="WaynisAI-Instalo.zip"',
            "Content-Length": str(len(data)),
            "Cache-Control": "no-store",
        })


@app.get("/code.zip", include_in_schema=False)
async def download_code():
    """Zip the whole deployable project (flat) for Render/GitHub upload.
    Built on the fly so it is always in sync with the current code."""
    import io
    import zipfile
    from fastapi.responses import StreamingResponse

    deploy_files = ["main.py", "engine.py", "agents.py", "brain.py",
                    "config.py", "providers.py", "requirements.txt",
                    "render.yaml", "README.md", "index.html",
                    "manifest.webmanifest", "sw.js",
                    "icon-192.png", "icon-512.png"]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in deploy_files:
            p = os.path.join(BASE, f)
            if os.path.isfile(p):
                z.write(p, f)
    data = buf.getvalue()
    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="WaynisAI-Kodi.zip"',
            "Content-Length": str(len(data)),
            "Cache-Control": "no-store",
        })


@app.get("/deploy.zip", include_in_schema=False)
async def download_deploy_zip():
    """Serve the easy-deploy package (single-file app) — no GitHub needed:
    Hugging Face Spaces or Glitch, just 2-3 files to upload."""
    from fastapi.responses import StreamingResponse
    z = _find_file("WaynisAI-DeployLehte.zip")
    if not z:
        return JSONResponse({"error": "ZIP nuk gjendet"}, status_code=404)
    with open(z, "rb") as f:
        data = f.read()
    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="WaynisAI-DeployLehte.zip"',
            "Content-Length": str(len(data)),
            "Cache-Control": "no-store",
        })


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    return {"ok": True, "t": engine.pipeline["cycles_run"]}


@app.get("/api/status")
async def status():
    acc = engine.account()
    stats = engine.stats()
    real = None
    if engine.mode == "real":
        try:
            real = engine.real_status()
        except Exception as e:
            real = {"error": str(e)[:120]}
    return {
        "account": acc,
        "stats": stats,
        "pipeline": engine.pipeline,
        "cycle_seconds": CYCLE_SECONDS,
        "auto_trade": engine.auto_trade,
        "compound": engine.compound,
        "compound_mult": engine.compound_mult,
        "mode": engine.mode,
        "real": real,
        "fee_rate": FEE_RATE,
        "lock": engine.lock_info(),
        "risk": engine.risk_info(),
        "fixed_risk": engine.fixed_risk_info(),
        "learning_ctrl": engine.learning_controls(),
        "dca": engine.dca_status(),
        "mtf_enabled": True,
        "session": {
            "started_at": engine.started_at,
            "scan_count": engine.scan_count,
            "watchlist_size": len(WATCHLIST),
            "scanned_per_cycle": SCAN_BATCH,
        },
        "ensemble": {"enabled": engine.variant_count > 0,
                     "variants": engine.variant_count,
                     "core_strategies": 16,
                     "total_strategies": engine.variant_count + 16},
        "turso": engine.turso_status(),
        "pyramid": engine.pyramid_summary(),
        "agents": engine.agents_info(),
        "ai": engine.brain.status(),
        "ai_last": engine.last_ai,
        "watchlist": [w[0] for w in WATCHLIST],
    }


@app.get("/api/tickers")
async def tickers():
    t = await market.fetch_all_tickers()
    return {"tickers": list(t.values())}


@app.get("/api/klines")
async def klines(symbol: str = "BTC-USDT", interval: str = "1m", limit: int = 150):
    sym = MarketData.okx_of(symbol)
    limit = max(30, min(500, int(limit)))
    data = await market.fetch_klines(sym, interval, limit)
    return {"symbol": sym, "interval": interval, "candles": data}


@app.get("/api/equity")
async def equity(limit: int = 400):
    return {"history": engine.equity_curve(limit)}


@app.get("/api/trades")
async def trades(limit: int = 60):
    return {"trades": engine.trades(limit)}


@app.get("/api/events")
async def events(limit: int = 40):
    return {"events": engine.recent_events(limit)}


@app.post("/api/cycle/run")
async def run_cycle():
    result = await engine.run_cycle_now()
    return {"ok": True, "pipeline": result}


@app.get("/api/ai/settings")
async def ai_settings_get():
    cfg = engine.brain.cfg
    return {"ok": True, "config": {
        k: cfg[k] for k in ("enabled", "provider", "model", "openai_model",
                            "base_url", "verdict_ttl")
    }, "has_key": bool(cfg.get("api_key")),
       "status": engine.brain.status()}


@app.post("/api/ai/settings")
async def ai_settings_set(body: dict):
    patch = {}
    for k in ("enabled", "provider", "model", "openai_model", "base_url",
              "api_key", "verdict_ttl"):
        if k in body:
            patch[k] = body[k]
    cfg = engine.brain.update_config(patch)
    engine._event("settings",
                  f"AI konfiguruar: {cfg.get('provider')} / {cfg.get('model')} "
                  f"{'AKTIV' if cfg.get('enabled') else 'OFF'}")
    return {"ok": True, "config": cfg, "status": engine.brain.status()}


@app.post("/api/settings")
async def set_settings(body: dict):
    if "auto_trade" in body:
        engine.auto_trade = bool(body["auto_trade"])
        engine._event("settings",
                      "Auto-trading " + ("ON" if engine.auto_trade else "OFF"))
    if "compound" in body:
        engine.compound = bool(body["compound"])
        engine._event("settings",
                      "Komponimi (compound) " +
                      ("AKTIV — pozicionet rriten me equity"
                       if engine.compound else
                       "OFF — madhësi fikse pozicionesh"))
    if "mode" in body:
        new_mode = engine.set_mode(str(body["mode"]))
        return {"ok": True, "mode": new_mode,
                "auto_trade": engine.auto_trade,
                "compound": engine.compound}
    if "compound_mult" in body:
        mult = engine.set_compound_mult(body["compound_mult"])
        return {"ok": True, "compound_mult": mult}
    if "threshold" in body or "learn_speed" in body:
        info = engine.set_learning(threshold=body.get("threshold"),
                                   speed=body.get("learn_speed"))
        return {"ok": True, "learning_ctrl": info}
    if any(k in body for k in ("fixed_risk_enabled", "fixed_entry_usd",
                               "fixed_max_loss_usd")):
        info = engine.set_fixed_risk(
            enabled=body.get("fixed_risk_enabled"),
            entry=body.get("fixed_entry_usd"),
            max_loss=body.get("fixed_max_loss_usd"))
        return {"ok": True, "fixed_risk": info}
    if "equity_lock_enabled" in body or "equity_lock_pct" in body:
        info = engine.set_equity_lock(
            enabled=body.get("equity_lock_enabled"),
            pct=body.get("equity_lock_pct"))
        return {"ok": True, "lock": info}
    return {"ok": True, "auto_trade": engine.auto_trade,
            "compound": engine.compound, "mode": engine.mode}


@app.post("/api/webhook/tradingview")
async def tradingview_webhook(body: dict = None):
    """Receives TradingView alerts (webhook) and turns them into trades.

    In TradingView (Premium) create an Alert → Webhook URL →
    paste this endpoint URL, and set the message (JSON):
      {"symbol":"BTCUSDT","side":"buy","price":0}
    side: buy/sell  (or long/short)
    """
    if body is None:
        body = {}
    symbol = str(body.get("symbol") or body.get("ticker") or "").upper()
    side = str(body.get("side") or body.get("action") or body.get("direction") or "").lower()
    price = float(body.get("price") or 0) or None

    # normalize symbol: BTCUSDT -> BTC-USDT
    if symbol and "-" not in symbol and symbol.endswith("USDT"):
        symbol = symbol[:-4] + "-USDT"
    # validate symbol is in watchlist
    ok_syms = {w[0] for w in WATCHLIST}
    if symbol not in ok_syms:
        return {"ok": False, "error": f"Simboli '{symbol}' nuk është në watchlist"}

    direction = None
    if side in ("buy", "long", "l"):
        direction = "LONG"
    elif side in ("sell", "short", "s"):
        direction = "SHORT"
    else:
        return {"ok": False, "error": f"Drejtimi '{side}' i panjohur (përdor buy/sell)"}

    # build a signal and execute through the same engine path
    import engine as eng
    sig = {"symbol": symbol, "direction": direction,
           "entry": price or (engine.last_tickers.get(symbol) or {}).get("price") or 0,
           "confidence": 80.0}
    # attach TP/SL (LONG: SL below; SHORT: SL above)
    if direction == "LONG":
        sig["tp"] = sig["entry"] * 1.0045
        sig["sl"] = sig["entry"] * 0.9965
    else:
        sig["tp"] = sig["entry"] * 0.9955
        sig["sl"] = sig["entry"] * 1.0035
    if not sig["entry"]:
        tickers = await market.fetch_all_tickers()
        engine.last_tickers = tickers
        sig["entry"] = (tickers.get(symbol) or {}).get("price") or 0
    if not sig["entry"]:
        return {"ok": False, "error": "Nuk u gjet çmimi"}

    qty = 0.0
    if engine.fixed_risk_enabled:
        notional = engine.fixed_entry_usd
        sl_pct = 0.0035
        qty = min(notional / sig["entry"],
                  engine.fixed_max_loss_usd / (sig["entry"] * sl_pct))
    else:
        qty = (engine.account()["equity"] * 0.35) / sig["entry"]

    if qty <= 0:
        return {"ok": False, "error": "Madhësi zero"}

    if engine.mode == "real" and engine.exchange.configured:
        tid = await engine.real_open(sig, qty)
    else:
        tid = engine._open_trade(sig, qty, votes=["TradingView"])
        if tid:
            engine._event("tv",
                          f"📡 TradingView: {direction} {symbol} "
                          f"{qty:.6f} @ {sig['entry']:.6g}",
                          symbol)

    engine._event("settings",
                  f"📡 TradingView sinjal: {direction} {symbol}")
    return {"ok": True, "trade_id": tid, "symbol": symbol,
            "direction": direction, "qty": round(qty, 6),
            "entry": sig["entry"], "mode": engine.mode}


@app.get("/api/webhook/info")
async def webhook_info():
    """Instructions + the webhook URL to paste into TradingView."""
    return {"ok": True,
            "webhook_url": f"https://waynis-ai-1.onrender.com/api/webhook/tradingview",
            "example": '{"symbol":"BTCUSDT","side":"buy"}',
            "note": "Vendos URL-në te TradingView → Alert → Webhook URL"}


@app.get("/api/learning")
async def learning():
    return {"ok": True, "learning": engine.learning_status()}


@app.post("/api/backtest/run")
async def backtest_run(symbols: str = "BTC-USDT,ETH-USDT,SOL-USDT,BNB-USDT,XRP-USDT,DOGE-USDT,ADA-USDT,AVAX-USDT,SUI-USDT,DOGE-USDT"):
    """Run the 20-agent strategy over ~40 days of 1h historical data
    with real fees. Returns the honest backtest report."""
    import backtest as bt
    syms = [s.strip() for s in symbols.split(",") if s.strip()]
    results = []
    for sym in dict.fromkeys(syms):
        try:
            candles = await market.fetch_klines_history(sym, "1h", 900)
            if len(candles) < 80:
                continue
            trades, pnl, dd = await asyncio.to_thread(
                bt.backtest_symbol, sym, candles)
            results.append((sym, trades, pnl, dd))
        except Exception:
            continue
    report = bt.summarize(results)
    engine._event("backtest",
                  f"🧪 Backtest: {report['trades']} tregti, win rate "
                  f"{report['win_rate']}%, PnL {report['total_pnl']:+.2f} USDT, "
                  f"R:R {report['rr']}, drawdown {report['max_drawdown_pct']}%")
    return {"ok": True, "report": report}


@app.get("/api/dca")
async def dca_status():
    return {"ok": True, "dca": engine.dca_status()}


@app.get("/api/dca/backtest")
async def dca_backtest(symbol: str = "BTC-USDT", amount: float = 5.0,
                       interval_days: float = 1.0, days: int = 365):
    r = await engine.dca_backtest(symbol, amount, interval_days, days)
    return {"ok": True, "result": r}


@app.post("/api/dca/settings")
async def dca_settings(body: dict):
    info = engine.dca_set(
        enabled=body.get("enabled"),
        amount=body.get("amount"),
        interval=body.get("interval_min"),
        symbol=body.get("symbol"))
    return {"ok": True, "dca": info}


@app.get("/api/real/status")
async def real_status():
    try:
        return {"ok": True, "real": engine.real_status()}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


@app.post("/api/reset")
async def reset(seed: bool = False):
    """Rivendos llogarinë nga e para.
    seed=true → mbjell demen e bukur (85%, Sot +52 — numra JO-realë, të
    shënuar si demo). seed=false → $10,000 i pastër pa asnjë tregti."""
    engine.reset(seed=seed)
    # pastro edhe cloud-in që historia e vjetër të mos rikthehet
    try:
        engine._turso_push_snapshot()
    except Exception:
        pass
    return {"ok": True, "balance": engine.account()["balance"],
            "demo": bool(seed)}


# ---------------------------------------------------------------------------
# WebSocket live feed
# ---------------------------------------------------------------------------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=0.5)
                if msg == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                pass
            except Exception:
                break

            tickers_data = await market.fetch_all_tickers()
            acc = engine.account()
            stats = engine.stats()
            payload = {
                "type": "tick",
                "tickers": [v for v in tickers_data.values()],
                "account": acc,
                "stats": stats,
                "pipeline": engine.pipeline,
            }
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                break
            await asyncio.sleep(CYCLE_SECONDS)
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(ws)


# ---------------------------------------------------------------------------
# Entry point — PORT comes from the environment (Render sets it);
# default 7860 = Hugging Face Spaces Docker port.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "7860"))
    uvicorn.run(app, host="0.0.0.0", port=port)
