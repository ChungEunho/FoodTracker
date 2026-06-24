# NutriTrack — AI 기반 식사 영양 트래커

macOS용 데스크톱 앱. 식사 사진 또는 브랜드/메뉴명을 입력하면 칼로리와 영양성분을 자동으로 기록합니다.

## 주요 기능

| 탭 | 설명 |
|---|---|
| 이미지 분석 | 음식 사진 → AI 자동 인식 → 영양성분 계산 후 저장 |
| 브랜드·메뉴 검색 | 브랜드명 + 메뉴명 입력 → 3단계 검색으로 영양정보 조회 |
| 직접 입력 | 칼로리/영양소를 직접 입력해 기록 |
| 일별 조회 | 날짜별 식사 기록 확인 및 삭제 |
| 기간 요약 | 날짜 범위별 평균 칼로리/영양소 요약 |
| 기록 관리 | 전체 기록 목록 조회 및 삭제 |

## 영양정보 검색 순서 (브랜드·메뉴 검색)

```
한국어 입력: 식품안전처 DB → SerpAPI(Google 검색+LLM 파싱) → LLM 직접 추정
영어 입력:   식품안전처 DB → CalorieNinjas → SerpAPI → LLM 직접 추정
```

## 설치 및 실행

### 1. 의존성 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. API 키 설정

`.env.example`을 `.env`로 복사 후 키 입력:

```bash
cp .env.example .env
# .env 파일을 편집기로 열어 각 API 키 입력
```

필요한 API 키:
- **OPENROUTER_API_KEY** (필수): [openrouter.ai](https://openrouter.ai) — 이미지 인식 및 LLM 추정용
- **DATA_GO_KR_FOOD_API_KEY** (권장): [data.go.kr](https://data.go.kr) — 식품안전처 영양 DB
- **SERPAPI_API_KEY** (권장): [serpapi.com](https://serpapi.com) — Google 검색 기반 영양정보 (무료 100회/월)
- **CALORIE_NINJA_API_KEY** (선택): [calorieninjas.com](https://calorieninjas.com) — 영어 식품 검색

### 3. 실행

```bash
source .venv/bin/activate
python app.py
```

### 4. macOS 앱 번들 빌드 (선택)

```bash
pip install pyinstaller
pyinstaller NutriTrack.spec --noconfirm
# dist/NutriTrack.app 생성됨
# dist/.env 파일에 API 키 별도 입력 필요
```

## 이미지 인식 모델 (OpenRouter 무료)

2026-06 기준 실제 동작 확인된 무료 비전 모델 순서:
1. `google/gemma-4-31b-it:free` — 31B, 가장 정확
2. `google/gemma-4-26b-a4b-it:free` — 26B MoE
3. `nvidia/nemotron-nano-12b-v2-vl:free` — 소형 폴백

> OpenRouter 무료 티어: 50회/일 한도. 초과 시 내일 자정(UTC) 리셋.

## 기술 스택

- **GUI**: Python tkinter + ttk
- **이미지 처리**: Pillow, pillow-heif
- **LLM**: OpenRouter API (OpenAI-compatible)
- **DB**: SQLite
- **번들**: PyInstaller (macOS .app)
