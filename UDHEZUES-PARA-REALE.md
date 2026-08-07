# 💰 Udhëzuesi i Para Reale (Real Mode) — hap pas hapi

> ⚠️ **Lexoje tërësisht para se të aktivizosh Real Mode.**
> Këtu trajtojmë para të vërteta — gabimet kushtojnë.

---

## Hapi 1 — Krijo çelësat API në Binance (të sigurt)

1. Hap **binance.com** → logohesh → lart djathtas **profile → API Management**.
2. **Create API** → emër: `waynis-bot` → verifikimi (2FA/email/SMS).
3. Në **API restrictions** zgjidh **ENABLE ONLY THESE**:
   - ✅ **Enable Spot & Margin Trading**
   - ❌ **Enable Withdrawal** — **MBETET I FIKUR!** (rrjeti kryesor i sigurisë)
4. **Create** → do të shohësh **API Key** dhe **Secret Key**.
   - 📋 Kopjo **të dyja** — Secret-i shfaqet VETËM NJË HERË!

> 🔐 **KURRË mos i dërgo çelësat në chat ose në GitHub.** Ata futen
> VETËM te Render (hapi 2). Nëse dikush i ka çelësat + lejen e tërheqjes,
> mund t'i marrë paratë — prandaj tërheqja mbetet e fikur.

## Hapi 2 — Vër çelësat te Render (Environment)

1. Hap **dashboard.render.com** → shërbimi **waynis-ai**.
2. Tab-i **Environment** → **Add Environment Variable**:
   - Emri: `BINANCE_API_KEY` → Vlera: çelësi yt API
   - Emri: `BINANCE_API_SECRET` → Vlera: sekreti yt
3. **Save Changes** → Render rindez botin vetë.

## Hapi 3 — Zgjidh rajonin e duhur (E RËNDËSISHME!)

Binance-i bllokon IP-të nga SHBA (gabimi 451).

- ✅ **Render në Frankfurt (EU)** → Binance punon.
- ❌ **Render në Oregon/Ohio (US)** → Binance e bllokon → tregtitë reale dështojnë.

**Nëse shërbimi yt është në SHBA:** krijon një **Web Service të ri** me rajon
**Frankfurt (EU)** dhe lidh të njëjtën repo — pastaj fshij të vjetrin.

**Alternativë më e thjeshtë (nëse s'do ta ndërrosh rajonin):** përdor **OKX**
në vend të Binance (funksionon nga SHBA). Krijo çelësa në OKX →
okx.com → API → Create API → fik tërheqjet → pastaj te Render shto:
- `REAL_EXCHANGE=okx`
- `OKX_API_KEY`, `OKX_API_SECRET`, `OKX_PASSPHRASE`

## Hapi 4 — Aktivizo Real Mode te dashboard

1. Hap **https://waynis-ai-1.onrender.com** në telefon.
2. ⚙️ **Cilësimet** → rreshti **"💰 Para reale (Real Mode)"** → ndiz çelësin.
3. Konfirmo paralajmërimin → boti tani tregton **spot, vetëm LONG**:
   - Bletë me çmim tregu, menjëherë vë **TP (+0.45%)** dhe **SL (−0.35%)**
     si urdhra mbrojtës **në exchange** (edhe nëse boti fiket, pozicioni ruhet).
   - Maks **2 pozicione** njëkohësisht, maks **15% e balancës** për urdhër.

## Hapi 5 — Vëzhgo 1–2 javë

Para se të rrisësh shumën, lëre të punojë 1–2 javë dhe krahasoje me
**Paper mode me tarifa** (tani tarifat 0.1%/anë janë të simuluara edhe në
paper — kështu e sheh të vërtetën para se të rrezikosh).

---

## ❓ Pyetje të shpeshta

**Po më bllokon Binance nga Render-i?**
Shenjë: ngjarjet tregojnë "dështoi hapja" me 451. Zgjidhja: rajon Frankfurt
ose kaloni te OKX (shih Hapi 3).

**Po fiket Render-i (free plan)?**
Pas 15 min pa vizita, boti fle — por **TP/SL janë në exchange**, pra pozicionet
mbrohen gjithmonë. Për 24/7: UptimeRobot ping çdo 5 min (si më parë).

**Po humb para?**
Po, mundet — asnjë strategji nuk garanton fitim. Për këtë fillove me shumë të
vogël ($20–50) dhe me tërheqje të fikur: humbja maksimale është vetëm ajo
shumë.

**Si e fik Real Mode?**
Cilësimet → çelësi i Real Mode → fike. (Pozicionet e hapura mbeten në
exchange me TP/SL derisa të mbyllen — fikja e modalitetit nuk i shet
automatikisht.)
