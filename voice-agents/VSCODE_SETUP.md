# VS Code Setup Guide — Voice Agents (apne computer pe)

Ye guide tumhe apne laptop/PC pe VS Code me poora project chalane me help karegi.
Total time: ~30-45 min (pehli baar models download honge).

---

## Ha, teeno agent alag-alag hain

| Agent | File (prompt+tools) | Webhook | Kya karta hai |
|---|---|---|---|
| Booking | `agents.py` → `"booking"` | `/voice/booking` | Slot check + appointment book (`data/bookings.json`) |
| Support | `agents.py` → `"support"` | `/voice/support` | FAQ se jawab, na mile to callback (`data/leads.csv`) |
| Lead | `agents.py` → `"lead"` | `/voice/lead` | Need/budget/timeline puchke lead save (`data/leads.csv`) |

Teenon ka code ek hi server (`server.py`) pe hai, lekin prompt, tools, webhook
aur data flow sab alag — neeche `agents.py` khol ke khud dekh sakte ho.

---

## Step 0 — Install karo

1. **Python 3.10+**: [python.org/downloads](https://www.python.org/downloads/) — install karte waqt
   **"Add python.exe to PATH"** tick karna mat bhoolna (Windows pe zaroori hai)
2. **VS Code**: [code.visualstudio.com](https://code.visualstudio.com/)
3. VS Code me **Python extension** install karo (Microsoft wali)

Check karo terminal me:
```
python --version
```

## Step 1 — Project kholo

1. `voice-agents.zip` ko unzip karo (koi bhi folder me, jaise `Documents/voice-agents`)
2. VS Code kholo → **File → Open Folder** → `voice-agents` folder select karo
3. VS Code me terminal kholo: **Terminal → New Terminal** (Ctrl + `)

## Step 2 — Virtual environment banao

```bash
# Windows:
python -m venv venv
venv\Scripts\activate

# Mac/Linux:
python3 -m venv venv
source venv/bin/activate
```

Terminal me `(venv)` dikhna chahiye. VS Code neeche right me bhi interpreter
select karne ko bolega — `venv` wala choose kar lena.

## Step 3 — Dependencies install karo

```bash
pip install -r requirements.txt
```

> Note: `faster-whisper` ke saath torch download hoga (~2GB). Pehli baar time lagega,
> ghabrana mat. Agar Windows pe error aaye to: `pip install --upgrade pip` karke dobara try karo.

## Step 4 — Piper Hindi voice download karo

1. [piper-voices releases](https://github.com/rhasspy/piper-voices/releases) kholo
2. **Hindi (hi_IN)** voice ki 2 files download karo: `.onnx` aur `.onnx.json`
3. Dono ko project ke `voices/` folder me rakho
4. Naam `.env` se match hone chahiye:
   ```
   PIPER_MODEL_PATH=voices/hi_IN.onnx
   PIPER_CONFIG_PATH=voices/hi_IN.onnx.json
   ```
   (Agar file ka naam alag hai to ya to rename karo, ya `.env` me naam badal do)

## Step 5 — .env check karo

`.env` file me tumhari keys **pehle se bhari hui** hain (Groq + Twilio).
Sirf ek cheez baad me badlegi: `PUBLIC_DOMAIN` (Step 6 me).

```bash
# Bina Twilio ke pehle demo try karo (koi install ke baad turant):
python demo_booking.py
python demo_support.py
python demo_lead.py
python smoke_test.py    # 17 checks — sab PASS hone chahiye
```

## Step 6 — ngrok (Twilio ko tumhare laptop tak pahunchne ke liye)

1. [ngrok.com](https://ngrok.com/) pe free signup karo → **authtoken** milega
2. [Download](https://ngrok.com/download) karke install karo, phir:
   ```bash
   ngrok config add-authtoken TUMHARA_TOKEN
   ```
3. Server chalao (VS Code ke terminal me):
   ```bash
   python server.py
   ```
4. **Doosra terminal** kholo (Ctrl+Shift+`) aur:
   ```bash
   ngrok http 8000
   ```
   Tumhe URL milega jaise `https://abcd-1234.ngrok-free.app`
5. `.env` me ye line update karo aur server **restart** karo:
   ```
   PUBLIC_DOMAIN=abcd-1234.ngrok-free.app
   ```
   (Free ngrok har restart pe URL badalta hai — yaad rakhna)

## Step 7 — Twilio webhook lagao

1. [Twilio console](https://console.twilio.com/) → **Phone Numbers** → apna number kholo
2. **Voice Configuration** me:
   - "A call comes in" → **Webhook**
   - URL: `https://TUMHARA-NGROK-URL/voice/booking`
   - Method: **HTTP POST**
   - Save karo
3. (3 numbers hain to har number pe apna webhook: `/voice/support`, `/voice/lead`)

## Step 8 — Live test! 📞

Apne phone se Twilio number pe call karo → agent Hindi me baat karega.
Booking karo → `data/bookings.json` me entry dikhegi.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `python` nahi mil raha | PATH me add karo, phir VS Code restart |
| `pip install` slow/fail | `pip install --upgrade pip` phir dobara |
| Whisper model download slow | Pehli baar ~500MB, normal hai |
| `Piper voice files nahi milein` | Step 4 dobara check karo, naam `.env` se match karo |
| Twilio call pe kuch nahi bolta | ngrok chal raha hai? `PUBLIC_DOMAIN` sahi hai? Server restart kiya? |
| Call ke start me "trial account" bajta hai | Normal hai — paid Twilio pe hat jayega |
| Port 8000 busy | `server.py` dobara to nahi chal raha? Ek hi instance rakho |

## File ka matlab (quick map)

- `server.py` — Twilio se call aati hai, audio ka pipeline chalata hai
- `brain.py` — sunna/sochna/bolna (Whisper → Groq → Piper)
- `agents.py` — teenon agents ke dimaag (prompts) — **yahi edit karke agent ka behaviour badlo**
- `tools_impl.py` — booking/FAQ/lead ka asli kaam + validation
- `data/faq.md` — apne business ke Q&A yahan likho (support agent yahi padhta hai)
- `data/slots.json` — appointment ke khaali slots yahan badlo
