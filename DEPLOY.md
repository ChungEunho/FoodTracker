# NutriTrack Deployment Guide

This document describes how to configure environment variables on each platform and the correct order in which to deploy NutriTrack's services.

No real secrets, API keys, or URLs should ever be committed to this repository. All values below are key names only.

---

## Deployment Order

1. Create a Supabase project and note the project URL, anon key, service role key, and JWT secret.
2. Deploy the backend to Railway, using the Supabase PostgreSQL connection string as `DATABASE_URL`.
3. The Railway container runs `alembic upgrade head` automatically on startup — no manual migration step needed.
4. Deploy the frontend to Vercel, setting `NEXT_PUBLIC_API_URL` to the Railway service URL.
5. Go back to Railway and set `ALLOWED_ORIGINS` to the Vercel deployment URL (exact origin, no trailing slash).

---

## Railway (Backend)

### How to set variables

1. Open the Railway dashboard and select your project.
2. Click the service, then go to the **Variables** tab.
3. Add each key below as a separate variable. Railway injects them as environment variables at runtime.

### Required variables

| Key | Description |
|-----|-------------|
| `SUPABASE_URL` | Your Supabase project URL (e.g. `https://xxxx.supabase.co`) |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key from Supabase → Settings → API |
| `SUPABASE_JWT_SECRET` | JWT secret from Supabase → Settings → API |
| `DATABASE_URL` | Supabase PostgreSQL connection string (postgres://…) |
| `OPENROUTER_API_KEY` | OpenRouter API key for LLM calls |
| `ALLOWED_ORIGINS` | Exact Vercel frontend URL, e.g. `https://nutritrack.vercel.app` (no wildcard, no trailing slash) |
| `ENVIRONMENT` | Set to `production` |
| `SKIP_AUTH` | Set to `false` in production |

### Optional variables

| Key | Description |
|-----|-------------|
| `DATA_GO_KR_FOOD_API_KEY` | Korea MFDS nutrition database |
| `SERPAPI_API_KEY` | Google search via SerpAPI for nutrition lookups |
| `CALORIE_NINJA_API_KEY` | CalorieNinja API for English food search |

### Notes

- Railway supports long-running HTTP connections — the vision pipeline (up to 2 minutes) will not be killed by a timeout.
- `alembic upgrade head` runs automatically inside the container before uvicorn starts. If migrations fail, the container will not start and Railway will retry per the restart policy in `railway.toml`.
- The Railway build uses `backend/Dockerfile` with `backend/` as the build context (configured in `railway.toml`).

---

## Vercel (Frontend)

### How to set variables

1. Open the Vercel dashboard and select your project.
2. Go to **Settings → Environment Variables**.
3. Add each key below. Set the environment scope to **Production**, **Preview**, and **Development** as appropriate.

### Root Directory setting

In the Vercel project settings, go to **Settings → General → Root Directory** and set it to `frontend`. This tells Vercel to treat `frontend/` as the project root instead of the repo root.

### Required variables

| Key | Description |
|-----|-------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL (same value as backend `SUPABASE_URL`) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon/public key (safe for client-side use) |
| `NEXT_PUBLIC_API_URL` | Railway backend URL, e.g. `https://nutritrack-backend.railway.app` |

### Notes

- `NEXT_PUBLIC_` prefix exposes the value to the browser bundle. Never use this prefix for secrets.
- For preview deployments (PRs), you may set `NEXT_PUBLIC_API_URL` to a staging Railway service if one exists, or leave it pointing at production.
- The `vercel.json` at `frontend/vercel.json` defines the framework, build, and install commands. Do not add secret values to `vercel.json`.

---

## GitHub Actions Secrets

The current CI workflow (`.github/workflows/ci.yml`) runs lint and build checks only and does not require any real secrets.

If integration tests or end-to-end tests are added later that need API keys:

1. Go to the GitHub repository → **Settings → Secrets and variables → Actions**.
2. Click **New repository secret** and add the key.
3. Reference it in the workflow with `${{ secrets.YOUR_KEY_NAME }}`.

Never paste real secret values directly into workflow YAML files.

---

## Local Development

```bash
# Backend
cp backend/.env.example backend/.env
# Fill in your dev Supabase project credentials and a dev OPENROUTER_API_KEY
cd backend
uvicorn app.main:app --reload

# Frontend
cp frontend/.env.example frontend/.env.local
# Fill in NEXT_PUBLIC_ values pointing at http://localhost:8000
cd frontend
npm install
npm run dev
```

Use separate Supabase projects (or separate schemas) for development and production. Never use production credentials locally.
