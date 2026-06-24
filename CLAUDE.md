# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

**NutriTrack** — an AI-powered meal nutrition tracker for macOS. Given a food photo or a brand/menu name, it identifies the food items and looks up or estimates their calorie and macro-nutrient data, then saves everything to a local SQLite database. The app ships as both a Python script and a standalone macOS `.app` bundle built with PyInstaller.

## Running the App

```bash
source .venv/bin/activate
python app.py                        # GUI
python step3_history.py log <image> --meal 점심 [--date YYYY-MM-DD] [--time HH:MM]
python step3_history.py show [--date YYYY-MM-DD]
python step3_history.py summary --from YYYY-MM-DD --to YYYY-MM-DD
python step3_history.py delete --id <id>
python test_api.py                   # quick API connectivity check
python test_vision.py                # test vision models against sample images
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # then fill in API keys
```

Required API keys (`.env`):
- `OPENROUTER_API_KEY` — required; used for all LLM calls
- `DATA_GO_KR_FOOD_API_KEY` — recommended; Korea MFDS nutrition DB
- `SERPAPI_API_KEY` — recommended; Google search for nutrition data (100 free/month)
- `CALORIE_NINJA_API_KEY` — optional; English food search (10,000 free/month)

## Building the macOS Bundle

```bash
pip install pyinstaller
pyinstaller NutriTrack.spec --noconfirm
# Output: dist/NutriTrack.app
# API keys must be placed in dist/.env (not bundled for security)
```

## Code Architecture

### Module Map

| File | Role |
|------|------|
| `app.py` | tkinter GUI — 4-tab notebook, threading wiring |
| `client.py` | OpenRouter API client (OpenAI-compatible). Exports `client` and `strip_fence()` |
| `_paths.py` | Path resolution that works in both script mode and PyInstaller `.app` bundle |
| `step1_recognize.py` | Image → food item list via vision LLM |
| `step2_nutrition.py` | Food item list → weight + macro-nutrients via LLM |
| `step3_history.py` | SQLite DB init/queries + CLI subcommands (`log`, `show`, `summary`, `delete`) |
| `nutrition_search.py` | Multi-tier brand/menu nutrition lookup |

### Image Analysis Pipeline

1. **`step1_recognize(image_path)`** — converts image to base64 JPEG data URL (resized to ≤1024px), sends to a free OpenRouter vision model. Returns `{"items": [{"name", "cooking_method", "notes"}], "raw_description": ...}`.  
   Vision models tried in order (30s timeout each, via `ThreadPoolExecutor`):
   1. `google/gemma-4-31b-it:free`
   2. `google/gemma-4-26b-a4b-it:free`
   3. `nvidia/nemotron-nano-12b-v2-vl:free`

2. **`step2_nutrition.analyze(step1_result)`** — sends food list to `openai/gpt-oss-120b:free`, which estimates weight (g) and macros per item. Computes a `total` dict and returns the full result.

3. GUI (`app.py`) or CLI (`step3_history.py`) saves the result to SQLite via `get_conn()`.

### Brand/Menu Search Pipeline (`nutrition_search.search_nutrition`)

Language is auto-detected (Korean characters → Korean path):

```
Korean input: MFDS DB → SerpAPI (Google search + LLM parse) → LLM direct estimate
English input: MFDS DB → CalorieNinjas → SerpAPI → LLM direct estimate
```

Each tier skips silently if the required API key is absent. Returns `(result_dict, found_name, is_exact)`.

### Database

SQLite file at:
- Script mode: `history.db` in project root
- `.app` bundle: `~/Library/Application Support/FoodTracker/history.db`

Path is resolved by `_paths.data_dir()`. Schema (single table `meals`):
```sql
id INTEGER PRIMARY KEY AUTOINCREMENT,
date TEXT, meal_type TEXT, image_path TEXT,
items_json TEXT, total_json TEXT,
created_at TEXT, meal_time TEXT
```
`items_json` and `total_json` store the full structured nutrition data as JSON strings.

### GUI Threading Model

All LLM/network calls in `app.py` run in daemon threads. Results are posted back to the main thread via a `queue.Queue` (`self._q`), polled every 100ms by `self._poll()`. Use `self._post(fn)` to schedule a UI callback from a worker thread — never touch tkinter widgets directly from a worker.

### GUI Tabs

1. **식사 기록** — 3 sub-tabs: image analysis (analyze & auto-save), brand/menu search (preview then save), manual entry (add items one by one then save). Common meal type / date / time controls below sub-tabs.
2. **일별 조회** — query by date; grouped by meal type; shows per-meal subtotals and daily total; supports deletion.
3. **기간 요약** — date-range query; shows daily calorie/macro breakdown + average row.
4. **기록 관리** — full records list with multi-select deletion.

### Path Resolution (`_paths.py`)

`env_path()` and `data_dir()` check `sys.frozen` to detect PyInstaller bundle mode and return appropriate paths. Import these instead of hardcoding paths anywhere in the codebase.

## Key Constraints

- **OpenRouter free tier**: 50 requests/day; resets at midnight UTC. Vision models and `gpt-oss-120b:free` all count toward this.
- **`model.txt`** is not used by the app at runtime — it is a reference list of models to experiment with.
- HEIC/HEIF image support requires `pillow-heif` (included in requirements). The app degrades gracefully if it is missing.
