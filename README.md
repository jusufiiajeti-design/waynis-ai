# ⚡ Waynis AI — Paper Trading Bot

Bot **paper trading** me çmime **reale** të tregut (OKX / Coinbase) dhe
**6-Cycle Execution Pipeline**, i ndërtuar sipas modelit që dërgove.
Pa para reale — vetëm simulim. Hapet në çdo browser, perfekt në **Android**.

---

## 🤖 Arkitektura: 20 agjentë bashkëpunues (multi-strategji + mësim)

Boti kontrollohet nga **20 agjentë** që punojnë së bashku në 6 faza:

| Faza | Agjentët |
|------|----------|
| **Scan** | 📡 Scanner |
| **Predict** | 📈 EMA Trend · 🔄 RSI Reversal · 🌊 MACD Momentum · 🎈 Bollinger Break · ⚡ Stochastic · 🔊 Volume Spike · 📏 ATR Channel · 🚀 Donchian Break · 🏎️ ROC Momentum · 🐢 Slow Trend → 🗳️ **Consensus** → 🧠 AI Predictor |
| **Validate** | 🌦️ Regime · ✅ Validator · 🛡️ Risk Manager |
| **Size** | ⚖️ Sizer |
| **Fill** | 🚦 Filler |
| **Track** | 📊 Tracker · 🎓 **Learning Agent** |

**Bashkëpunimi:** 10 strategjitë VOTOJNË për çdo monedhë. 🗳️ Consensus-i i
kombinon votat me **peshat e mësuara** → fiton sinjali me konsensus më të fortë.

**Mësimi:** pas çdo tregtie të mbyllur, 🎓 Learning Agent-i e **shpërblen**
strategjinë që votoi drejt (pesha rritet) ose e **ul** atë që votoi gabim.
Peshat ruhen në `data/strategy_weights.json` dhe shfaqen në dashboard —
kështu boti **aftësohet me kalimin e kohës**: strategjitë që fitojnë marrin
gjithnjë e më shumë influencë.

## 🧠 AI Logic — agjentët "mendojnë" para se të veprojnë

Boti **nuk** është një motor i vetëm — kontrollohet nga **6 agjentë të
specializuar** të cilët komunikojnë përmes një autobusi të përbashkët
(`CycleContext`) dhe një **koordinator** që i drejton në çdo cikël:

| Cikli | Agjenti | Çfarë bën |
|-------|---------|-----------|
| 1 | 📡 **Scanner** | Tërheq çmime live + qirinj nga exchange |
| 2 | 🎯 **Predictor** | EMA 9/21 + RSI 14 → parashikon drejtimin, jep konfidencë |
| 3 | ✅ **Validator** | Hedh setup-et e rrezikshme (volum, RSI, momentum, portofol i plotë) |
| 4 | ⚖️ **Sizer** | Llogarit madhësinë e pozicionit — **FIKS ose KOMPONIM** |
| 5 | ⚡ **Filler** | Ekzekuton urdhrin paper (DB + feed i ngjarjeve) |
| 6 | 📊 **Tracker** | Monitoron pozicionet: TP, SL, trailing breakeven, PnL live |

Çdo agjent është autonom: lexon kontekstin e përbashkët, vendos, vepron dhe
raporton te pipeline. Koordinatori (motori) e mban ciklin gjallë dhe i
rifillon agjentët në çdo cikël 4-sekondësh. Në dashboard, hapi aktiv tregon
agjentin që po punon.

## 🧠 AI Logic — agjentët "mendojnë" para se të veprojnë

Çdo cikël, pasi agjentët gjejnë një setup, **truri AI** (i cili punon në
background, pa bllokuar ciklin 4-sekondësh) analizon fotografinë e tregut
(EMA, RSI, volum, momentum, 24h, qirinjtë e fundit) dhe kthen një **verdikt**:

- **🎯 Predictor** — e dërgon kandidatin te AI; kur kthehet verdikti,
  konfidenca e sinjalit **përforcohet** (AI pajtohet) ose **ulet** (AI
  kundërshton me ≥65% konfidencë).
- **✅ Validator** — AI ka **të drejtë vetoje**: nëse AI sheh drejtim të
  kundërt me ≥70% konfidencë, tregtia anulohet me arsyetim.
- 📊 **Feed** — çdo verdikt shfaqet si ngjarje `🧠 AI (modeli): VERDIKT % — arsye`.

**Provider-ët e AI** (zgjidhen te Cilësimet → "AI Logjika"):

| Provider | Përshkrimi | Çelës? |
|----------|-----------|--------|
| 🤖 **Ollama (lokal)** | LLM e vërtetë që punon në pajisje, falas, offline. Default: `qwen2.5:0.5b` | Jo |
| ☁️ **Pollinations** | LLM cloud falas (text.pollinations.ai) | Jo |
| 🔑 **OpenAI-compatible** | Çdo API (OpenAI, Groq, OpenRouter, DeepSeek…) — cilësi më e lartë | Po |

Nëse të gjithë provider-ët dështojnë, boti kalon automatikisht te
**motori simbolik** — një arsyetues i strukturuar që shpjegon hap pas hapi
vendimin në shqip ("EMA9 mbi EMA21 → trend rritës; RSI në zonë të
shëndetshme; volumi 1.8x konfirmon…"). Kurrë nuk ngec.

> **Për cilësi më të mirë lokale:** instaloni një model më të madh me
> `ollama pull qwen2.5:3b` ose `llama3.2:3b` dhe vendosni emrin te
> Cilësimet. (Këtu përdoret 0.5B sepse sandbox-i ka vetëm 1.9GB RAM.)
> **Në telefon:** aplikacioni Android punon me çdo provider — për AI të
> vërtetë pa kompjuter, përdorni provider-in "OpenAI-compatible" me një
> çelës falas nga Groq/OpenRouter, ose Pollinations.

## 💹 Efekti komponues (Compound)

Ka **çelës të dedikuar** në Cilësimet:

- **KOMPONIM (ON — default):** risku llogaritet si % e *equity aktual* →
  sa më shumë fitime, aq më të mëdha pozicionet. Kjo prodhon **rritje
  eksponenciale** (efekti komponues klasik i interesit të përbërë).
- **FIKS (OFF):** risku llogaritet si % e *balancës fillestare* ($10,000) →
  madhësi konstante, rritje lineare.

Shembull: me risk 0.75% dhe equity $10,000 → risk $75/urdhër. Nëse equity
rritet në $12,000 → risk $90/urdhër (komponim), kurse në modalitetin FIKS
mbetet $75. **Faktori i komponimit** (equity ÷ 10,000) shfaqet te Cilësimet
dhe **kurba e equity** (grafik 24-orësh me zonë jeshile) është te tab-i
"Tregti" — aty e sheh efektin komponues me sytë e tu.

## 🪜 Spot Pyramiding (strategjia universale EMA+RSI+volume)

Sistem i veçantë brenda botit për **5 asete** (BTC, ETH, SOL, BNB, XRP) me
**100€/aset** (demo: 108 USDT) sipas `STRATEGJIA-SPOT.md`:
- **Filtri i trendit (4H):** çmimi > EMA200, EMA50 > EMA200, RSI > 50 → përndryshe NO TRADE
- **Hyrja (1H):** mbi EMA20/50, RSI 55–68, volum ≥1.2×SMA20, breakout i swing-high
- **Pyramiding 40/30/30** (max 3 hyrje, KURRË averaging-down)
- **SL** poshtë swing-low (max 6%), pas BUY2 kurrë nën mesataren
- **Dalje graduale:** +6% → 25%, +12% → 25%, pjesa → trailing 4%
- Panel: tab-i **Spot** · API: `/api/spot` · Demo — asnjë fitim i garantuar

## 🪜 Pyramiding në botin kryesor (i gjithë boti)

I gjithë boti tani piramidon si sistemi spot, por me **hyrjen normale** ($15
fiks ose ×komponim) dhe **të gjithë agjentët/strategjitë**:
- Agjent i ri **🪜 Pyramid**: kur një pozicion është në **fitim ≥ $0.50** dhe
  çmimi bën **higher-high** (LONG) / **lower-low** (SHORT) → shton një
  pozicion tjetër me madhësinë normale. **Max 3 për simbol.**
- **KURRË averaging-down**: shtohet vetëm në fitim, kurrë kundër tij.
- **Mbrojtje grupi**: kur SL i një pozicioni preket, mbyllen të gjitha shtesat
  e atij simboli (nuk lihen të humbasin më tej).
- Shkalla e fitimit $1/$2/$3/$4/$5 (dollarë të plotë) mbetet — çdo pozicion i
  grupit e kap fitimin e vet, duke dhënë dalje graduale natyrale.

## 🎯 Synimi $60/ditë — çfarë u ndryshua (dhe çfarë është realiste)

**Ndryshimet reale** (nuk ka numra të sajuar):
- Shkalla **$1 tani kyçet nga trailing** (SL lëviz lart), jo nga kapja e
  menjëhershme → pozicioni vazhdon drejt **$2/$3/$4/$5** → fitim mesatar më i madh.
- **Time-stop 30 min**: liron vendet që nuk kanë ecur — me fitim e mbyll me
  dollarin e plotë të kyçur, pa fitim me humbje të vogël.
- **MAX_OPEN 30** (më shumë pozicione njëkohësisht) + **cooldown 10s** → më shumë tregti/ditë.
- Fix `rsi()` në treg pa lëvizje (nuk jep më sinjal të rremë "i mbingarkuar").

**Matematika e ndershme e $60/ditë:** me fitim mesatar ~$2 dhe humbje të vogla,
duhen **~40–80 tregti të mbyllura në ditë** me normë fitimi pozitive. Boti tani
ka aftësinë ta bëjë, por **rezultati varet nga tregu** — matet me të dhëna reale
pas 30+ tregtive (1–2 ditë), jo nga premtime.

## ☁️ Ruajtja përgjithmonë (Turso — databazë falas)

- Pa Turso: Render-i falas e fshin diskun lokal me rindezje → historia reale humbet.
- Me Turso: çdo hapje/mbyllje tregtie + balanca **sinkronizohet menjëherë**
  në cloud; kur serveri rindizet, historia e vërtetë **rikthehet automatikisht**.
- Kredencialet: skedari `turso.json` (url + token) ose variablat e ambientit
  `TURSO_URL` / `TURSO_TOKEN`. Nëse Turso është jashtë linje, boti vazhdon
  lokal dhe sinkronizon në goditjen tjetër të suksesshme.

## 🧩 100,000 agjentë që bashkëpunojnë

- **29 agjentë bërthamë** (16 strategji + Ensemble, Grid, Consensus, AI,
  Validator, Risk, Sizer, **Pyramid 🪜**, Filler, Tracker, Learning…) + **100,000 variante
  strategjike unike** (EMA, RSI, MACD, BOLL, MOM, STOCH, ATR, CCI, MFI,
  SMA, TRIX, DUALMOM, BTREND, EMARSI…) = **100,029 agjentë gjithsej**.
- **Mostër rrotulluese:** në çdo cikël votojnë 1,500 agjentë nga 100,000
  (rreth 27 ms) — me kalimin e kohës TË GJITHË 100,000 marrin pjesë
  njësoj shpesh, pa e ngadalësuar botin.
- Bashkëpunimi: votat grupohen në **familje strategjish** dhe **çdo familje
  ka një zë të barabartë** — asnjë familje nuk e dominon vendimin; familjet
  bien dakord së bashku (konsensus i peshuar).
- Agjenti **Learning** mëson nga çdo tregti në nivel familjeje dhe i
  rregullon peshat e familjeve që bashkëpunuan për fitimin.

## 💵 Fitimi kapet vetëm në dollarë të plotë

- **Korniza: 5 minuta** (e fiksuar — nuk ndryshohet).
- **Hyrja: $15** për tregti, **humbja maksimale: $2**.
- Agjenti **mban pozicionin derisa fitimi të arrijë $1** — asnjëherë nuk kapet
  fitim nën $1 dhe **asnjëherë me centa** (p.sh. JO $1.04).
- Fitimi matet **neto (pas tarifave)** dhe kapet në **shkallët $1 → $2 → $3 →
  $4 → $5**: kur tregu arrin shkallën, ajo kyçet si dollar i plotë.
- Edhe TP (35%, rrjet sigurie) dhe historiku demo përdorin dollarë të plotë.

---

## 🚀 Si ta hapësh në Android

1. Hap linkun e **LIVE PREVIEW** në browserin e telefonit (Chrome).
2. Për ta instaluar si app në telefon:
   - **Chrome** → menu (⋮) → **"Add to Home screen"** → hapet si app i plotë.

> Shënim: preview-i qëndron gjallë vetëm sa kohë serveri është i ndezur.
> Për përdorim 24/7, shih "Deploy" më poshtë.

## 🧠 Çfarë bën boti

- 📈 **Chart live** — qirinj real 1m–1d me EMA 9/21
- 📊 **Statistika** — PnL 24h, win rate, mesatarja ditore, equity
- 📡 **Live Spot Feed** — çmime reale në kohë reale (WebSocket)
- 🔄 **Manual Validate** — butoni "Validoni ciklin tani" ekzekuton një cikël menjeherë
- 🧾 **Historiku i tregtive** me fitore/humbje dhe konfidencë
- ⚙️ **Auto-trading on/off** + **Compound on/off** + reset i llogarisë demo

## 🛠️ Si ta nisësh lokalisht

```bash
# 1) (opsionale, për AI lokal) instalo Ollama dhe modelin:
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:0.5b      # ose një model më i madh nëse ke RAM

# 2) nis serverin:
cd waynis-ai
pip install -r requirements.txt
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Hap `http://localhost:8000` në kompjuter, ose nga telefoni në të njëjtin WiFi:
`http://IP_I_KOMPJUTERIT:8000`.

> Pa Ollama, boti punon njësoj — AI kalon te Pollinations (cloud falas) ose
> te motori simbolik offline.

## ☁️ Deploy 24/7 (që të funksionojë gjithmonë në telefon)

**Render (falas, më i thjeshti):**
1. Krijo llogari në [render.com](https://render.com) → **New → Web Service**.
2. Lidh repon (GitHub) me këtë folder, ose përdor *Deploy from blueprint*.
3. Build command: `pip install -r requirements.txt`
4. Start command: `python3 -m uvicorn main:app --host 0.0.0.0 --port 8000`
5. Merr URL-në → hape në telefon → "Add to Home screen".

Alternativa: **Railway** (`railway up`), **Fly.io**, ose **PythonAnywhere**.

## 📡 API

| Metoda | Rruga | Përshkrimi |
|--------|-------|-----------|
| GET | `/api/status` | Gjendja e llogarisë, statistikat, pipeline |
| GET | `/api/tickers` | Çmimet live të të 12 monedhave |
| GET | `/api/klines?symbol=BTC-USDT&interval=1m&limit=150` | Qirinjtë |
| GET | `/api/trades` | Historiku i tregtive |
| GET | `/api/events` | Ngjarjet e botit (fill, TP, SL, …) |
| GET | `/api/equity` | Kurba e equity (efekti komponues) |
| POST | `/api/cycle/run` | Ekzekuton një cikël menjeherë |
| POST | `/api/settings` | Ndrysho auto_trade / compound |
| GET/POST | `/api/ai/settings` | Lexo/ndrysho konfigurimin e AI (provider, model, çelës) |
| POST | `/api/reset?seed=true` | Rivendos llogarinë demo |
| WS | `/ws` | Feed live (çmime + ngjarje) |

## 📁 Struktura

```
waynis-ai/
├── config.py        # Konfigurimi qendror (risk, TP/SL, komponim)
├── brain.py         # 🧠 Truri AI: Ollama / Pollinations / OpenAI / motor simbolik
├── agents.py        # 6 agjentët e tregtimit + autobusi i kontekstit
├── engine.py        # Koordinatori (llogaria, cikli, menaxhimi i urdhrave)
├── main.py          # FastAPI server (API + WebSocket + frontend)
├── providers.py     # Tërheq çmime reale (OKX → Coinbase → Kraken)
├── static/
│   ├── index.html   # Dashboard mobile-first (pa CDN, punon offline)
│   ├── manifest.webmanifest  # PWA — instalohet në Android
│   ├── icon-192.png / icon-512.png
│   └── sw.js        # Service worker (cache offline)
└── data/paper.db    # SQLite (krijohet vetë)
```

## ⚠️ Disclaimer

Ky është **demo edukative** me tregti të simuluara (paper). Çmimet janë reale,
por asnjë para nuk investohet apo rrezikohet. Tregtimi i kriptomonedhave në
tregjet reale mbart rrezik të lartë — mos investo para që s'mund t'i humbësh.
Historiku i tregtive në fillim është **seed demo** (mund të fshihet me Reset).


---
> Deploy marker: cloud-storage-live · 2026-08-09
