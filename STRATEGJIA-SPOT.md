# 📘 STRATEGJIA UNIVERSALE SPOT — EMA + RSI + VOLUME + PYRAMIDING
**Waynis AI · Version 1.0 · Demo/Paper — NUK është këshillë financiare**

> ⚠️ Kjo strategji **NUK ka win-rate të garantuar**. Është një sistem mekanik
> trend-following për **spot** (blej mbaj, shes gradualisht — jo short).
> Testohet me të dhëna historike dhe pastaj në demo përpara çdo përdorimi real.
> Në treg anësor (sideways) strategjitë trend-following humbasin shpesh.

---

## 1) Asetet dhe kapitali

**5 monedha bërthamë** (me shembullin 100€ për secilën):

| Aset | Kapitali | Hyrja 1 (40%) | Hyrja 2 (30%) | Hyrja 3 (30%) | Rezervë |
|------|----------|---------------|---------------|---------------|---------|
| **BTC** | 100€ | 40€ | 30€ | 30€ | — |
| **ETH** | 100€ | 40€ | 30€ | 30€ | — |
| **SOL** | 100€ | 40€ | 30€ | 30€ | — |
| **BNB** | 100€ | 40€ | 30€ | 30€ | — |
| **XRP** | 100€ | 40€ | 30€ | 30€ | — |

Total: **500€** (100€/aset). Nëse do 10 monedha, ndaje kapitalin: BTC 25€,
ETH 20€, SOL 15€, BNB 10€, XRP 10€, dhe pjesa tjetër për 4–5 altcoin.
**Kurrë mos hap të gjitha njëkohësisht** — nëse BTC bie fort, altcoins bien
bashkë me të (diversifikimi nominal ≠ diversifikim i vërtetë).

---

## 2) Kornizat kohore

| Përdorim | Korniza |
|----------|---------|
| **Filtri i trendit** (drejtimi kryesor) | **4H** |
| **Hyrja** (sinjali BUY) | **1H** |
| **Menaxhimi i pozicionit** (TP/trailing) | **1H** |

---

## 3) Indikatorët

- **EMA 20** — trend afatshkurtër (1H)
- **EMA 50** — trend i mesëm (1H + 4H)
- **EMA 200** — trend afatgjatë (4H) ← filtri kryesor
- **RSI 14** — momentum (4H për filtër, 1H për hyrje)
- **Volume SMA 20** — vëllimi mesatar 20 qirinj (1H) ← konfirmim

---

## 4) Rregullat BUY (të gjitha duhen plotësuar)

### Filtri i trendit (4H) — pa këtë: **NO TRADE**
1. Çmimi > **EMA 200** (4H) — vetëm në treg rritës
2. **EMA 50 > EMA 200** (4H) — trend rritës i konfirmuar
3. **RSI(14) > 50** (4H) — momentum pozitiv

### Sinjali i hyrjes (1H) — vetëm pas filtrit:
4. Çmimi > **EMA 20** dhe > **EMA 50** (1H)
5. **RSI(14) në 55–68** (1H) — momentum i fortë, por jo i mbingarkuar
6. **Volume i qiriut ≥ 1.2 × Volume SMA20** — breakout me vëllim
7. Qiriu **mbyllet mbi swing-high** të fundit (maksimumi i 20 qirinjve të fundit + tampon 0.1%)

**Vetëm kur plotësohen TË GJITHA → BUY.** Jo "qiriu është jeshil, blej".

---

## 5) Pyramiding (BUY-BUY-BUY) — 40% → 30% → 30%

Sekuenca: **Breakout → Retest → BUY 1 → Higher High → BUY 2 → Higher High → BUY 3**

| Hapi | Kushti | Madhësia |
|------|--------|----------|
| **BUY 1** | Breakout + retest i mbajtur (çmimi nuk bie nën swing-low) | 40% |
| **BUY 2** | Çmimi bën **higher-high të ri** (1H) pas BUY 1 | 30% |
| **BUY 3** | Një **higher-high tjetër** (vazhdim trendi) | 30% |

**RREGULLI I ARTË:**
- Nëse pas BUY 1 tregu bie dhe sinjali prishet → **NUK bëhet BUY 2**.
- **Kurrë mos shto për të "ulur mesataren" (averaging down).** Pyramiding
  shtohet VETËM në drejtimin e fitimit, kurrë kundër tij.
- **Maksimumi 3 hyrje.** Nuk ka BUY 4, BUY 5, BUY 6.

---

## 6) Stop-loss (pjesa më e rëndësishme)

- SL **poshtë swing-low/retest-it** (minimumi i 20 qirinjve 1H), **JO një
  përqindje e rastësishme**.
- Shembull: hyrja mesatare 100€, zona që invalidon setup-in = 96€ → **SL ≈ 96€**
  (humbje maksimale ≈ **4%** e atij aseti).
- Pas çdo shtese (BUY 2, BUY 3), SL ngrihet në nivelin e ri të retest-it —
  por **kurrë më poshtë se hyrja mesatare** (mbrojtje).
- Nëse SL preket → **mbyllet GJITHË pozicioni i atij aseti** (jo vetëm një pjesë).

---

## 7) Marrja e fitimit (SELL-SELL-SELL — shitje graduale)

| Niveli | Veprimi |
|--------|---------|
| **+5–8%** | Shit **25%** e pozicionit (marr fitimin e parë) |
| **+10–15%** | Shit **25%** të tjera |
| **Pjesa tjetër** | **Trailing stop** (SL ndjek çmimin 3–4% poshtë majës) — e lë të vrapojë, por e mbyll kur trendi kthehet |

Kështu **nuk përpiqesh të kapësh majën** — merr fitim në rrugë dhe pjesën e
fundit e mbyll trailing-u kur trendi dobësohet.

---

## 8) SELL i plotë (dalja)

Pozicioni i atij aseti mbyllet i gjithë kur:
- **SL preket** (poshtë swing-low), ose
- **Filtri i trendit prishet**: çmimi bie nën **EMA 200 (4H)** ose
  **EMA 50 < EMA 200 (4H)** → tregu u kthye → dil, mos lufto trendin.

---

## 9) Shembull i plotë me 100€ për ETH

1. ETH në 4H: mbi EMA200, EMA50 > EMA200, RSI = 58 ✅ → lejohet të kërkohet hyrje
2. Në 1H: çmimi thyen swing-high me volum 1.5×, RSI = 61, qiri mbyllet sipër ✅
3. **BUY 1 = 40€** (hyrja mesatare 40€)
4. ETH bën higher-high → **BUY 2 = 30€** (mesatare tani ~ 70€)
5. Përsëri higher-high → **BUY 3 = 30€** (total 100€, mesatarja ~ çmimi i fundit)
6. SL = poshtë swing-low më të afërt (p.sh. −4% nga mesatarja)
7. +6% → shet 25% (25€) → fitim i parë i kyçur
8. +12% → shet 25% të tjera
9. Pjesa e mbetur 50% → trailing stop 4% → mbyll kur trendi dobësohet

---

## 10) Rregulli kryesor me një fjali

**Trend ↑ (EMA200/50) + breakout/retest me volum + RSI i shëndetshëm = BUY
(pjesë-pjesë, max 3). Trend ↓ = mos bli vetëm sepse çmimi është "më lirë".**

---

## 11) Testimi i ndershëm

- Kjo strategji duhet **testuar me të dhëna historike** dhe **pastaj në demo**
  (pikërisht çfarë po bëjmë në Waynis) para çdo paraje reale.
- Në bull market mund të duket shkëlqyeshme; në treg anësor humbet shpesh
  (SL të shumta të vogla).
- Tarifat (0.1%/anë) dhe slippage ndryshojnë rezultatin — i kemi të përfshira
  në simulim.
