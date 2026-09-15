# ResumeIQ — Product Overview

**Version:** 0.1.0 (from FastAPI app metadata)  
**Last updated:** June 2026  
**Audience:** Product, engineering, deployment, and stakeholders

---

## 1. Executive summary

**ResumeIQ** is a full-stack web application that helps job seekers **build, score, and export ATS-friendly resumes**, **discover jobs**, and **track applications** in one workspace. Users can upload an existing resume or create one step-by-step, choose from **LaTeX-based resume templates** (Chicago, Classic, Easy, Milano), run **ATS scoring**, and export **PDFs that match the selected template layout**.

The product pairs a **React** single-page UI with a **FastAPI** backend. Optional **OpenAI** powers parsing, summaries, and job intelligence; **LaTeX (pdflatex)** is required on the server for template-accurate PDF export.

---

## 2. Product vision & value proposition

| Problem | ResumeIQ response |
|--------|-------------------|
| Resumes fail ATS parsers | Structured JSON resume model + ATS scoring with actionable suggestions |
| Generic PDF exports | Packaged LaTeX templates with server-side compilation |
| Scattered job search | Job listings, match scores, and application kanban in one app |
| Slow first resume | Upload → parse → template → edit in minutes |

**Primary value:** A **template-first, ATS-aware** resume workflow from upload through export, with job tracking as a secondary pillar.

---

## 3. Target users

- **Job seekers** updating or creating a professional resume  
- **Career switchers** who want ATS feedback before applying  
- **Power users** who care about LaTeX layout quality for PDF output  

---

## 4. Feature catalog

### 4.1 Authentication & account

- Email registration with **OTP verification** (SMTP optional; dev OTP in API when email is disabled)
- Login (verified email required)
- Forgot / reset password via OTP
- JWT bearer authentication stored in browser `localStorage`
- User profile fields: name, email, plan (`free` by default)

### 4.2 Onboarding (first-time flow)

Route: `/resume/onboarding`

1. **Upload** PDF, DOCX, or TXT resume  
2. Backend **parses** file into structured JSON + **ATS baseline** score  
3. User **selects a template** from the catalog (with preview thumbnails)  
4. Template applied to resume; user redirected to **editor**  
5. Onboarding completion flag stored per user (`localStorage`)

Returning users can **re-upload** from the same page without repeating the full gate.

### 4.3 Dashboard

Route: `/dashboard`

- Overview stats: total resumes, jobs saved, applications sent, average ATS score  
- Recent resume cards (edit, download PDF, duplicate, delete)  
- Job recommendations (top matches from seeded listings)  
- Quick actions: **Upload resume**, **Create resume** (builder)

### 4.4 Resume builder (from scratch)

Route: `/resume/new`

Five-step wizard:

1. Personal info  
2. Work experience  
3. Education  
4. Skills  
5. Template selection & export  

Creates resume via upload/patch pipeline when direct create is unavailable.

### 4.5 Resume editor

Route: `/resume/:id/edit`

- Section-based editing: personal, summary, experience, skills  
- **Live preview** (HTML) + **template selector** with layout thumbnail  
- **Auto-save** (debounced PATCH with optional ATS recalculation)  
- **Check ATS** — detailed score, dimensions, suggestions  
- **Export PDF** — LaTeX template PDF (requires server LaTeX)  
- **Export TEX** — downloadable LaTeX source  
- **ATS Panel** — side panel for scoring details  

### 4.6 Template system

- **Catalog API:** `GET /api/v1/templates`  
- **Packaged templates:** ZIP files under `backend/templates/` → extracted to `backend/templates/.extracted/`  
- Current catalog (when zips present): **Chicago, Classic, Easy, Milano**  
- Each template has: name, ATS score badge, description, **preview image** (`GET /api/v1/templates/{id}/preview`)  
- **HTML preview:** `GET /api/v1/templates/{id}/preview-html` (optional resume data)  
- **Web import:** `POST /api/v1/templates/import-web` — import remote `.tex` / `.zip` URL  
- **Template select** blends content ATS with template ATS:  
  `0.42 × content + 0.58 × template_score` (cap 100)

### 4.7 PDF export pipeline

For LaTeX template IDs (`zip_*`, folder, or built-in LaTeX):

1. Render resume JSON into template-specific LaTeX (`resume_template_engine`)  
2. Compile with **pdflatex** in the template’s `.extracted` folder when applicable  
3. Return PDF with headers: `X-ResumeIQ-Render-Mode: latex`, `X-ResumeIQ-Template-Id`

If no LaTeX engine is found → **HTTP 503** (no silent generic PDF for LaTeX templates).

Fallback **ReportLab** PDF exists only for non-LaTeX export paths.

### 4.8 ATS scoring

Engine: `ats_engine.py` — weighted dimensions:

| Dimension | Weight |
|-----------|--------|
| Keyword match (vs JD or default) | 35% |
| Format compliance | 20% |
| Content completeness | 20% |
| Quantification (metrics in bullets) | 10% |
| Length optimization | 8% |
| Skills alignment | 7% |

**Triggered on:** upload, patch with `recalc_ats`, template change, re-salvage, AI summary, tailor session.  
**Standalone:** `POST /api/v1/ats/score`

### 4.9 Jobs

Route: `/jobs`

- Search and filter **seeded job listings** in the database  
- Match score vs resume skills (`GET /jobs/match`)  
- Save jobs to **Applications**  
- Backend also exposes **live JobSpy + SerpAPI** search (`POST /jobs/jsearch/smart`) — not wired in current frontend UI

### 4.10 Applications

Route: `/applications`

- Kanban board: **Saved → Applied → Interview → Offer → Rejected**  
- Drag-and-drop status updates  
- Linked to resume and job listing records  

### 4.11 Subscription & profile (UI)

Routes: `/subscription`, `/profile`

- Pricing tiers displayed (Free / Basic / Pro)  
- Profile settings UI  
- **Note:** No payment or profile-update API integrated yet; `User.plan` defaults to `free`

### 4.12 Tailoring (backend only)

API under `/api/v1/tailor` and `/api/v1/jd`:

- Analyze job description  
- AI-generate tailored resume JSON  
- Stream preview tokens (SSE)  
- Export tailored PDF  

**No dedicated frontend page** in the current SPA; available for future UI or integrations.

---

## 5. User journeys

### Journey A — New user (upload path)

```
Register → Verify OTP → Login → Onboarding upload → Pick template → Editor → Export PDF
```

### Journey B — New user (builder path)

```
Register → … → Dashboard → Create resume → 5-step wizard → Save → Editor → Export PDF
```

### Journey C — Returning user

```
Login → Dashboard → Edit resume / change template → Export PDF
                  → Jobs → Save application → Applications kanban
```

### Journey D — ATS optimization

```
Editor → Edit sections → Check ATS → Apply suggestions → Re-export PDF
```

---

## 6. System architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (React SPA @ /resumeiq/)                           │
│  - Vite build in production, dev server + /api proxy in dev │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTPS / JSON  /api/v1/*
┌───────────────────────────▼─────────────────────────────────┐
│  FastAPI (Uvicorn)                                          │
│  Routers: auth, resumes, templates, ats, jobs,            │
│           applications, jd, tailor                          │
│  Services: parse, ATS, LaTeX export, jobs, OTP, catalog   │
└───────┬─────────────────────────────┬───────────────────────┘
        │                             │
        ▼                             ▼
┌───────────────┐            ┌────────────────────┐
│ SQLite/MySQL  │            │ External services  │
│ User, Resume, │            │ NVIDIA NIM, SMTP,  │
│ JobListing,   │            │ SerpAPI, JobSpy,   │
│ Application,  │            │ pdflatex (local)   │
│ TemplateCatalog            └────────────────────┘
└───────────────┘
```

### Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, Vite 5, React Router 6, Tailwind CSS, Axios |
| Backend | FastAPI, SQLModel, Pydantic Settings, async SQLAlchemy |
| Auth | bcrypt + JWT (python-jose) |
| DB | SQLite (default) or MySQL (`aiomysql`) |
| PDF | pdflatex / MiKTeX / TeX Live; ReportLab fallback |
| Parsing | pypdf, pdfplumber, mammoth, optional OpenAI |
| Jobs | python-jobspy, SerpAPI (optional) |

---

## 7. Frontend routes

| Path | Page | Gate |
|------|------|------|
| `/` | Redirect to dashboard or onboarding | Auth |
| `/login`, `/register`, `/forgot-password` | Auth pages | Public |
| `/resume/onboarding` | Upload + template pick | Auth |
| `/dashboard` | Dashboard | Auth + onboarding |
| `/resume/new` | Builder wizard | Auth + onboarding |
| `/resume/:id/edit` | Editor | Auth + onboarding |
| `/jobs` | Job search | Auth + onboarding |
| `/applications` | Kanban | Auth + onboarding |
| `/subscription` | Pricing UI | Auth + onboarding |
| `/profile` | Profile UI | Auth + onboarding |

**Base URL:** `/resumeiq/` (configured in Vite `base`).

---

## 8. API reference (summary)

**Base:** `/api/v1`  
**Health:** `GET /health`

### Auth — `/auth`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/register` | Create account, send OTP |
| POST | `/verify-otp` | Verify email → JWT |
| POST | `/login` | Login → JWT |
| POST | `/resend-otp` | Resend registration OTP |
| POST | `/forgot-password` | Request reset OTP |
| POST | `/reset-password` | Reset password → JWT |
| GET | `/me` | Current user |

### Resumes — `/resumes`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/upload` | Upload + parse + ATS baseline |
| GET | `/` | List resumes |
| GET | `/{id}` | Get resume |
| PATCH | `/{id}` | Update JSON (`recalc_ats` optional) |
| DELETE | `/{id}` | Soft delete |
| POST | `/{id}/generate-summary` | AI summary |
| POST | `/{id}/select-template` | Set active template + blended ATS |
| POST | `/{id}/re-salvage` | Re-normalize parsed JSON |
| GET | `/{id}/export-pdf` | PDF export (`?template_id=`) |
| GET | `/{id}/export-tex` | LaTeX source download |

### Templates — `/templates`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List active templates |
| POST | `/import-web` | Import remote LaTeX URL |
| GET | `/{id}/preview` | Template thumbnail (SVG/PNG) |
| GET | `/{id}/preview-html` | HTML layout preview |

### ATS — `/ats`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/score` | Score resume JSON vs optional JD keywords |

### Jobs — `/jobs`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/search` | Search seeded listings |
| GET | `/match` | Match listings to resume |
| POST | `/jsearch/smart` | Live JobSpy search |
| POST | `/listing/{id}/refresh-description` | Fetch JD from apply URL |

### Applications — `/applications`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List applications |
| POST | `/` | Create / upsert application |
| PATCH | `/{id}` | Update status, notes |

### JD & Tailor — `/jd`, `/tailor`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/jd/analyze` | Parse and store job description |
| POST | `/tailor` | Generate tailored resume session |
| GET | `/tailor/stream/preview` | SSE tailored content stream |
| GET | `/tailor/{id}/pdf` | Tailored PDF export |

---

## 9. Data model (core entities)

| Entity | Purpose |
|--------|---------|
| **User** | Account, email verification, plan |
| **EmailOtpCode** | Registration / password-reset OTP |
| **Resume** | `parsed_json`, `ats_baseline`, `active_template_id`, soft delete |
| **TemplateCatalog** | Synced template metadata from registry |
| **JobListing** | Seeded + scraped job rows |
| **Application** | User ↔ job ↔ resume, status pipeline |
| **JDAnalysis** | Parsed job description |
| **TailoringSession** | AI-tailored resume output |

See also `DB_working.md` and `backend/sql/resumeiq_schema.sql` for database details.

---

## 10. Configuration & environment

Config loads from **repo root `.env`** then **`backend/.env`** (backend overrides).

### Essential (production)

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | JWT signing — **must change in production** |
| `DATABASE_URL` or `USE_MYSQL` + `MYSQL_*` | Database connection |
| `CORS_ORIGINS` | Allowed frontend origins |
| `OPENAI_API_KEY` | Parsing, summaries, tailor, job AI (optional but recommended) |
| `NVIDIA_MODEL` | Default `moonshotai/kimi-k3` |
| `NVIDIA_TEMPERATURE` | Default `0.4` |
| `NVIDIA_MAX_TOKENS` | Default `16384` |
| `LATEX_PDFLATEX` or `LATEX_PATH_EXTRA` | PDF export for LaTeX templates |

### LaTeX (PDF export)

| Variable | Example |
|----------|---------|
| `LATEX_PDFLATEX` | Full path to `pdflatex.exe` or `/usr/bin/pdflatex` |
| `LATEX_PATH_EXTRA` | Directory containing `pdflatex` (prepended to PATH) |

On Windows, the backend also scans common MiKTeX install folders when these are unset.

### Email (OTP)

| Variable | Purpose |
|----------|---------|
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Send verification emails |

If SMTP is empty, OTP may appear in API responses for development.

### Jobs (optional)

`SERPAPI_KEY`, `JOBSPY_SITES`, and related limits — see `backend/app/config.py`.

### Frontend (build-time)

| Variable | Default |
|----------|---------|
| `VITE_BASE` | `/resumeiq/` |
| `VITE_DEV_API_TARGET` | `http://127.0.0.1:8000` |
| `VITE_API_URL` | Optional absolute API origin for production |

---

## 11. Local development

### Backend

```powershell
cd backend
pip install -r requirements.txt
# Configure backend/.env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

Or use `backend/start-backend.ps1` (default port **8010** — port 8000 is often taken by other local apps).

Demo accounts (seeded on startup): see `DEV_CREDENTIALS.md` (`admin@resumeiq.dev` / `user@resumeiq.dev`).

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open: `http://localhost:5173/resumeiq/` (API proxied to port 8000).

### Production-style (single server)

```powershell
cd frontend && npm run build
cd ../backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

App UI: `http://localhost:8000/resumeiq/`  
API: `http://localhost:8000/api/v1/...`

---

## 12. Deployment guide

### Application server

1. Install **Python 3.11+** and dependencies from `backend/requirements.txt`  
2. Install **TeX Live** (Linux) or **MiKTeX** (Windows) for PDF export  
3. Set environment variables (see §10) on the **process** that runs Uvicorn/Gunicorn  
4. Build frontend: `npm run build` → serve `frontend/dist` via FastAPI mount at `/resumeiq/`  
5. Run migrations via app startup (`init_db`) or apply `backend/sql/resumeiq_schema.sql` for MySQL  
6. Use a reverse proxy (nginx, Caddy) for HTTPS and optional static caching  

### Linux (TeX)

```bash
sudo apt-get install -y texlive-latex-base texlive-latex-recommended texlive-fonts-recommended
which pdflatex   # confirm /usr/bin/pdflatex
```

### Docker considerations

- Use a image layer that installs TeX; slim images will **not** export LaTeX PDFs without it  
- Pass `LATEX_PDFLATEX` if PATH inside the container is minimal  
- Mount persistent volume for SQLite or use managed MySQL  

### Checklist before go-live

- [ ] Strong `SECRET_KEY`  
- [ ] Production database (MySQL recommended)  
- [ ] SMTP configured for OTP email  
- [ ] `pdflatex` verified from the same user/service that runs the API  
- [ ] `CORS_ORIGINS` set to production frontend URL  
- [ ] Frontend built with correct `VITE_BASE` and optional `VITE_API_URL`  

---

## 13. Project structure

```
ResumeIQ/
├── PRODUCT_OVERVIEW.md      ← this document
├── DB_working.md            ← database notes
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI entry, SPA mount
│   │   ├── config.py        # Settings
│   │   ├── routers/         # HTTP API
│   │   ├── services/        # Business logic
│   │   └── static/template_previews/
│   ├── templates/           # Packaged .zip LaTeX templates
│   ├── requirements.txt
│   └── .env                 # Secrets (not committed)
├── frontend/
│   ├── src/pages/           # Route pages
│   ├── src/components/      # UI components
│   ├── src/hooks/           # Data hooks
│   └── dist/                # Production build
└── Templates/               # Optional folder-based LaTeX imports
```

---

## 14. Known limitations & future work

| Area | Current state |
|------|----------------|
| Live job search UI | API exists; frontend uses seeded DB listings |
| Resume tailoring UI | Backend + SSE; no SPA page |
| Subscription billing | UI only; no Stripe/payment integration |
| Profile updates | UI only; no PATCH user API |
| JWT refresh | Frontend references refresh; backend has no refresh route |
| DOCX export | Endpoint disabled; TEX fallback offered |
| Live preview vs PDF | Editor preview is HTML; PDF uses LaTeX (may differ visually) |

---

## 15. Glossary

| Term | Meaning |
|------|---------|
| **ATS** | Applicant Tracking System — software employers use to parse and rank resumes |
| **Baseline ATS** | Score stored on the resume record after upload or recalculation |
| **Parsed JSON** | Canonical resume structure (contact, experience, skills, etc.) |
| **Template ID** | e.g. `zip_milano_latex_resume_template_free_download` |
| **Packaged template** | LaTeX resume shipped as `.zip` under `backend/templates/` |
| **Onboarding gate** | First-time users must complete upload/template flow before dashboard |

---

## 16. Support & troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| PDF export 503 | No `pdflatex` for API process | Set `LATEX_PDFLATEX` in `.env`; install MiKTeX/TeX Live; restart API |
| OTP not received | SMTP not configured | Configure SMTP or use `dev_otp` in dev responses |
| Empty job list | No seeds / DB reset | Restart app to seed listings or run job import |
| Template preview blank | Stale frontend build | `npm run build` + hard refresh |
| Login loop | Unverified email | Complete OTP verification |

---

*This document reflects the ResumeIQ codebase as implemented. For schema-level detail, see `DB_working.md`.*
