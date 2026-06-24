---
name: project-nutritrack-gitignore-hygiene
description: .gitignore rules and secrets hygiene decisions for NutriTrack repo
metadata:
  type: project
---

The root `.gitignore` was updated (2026-06-25) to cover all secret, build, and OS artefact patterns for the new web stack while preserving the macOS app patterns.

**Critical secret-blocking lines:**
```
.env
.env.local
.env.*.local
*.pem
*.key
!.env.example   # negation — .env.example IS committed
```

**Why:** The repo already had a `.env` file at the root (used by the macOS app) and a `dist/.env` from PyInstaller builds. These must never reach git.

**How to apply:** When creating any new service directory, add a `.env.example` there (not a `.env`). Real secrets go only into platform dashboards (Vercel, Railway, Supabase).

**Committed env example files:**
- `backend/.env.example` — backend keys (service role, JWT secret, DB URL, etc.)
- `frontend/.env.example` — public Next.js keys (`NEXT_PUBLIC_*`)
- Root `.env.example` — legacy macOS app keys (OPENROUTER, DATA_GO_KR, SERPAPI, CALORIE_NINJA)

See also: [[project-nutritrack-web-migration]]
