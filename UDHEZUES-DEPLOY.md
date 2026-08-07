# 🚀 Deploy pa GitHub — UDHËZUES

Kjo paketë ka vetëm **3 skedarë** dhe punon pa GitHub, pa token, pa komanda:

- **app.py** — e gjithë aplikacioni (bot + dashboard) në një skedar të vetëm
- **Dockerfile** — për **Hugging Face Spaces** (host falas, më i rekomanduari)
- **package.json** — për **Glitch** (alternativë edhe më e thjeshtë)

---

## ✅ Opsioni 1 — Hugging Face Spaces (rekomandohet)

Host falas dhe i besueshëm. Nuk të duhet asgjë tjetër përveç një email-i.

1. **Hap** `huggingface.co` në Chrome → **Sign up** (email, fjalëkalim — 1 min).
2. Kliko **fotografinë tënde** (lart djathtas) → **+ New Space**.
3. Mbush:
   - **Space name:** `waynis-ai`
   - **License:** çfarëdo (p.sh. MIT)
   - **SDK:** zgjidh **Docker**
   - **Space hardware:** `CPU basic` (Free)
   - **Visibility:** **Public**
   - → **Create Space**
4. Hap tab-in **Files** → butoni **"Upload files"**:
   - zgjidh **app.py** dhe **Dockerfile** (2 skedarë) → **Commit changes to main**
5. **Prit 2–3 minuta** (tab-i **Builder** tregon përparimin — "Building...").
6. Kur mbaron: URL-ja jote është:
   `https://EMRI_YT-waynis-ai.hf.space`
7. Hape atë URL në telefon → **⋮ → Add to Home screen** → gati! ✅

### ⏰ Që të mos flejë kurrë (opsionale, falas)
HF e vë në gjumë pas 48 orësh pa vizita. Për ta mbajtur zgjuar:
**uptimerobot.com** → krijo llogari falas → **New monitor** →
HTTP → ngjit URL-në → interval **5 min**. Kjo e mban botin gjithmonë duke punuar.

---

## ✅ Opsioni 2 — Glitch (edhe më i thjeshtë, pa Docker)

1. Hap `glitch.com` → **Sign in** (me Google ose email).
2. **New project** → **glitch-hello-express** (ose import).
3. Fshi skedarët e parazgjedhur (server.js, public/, etj.).
4. Ngarko **app.py** dhe **package.json** në pemën e skedarëve.
5. Glitch-i e nis vetë → URL: `https://emri-i-projektit.glitch.me`
6. Hape në telefon → **Add to Home screen** → gati!

> Glitch fle pas ~5 min pushim → UptimeRobot e mban zgjuar njësoj.

---

## 🎯 Çfarë duhet të dish

- **Të dy hostet janë falas** dhe pa GitHub.
- Boti punon njësoj si këtu: 6 agjentë, AI (auto → Pollinations falas → simbolik), compound, chart live.
- WebSocket-i mund të mos punojë në këto hoste — **por dashboard-i ka polling automatik**, kështu që gjithçka funksionon njësoj.
- Nëse ndonjë ditë e lësh botin, thjesht hap URL-në dhe e ndez sërish.
