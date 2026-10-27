# Voice Agents — 3 Alag Agents, Ek Hi Server (100% Free Stack)

Teenon agents — **Appointment Booking**, **Customer Support**, **Lead Qualification** —
ek hi FastAPI server pe chalte hain. Har agent ka apna prompt, apne tools, aur apna
Twilio webhook hai.

```
voice-agents/
├── server.py          # FastAPI + Twilio Media Streams (call receive karta hai)
├── brain.py           # Sunna (Whisper) → Sochna (Groq LLM) → Bolna (Piper TTS)
├── agents.py          # Teenon agents ke prompts + tools ki definition
├── tools_impl.py      # Tools ka asli kaam (validation ke saath)
├── demo_common.py     # Terminal demos ke shared helpers
├── demo_booking.py    # Booking agent ka end-to-end terminal demo
├── demo_support.py    # Support agent ka end-to-end terminal demo
├── demo_lead.py       # Lead agent ka end-to-end terminal demo
├── smoke_test.py      # Automated test: 17 checks (tools + validation + config)
├── start.sh           # Server start karne ki script
├── requirements.txt
├── .env / .env.example
└── data/
    ├── slots.json     # Available appointment slots
    ├── bookings.json  # Booked appointments
    ├── leads.csv      # Qualified leads + callback requests
    └── faq.md         # Support knowledge base
```

## Quick commands

```bash
./start.sh              # server chalao (pehli baar deps install hongi)
python smoke_test.py    # 17 automated checks
python demo_booking.py  # booking agent try karo (terminal me)
python demo_support.py  # support agent try karo
python demo_lead.py     # lead agent try karo
```

---

## Demo mode — bina API keys ke try karo (2 min)

`.env` me demo values hain to ye turant chalega (asli GROQ_API_KEY hai to asli LLM):

```bash
python demo_booking.py   # naam → "kal" → "11 baje" → phone number
python demo_support.py   # "refund kaise milega" → haan
                         # ya "mera printer blast ho gaya" → callback flow
python demo_lead.py      # need → budget → timeline → naam → phone
```

Tools **asli** chalte hain: booking `data/bookings.json` me, leads `data/leads.csv` me.
Junk/placeholder data tools **reject** kar dete hain aur LLM ko batate hain ki
caller se kya puchna hai — taaki galat leads kabhi save na hon.

---

| Cheez | Kahan se | Cost |
|---|---|---|
| Phone numbers | Twilio trial account | Free (trial credit ke saath) |
| Dimaag (LLM) | Groq free tier | Free |
| Sunna (STT) | faster-whisper (apne machine pe) | Free |
| Bolna (TTS) | Piper TTS (apne machine pe) | Free |
| Public URL | ngrok free | Free (testing ke liye) |

**Ek honest baat:** Twilio trial me **1 free number** milta hai. Teenon agents ke liye 2 options:
- **Free wala:** 1 number + IVR menu — "Appointment ke liye 1 dabayein, support ke liye 2, sales ke liye 3"
- **Alag-alag numbers:** har number ~$1/month + thoda call credit (~₹300-400/month total me teenon chal jayenge)

Neeche dono ka setup diya hai. Shuru free wale se karo.

---

## Step 1 — Public URL (domain)

Twilio ko tumhare server tak pahunchna hai, isliye public URL chahiye.

**Testing (free, 2 min):**
```bash
ngrok http 8000
# milega kuch aisa: https://abcd-1234.ngrok-free.app
# Note: free ngrok restart hone pe URL badal jata hai
```

**Permanent (jab serious ho):** koi sasta VPS (Hostinger/Contabo ~₹400/month) +
koi sasta domain, phir Caddy/Nginx se HTTPS. Code me kuch badalna nahi padega —
sirf `PUBLIC_DOMAIN` env variable update karna hai.

---

## Step 2 — Twilio setup (3 alag numbers)

1. [twilio.com/try-twilio](https://www.twilio.com/try-twilio) pe account banao
2. **3 alag phone numbers** lo (Phone Numbers → Buy a Number). Trial me pehla free milta hai,
   baaki ~$1/month each.
3. Har number ke **Voice webhook** (HTTP POST) me apne agent ka URL daalo:

   | Number | Webhook URL | Agent |
   |---|---|---|
   | +17372508034 (tumhara number) | `https://TUMHARA-DOMAIN/voice/booking` | Appointment Booking |
   | Number 2 | `https://TUMHARA-DOMAIN/voice/support` | Customer Support |
   | Number 3 | `https://TUMHARA-DOMAIN/voice/lead` | Lead Qualification |

4. `.env` me `TWILIO_ACCOUNT_SID` aur `TWILIO_AUTH_TOKEN` daalo

Teenon agents ek hi server pe chalte hain, lekin teenon ke number, webhook aur
conversation bilkul alag hain — ek dusre se koi link nahi.

> **Budget option:** agar shuru me 1 hi number lena hai to uske webhook me
> `https://TUMHARA-DOMAIN/voice/menu` daalo — caller 1/2/3 dabake agent choose karega.

---

## Step 3 — Groq API key (free LLM)

1. [console.groq.com](https://console.groq.com) pe account banao
2. API key banao → `.env` me `GROQ_API_KEY` me daalo
3. Free tier kaafi hai — Llama 3.3 model bahut fast hai (low latency = human-like feel)

---

## Step 4 — Server setup

```bash
cd voice-agents
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Piper Hindi voice download karo (piper-voices repo se hi_IN voice)
mkdir -p voices
# https://github.com/rhasspy/piper-voices se Hindi voice (.onnx + .onnx.json) download karke voices/ me rakho

cp .env.example .env
# .env me apni values bhardo

# Pehli baar Whisper model download hoga (~500MB for 'small')
python server.py
```

Phir doosre terminal me:
```bash
ngrok http 8000
```

---

## Step 5 — Test call

1. ngrok wala URL `.env` ke `PUBLIC_DOMAIN` me daalo, server restart karo
2. Twilio number pe apne phone se call karo
3. Menu sunai dega → 1/2/3 dabao → agent se baat karo!

---

## Teenon agents kya karte hain

**1. Appointment Booking** (`/voice/booking`)
- Naam, date, time puchta hai
- `check_slots` tool se khaali slots dekhta hai
- `book_appointment` se `data/bookings.json` me save karta hai

**2. Customer Support** (`/voice/support`)
- Sawal sunke `search_faq` se `data/faq.md` me jawab dhundta hai
- Jawab na mile to callback request note karke `data/leads.csv` me daalta hai

**3. Lead Qualification** (`/voice/lead`)
- 4 cheezein puchta hai: kya chahiye, budget, timeline, contact number
- `save_lead` se `data/leads.csv` me save karta hai

---

## Human-like feel ke liye jo already built-in hai

- **Barge-in:** beech me bologe to agent ruk jayega
- **Chhote jawab:** prompts me 1-2 line ki limit hai
- **Backchanneling:** prompts me "hmm", "achha", "samajh gaya" use karne ko bola gaya hai
- **Streaming:** Groq fast hai, isliye jawab me delay kam

## Production me jaane se pehle (TODO)

- [ ] ngrok ki jagah permanent domain + VPS
- [ ] Trial ki jagah paid Twilio (trial me call ke shuru me "trial account" message aata hai)
- [ ] `data/` ki jagah asli database (SQLite/Postgres) + Google Calendar integration
- [ ] Call recordings + transcripts ka log
- [ ] Hindi STT accuracy ke liye Deepgram ka free credit try karo (faster-whisper se better hai)
