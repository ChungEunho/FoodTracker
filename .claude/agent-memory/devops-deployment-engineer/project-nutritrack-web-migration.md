---
name: project-nutritrack-web-migration
description: NutriTrack macOS app → fullstack web app migration; confirmed platform choices, repo layout, and env var naming conventions
metadata:
  type: project
---

NutriTrack is being migrated from a Python/tkinter macOS desktop app to a Next.js 15 + FastAPI web application. The root repo at `/Users/eunho/Desktop/DGIST/Side_Projects/Claude/Study04` already existed and was NOT re-initialized.

**Platform decisions (confirmed):**
- Frontend: Next.js 15 (App Router) → Vercel
- Backend: FastAPI Python 3.11+ → Railway (chosen for long-lived HTTP connections; vision pipeline takes 10–60+ seconds)
- DB / Auth / Storage: Supabase (managed PostgreSQL + Auth + Storage)
- Image upload path: Browser → Supabase Storage → URL → FastAPI (no binary upload to FastAPI directly)

**Repo layout:**
- `frontend/` — Next.js app; `app/(auth)/`, `app/(dashboard)/log|daily|summary|records`, `components/log/`, `lib/supabase/`, `public/`
- `backend/` — FastAPI; `app/auth/`, `app/routers/`, `app/services/`, `app/db/`, `alembic/versions/`
- Root-level macOS Python files (`step1_recognize.py`, `step2_nutrition.py`, `step3_history.py`, `app.py`, etc.) are preserved untouched.

**Environment variable naming (standardized):**
- Backend: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `DATABASE_URL`, `OPENROUTER_API_KEY`, `DATA_GO_KR_FOOD_API_KEY`, `SERPAPI_API_KEY`, `CALORIE_NINJA_API_KEY`, `ALLOWED_ORIGINS`
- Frontend: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL`

**CORS:** `ALLOWED_ORIGINS` env var on Railway backend; dev default `http://localhost:3000`; prod must be set to exact Vercel URL.

**Why:** macOS app was single-user SQLite; web version needs multi-user auth, cloud DB, and a long-timeout backend host for the vision pipeline.

**How to apply:** When suggesting deployment steps, Railway is the confirmed backend host. Supabase is the DB/Auth layer — do not suggest alternative auth providers without user confirmation. Always reference `backend/.env.example` and `frontend/.env.example` for key names.

See also: [[project-nutritrack-gitignore-hygiene]]
