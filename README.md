# NutriTrack — 웹앱

AI 기반 식사 영양 트래커. 식사 사진을 업로드하거나 브랜드/메뉴명을 입력하면 칼로리와 영양성분을 자동으로 기록합니다.
macOS 데스크톱 앱에서 Next.js + FastAPI 풀스택 웹앱으로 전환 중입니다.

---

## 프로젝트 구조

```
.
├── frontend/          # Next.js 15 (App Router) — Vercel 배포
│   ├── app/           # 페이지 및 레이아웃 (Route Groups 사용)
│   ├── components/    # 재사용 UI 컴포넌트
│   ├── lib/supabase/  # Supabase 클라이언트 초기화
│   └── public/        # 정적 에셋
│
├── backend/           # FastAPI (Python 3.11+) — Railway 배포
│   ├── app/
│   │   ├── auth/      # Supabase JWT 검증 미들웨어
│   │   ├── routers/   # API 라우터 (meals, nutrition, vision 등)
│   │   ├── services/  # 비즈니스 로직 (vision pipeline, nutrition search)
│   │   └── db/        # SQLAlchemy 모델 및 세션
│   └── alembic/       # DB 마이그레이션
│
└── (루트)             # 기존 macOS 앱 Python 스크립트 (step1~3, app.py 등)
```

---

## 로컬 실행 (개발 환경)

### 사전 준비

- Node.js 18+
- Python 3.11+
- Supabase CLI (`brew install supabase/tap/supabase`)

### 환경변수 설정

```bash
# Backend
cp backend/.env.example backend/.env
# backend/.env 를 열어 각 키 입력

# Frontend
cp frontend/.env.example frontend/.env.local
# frontend/.env.local 를 열어 각 키 입력
```

### Backend 실행

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend 실행

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 `http://localhost:3000` 접속.

---

## 스택

| 레이어 | 기술 | 비고 |
|---|---|---|
| Frontend | Next.js 15 (App Router) + TypeScript | React 19 |
| Backend | FastAPI + Python 3.11 | uvicorn, asyncpg |
| DB / Auth / Storage | Supabase | PostgreSQL + Row Level Security |
| 이미지 업로드 | 브라우저 → Supabase Storage → URL → FastAPI | 서버에 바이너리 전달 없음 |
| Vision / LLM | OpenRouter API (무료 비전 모델) | 10~60초 소요 가능 |
| 영양 검색 | 식품안전처 DB → SerpAPI → CalorieNinjas → LLM 추정 | |

---

## 배포

| 구성 요소 | 플랫폼 | 비고 |
|---|---|---|
| Frontend | Vercel | `main` 브랜치 자동 배포 |
| Backend | Railway | 장시간 HTTP 연결 지원 (vision pipeline 용) |
| DB / Auth / Storage | Supabase | 관리형 PostgreSQL |

---

## 환경변수 목록

실제 값은 각 플랫폼 대시보드에서만 관리합니다. 커밋되는 파일은 `*.env.example` 뿐입니다.

- `backend/.env.example` — FastAPI에 필요한 모든 키 목록
- `frontend/.env.example` — Next.js 공개 키 (`NEXT_PUBLIC_*`) 목록

---

## 이미지 인식 모델 (OpenRouter 무료)

2026-06 기준 실제 동작 확인된 무료 비전 모델:

1. `google/gemma-4-31b-it:free` — 31B, 가장 정확
2. `google/gemma-4-26b-a4b-it:free` — 26B MoE
3. `nvidia/nemotron-nano-12b-v2-vl:free` — 소형 폴백

> OpenRouter 무료 티어: 50회/일 한도. 초과 시 내일 자정(UTC) 리셋.
