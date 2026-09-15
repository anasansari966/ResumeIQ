# ResumeIQ — Dev login accounts

Seeded automatically when the backend starts (`app.services.seed_users`).

| Role | Email | Password |
|------|-------|----------|
| Superadmin | `admin@resumeiq.dev` | `Admin@12345` |
| User | `user@resumeiq.dev` | `User@12345` |

Both accounts are **email-verified** (no OTP needed).

## Run (local)

**Important:** Port **8000** is often used by other apps on this machine. ResumeIQ uses **8010**.

**Terminal 1 — API:**

```powershell
cd D:\ResumeIQ\backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

**Terminal 2 — UI:**

```powershell
cd D:\ResumeIQ\frontend
npm run dev
```

Open: http://localhost:5173/resumeiq/login

Vite proxies `/api` → `http://127.0.0.1:8010` (`frontend/.env.development`).

## NVIDIA LLM keys

OpenAI powers parse / ATS structure / tailor / jobs AI.

Get a key from https://platform.openai.com/api-keys and put it in the repo-root `.env` or `backend/.env`:

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_TEMPERATURE=0.2
OPENAI_MAX_TOKENS=4096
OPENAI_TIMEOUT=120
```

Check: `GET http://127.0.0.1:8010/health/llm`
