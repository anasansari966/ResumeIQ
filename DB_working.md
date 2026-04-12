# DB_working — How ResumeIQ Uses the Database

This document describes how the backend connects to the database, when schema is created or updated, and how each HTTP request obtains a session and runs queries.

---

## 1. Which database?

Connection is resolved in `app/config.py` by `resolved_database_url()`:

| Priority | Condition | Resulting DSN |
|----------|-----------|----------------|
| 1 | `DATABASE_URL` is set (non-empty) | Used as-is (e.g. `mysql+aiomysql://...` or `sqlite+aiosqlite:///...`) |
| 2 | `USE_MYSQL=true` and no explicit `DATABASE_URL` | Built from `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB`. User and password are URL-encoded (`quote_plus`) so special characters in passwords do not break the URL. |
| 3 | Otherwise | Default SQLite file: `sqlite+aiosqlite:///./resumeiq.db` (created relative to the process working directory) |

Environment variables are loaded by **pydantic-settings** from:

- Repo root `.env` (if present), then  
- `backend/.env` (last wins for duplicate keys)

See `Settings` in `app/config.py` for field names and aliases (`USE_MYSQL`, `MYSQL_*`, etc.).

---

## 2. Stack

- **ORM / models**: [SQLModel](https://sqlmodel.tiangolo.com/) (Pydantic + SQLAlchemy).
- **Async engine**: `sqlalchemy.ext.asyncio.create_async_engine` with:
  - `mysql+aiomysql` for MySQL (driver: **aiomysql**),
  - `sqlite+aiosqlite` for SQLite.
- **Sessions**: `sqlmodel.ext.asyncio.session.AsyncSession`, created via a `sessionmaker` bound to the engine (`expire_on_commit=False`).

Code lives in `app/database.py`.

---

## 3. Engine and session factory (singletons)

`app/database.py` defines:

- **`engine`** — one async engine for the whole process, built from `resolved_database_url()`.
- **`async_session_factory`** — produces new `AsyncSession` instances.
- **`get_session()`** — async generator used with FastAPI **`Depends`**:

```text
Request → FastAPI resolves Depends(get_session) → async with async_session_factory() as session → yield session → route handler runs → session closed after response
```

Each request that injects `session: AsyncSession = Depends(get_session)` (directly or via a dependency that depends on it) gets **one session per request**. The session is not shared across concurrent requests.

---

## 4. How a request “hits” the database

Typical chain:

1. Client calls an API route (e.g. `POST /api/v1/resumes/upload`).
2. FastAPI builds the dependency graph. If the route (or a nested dependency like `get_current_user`) needs a DB session, it calls **`get_session`**.
3. **`get_session`** opens an **`AsyncSession`** from **`async_session_factory`** and **yields** it to the route.
4. The route uses **`await session.exec(...)`**, **`await session.get(Model, id)`**, **`session.add(...)`**, **`await session.commit()`**, **`await session.refresh(...)`**, etc.
5. When the request finishes, the context manager exits and the session is **closed**.

Authenticated routes often use:

- `Depends(get_session)` for the session, and  
- `Depends(get_current_user)` in `app/deps.py`, which **also** takes `session` and runs `await session.get(User, uid)` to load the user from the JWT `sub`.

So **one request** → **one session** → multiple SQL operations in that handler (until commit/rollback).

---

## 5. Application startup and shutdown

In `app/main.py` **lifespan**:

| Phase | Action |
|-------|--------|
| **Startup** | `await init_db()` — see below. Then optional seeding of empty `JobListing` rows if the table has no rows. |
| **Shutdown** | `await engine.dispose()` — closes the connection pool. |

### `init_db()` (`app/database.py`)

1. `async with engine.begin() as conn` — one transaction.
2. `await conn.run_sync(SQLModel.metadata.create_all)` — creates tables that do not exist, from all imported SQLModel metadata.
3. `await conn.run_sync(_run_legacy_migrations)` — sync SQL for small, additive changes on existing DBs (e.g. new columns on `user`, `emailotpcode` table, MySQL `MEDIUMTEXT` for long text columns).

There is no separate migration tool (e.g. Alembic) in this flow; schema evolution is **create_all** plus these guarded `ALTER`s.

---

## 6. Main tables (entities)

Defined in `app/models_db.py` (all mapped to SQL tables):

| Model | Purpose |
|-------|---------|
| **User** | Accounts (email, password hash, plan, email_verified, …) |
| **EmailOtpCode** | Email verification OTPs |
| **Resume** | Uploaded resume metadata + `parsed_json` (JSON), ATS score, soft-delete |
| **JDAnalysis** | Pasted job description analyses (`raw_jd`, `parsed_json`) |
| **TailoringSession** | JD-tailored resume outputs and PDF references |
| **JobListing** | Scraped/aggregated job postings (boards, descriptions, skills JSON) |
| **Application** | User’s saved/applied jobs (links `user`, `joblisting`, optional `resume`) |

Relationships use `foreign_key=` on integer IDs as in the models file.

---

## 7. Where the DB is used (by feature)

- **Auth** (`app/routers/auth.py`): register/login, OTP — `User`, `EmailOtpCode`.
- **Resumes** (`app/routers/resumes.py`): CRUD resumes, parsed JSON.
- **JD** (`app/routers/jd.py`): `JDAnalysis` rows.
- **Tailor** (`app/routers/tailor.py`): `TailoringSession`, resumes, JD analysis.
- **Jobs** (`app/routers/jobs.py`): `JobListing`, `Application`, resume-driven match; job search pipelines **upsert** listings and read them back.
- **Applications** (`app/routers/applications.py`): tracker / pipeline status.

Services under `app/services/` receive an `AsyncSession` from the router and perform queries/commits there (e.g. `upsert_job_listing` in `jsearch_pipeline.py`).

---

## 8. Read path vs write path

- **Reads**: `select(...)`, `session.get(...)`, `await session.exec(...)`.
- **Writes**: `session.add(...)`, `await session.commit()` — often after flush for generated IDs.

Failed requests may leave an uncommitted transaction depending on exception handling; routes should commit only after successful work or rely on session rollback on error (SQLAlchemy session behavior).

---

## 9. SQLite vs MySQL notes

- **SQLite**: file DB, good for local dev; `create_all` creates the file. Types like `JSON` and `Text` map appropriately.
- **MySQL**: create the **database** (schema) beforehand; the app creates **tables**. Some columns are widened via `_run_legacy_migrations` (e.g. long JD text).

---

## 10. Quick reference — files

| File | Role |
|------|------|
| `backend/app/config.py` | `resolved_database_url()`, `settings` |
| `backend/app/database.py` | Engine, `get_session`, `init_db`, migrations |
| `backend/app/models_db.py` | SQLModel table definitions |
| `backend/app/deps.py` | `get_current_user` (JWT + `session.get(User, ...)`) |
| `backend/app/main.py` | Lifespan: `init_db`, `engine.dispose` |

This is the full path from environment variables → connection URL → async engine → per-request `AsyncSession` → SQLModel operations on your tables.
