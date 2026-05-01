# 🤖 AI Assistant Pro — Full Edition

> Llama 3 (Groq) · Image Vision · PDF/DOCX · Supabase Memory · Auto Web Search

---

## ✅ Features

| Feature | Status | Free? |
|---|---|---|
| Chat (Llama 3 / Groq) | ✅ | ✅ Free |
| Auto web search | ✅ | ✅ Free (2500/mo) |
| Image understanding (LLaVA) | ✅ | ✅ Free |
| PDF upload & analysis | ✅ | ✅ Free |
| DOCX upload & analysis | ✅ | ✅ Free |
| CSV / code file upload | ✅ | ✅ Free |
| Persistent memory (Supabase) | ✅ | ✅ Free (500MB) |
| Calculator / weather / datetime | ✅ | ✅ Free |
| Session history sidebar | ✅ | ✅ Free |
| Copy code blocks | ✅ | ✅ Free |

---

## 🚀 Quick Start (Local)

```bash
cd backend
cp .env.example .env
# Fill in your keys (see below)

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Open `frontend/index.html` in your browser.

---

## 🔑 API Keys (All Free)

### 1. Groq — REQUIRED (AI engine)
1. Go to https://console.groq.com
2. Sign up → API Keys → Create key
3. Add to `.env`: `GROQ_API_KEY=gsk_...`

### 2. Supabase — REQUIRED for persistent memory
1. Go to https://supabase.com → New project (free)
2. SQL Editor → paste contents of `supabase_setup.sql` → Run
3. Settings → API → copy Project URL and anon key
4. Add to `.env`:
   ```
   SUPABASE_URL=https://xxxx.supabase.co
   SUPABASE_KEY=eyJ...
   ```

### 3. Serper — OPTIONAL (web search)
1. Go to https://serper.dev → free account (2500 searches/month)
2. Add to `.env`: `SERPER_API_KEY=...`
> Without this, AI will note it can't search but still answers from training data

### 4. OpenWeather — OPTIONAL (weather tool)
1. Go to https://openweathermap.org → free API key
2. Add to `.env`: `OPENWEATHER_KEY=...`

---

## 🌐 Deploy to Render

1. Push project to GitHub
2. render.com → New → Blueprint → connect repo
3. Set these env vars in Render dashboard:
   - `GROQ_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `SERPER_API_KEY` (optional)
4. Deploy → live in ~2 min

---

## 🔄 Swap AI Models

Change `GROQ_MODEL` in `.env`:

| Model | Best for |
|---|---|
| `llama3-8b-8192` | Fast everyday chat (default) |
| `llama3-70b-8192` | Complex reasoning |
| `mixtral-8x7b-32768` | Long documents |
| `gemma2-9b-it` | Alternative |

---

## 📁 Project Structure

```
ai-assistant/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   ├── routers/
│   │   ├── chat.py       # /api/chat, /api/chat/stream, /api/chat/upload
│   │   ├── memory.py     # /api/sessions
│   │   ├── tools.py      # /api/tools
│   │   └── health.py     # /api/health
│   └── services/
│       ├── model_service.py    # Groq + vision + agentic loop
│       ├── memory_service.py   # Supabase + file fallback
│       ├── file_service.py     # PDF, DOCX, image, CSV parsing
│       └── tool_service.py     # Web search, calculator, weather
├── frontend/
│   └── index.html        # Full chat UI
├── supabase_setup.sql    # Run once in Supabase SQL editor
└── render.yaml           # Render deployment
```
