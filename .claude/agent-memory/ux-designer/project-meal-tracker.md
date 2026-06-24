---
name: project-meal-tracker
description: UX patterns and conventions for the tkinter meal nutrition tracker app (app.py)
metadata:
  type: project
---

This project is a Python tkinter GUI for tracking meal nutrition, structured as a 4-tab Notebook:
- Tab 1 (식사 기록): image upload → LLM analysis → results table → DB save
- Tab 2 (일별 조회): date input → daily meal list
- Tab 3 (기간 요약): date range → per-day calorie/nutrient averages
- Tab 4 (기록 관리): full record list + multi-select delete

**Why:** Study/experimentation project using the OpenRouter API for LLM-powered food recognition.

**Visual theme (applied 2026-06-24):**
- Base ttk theme: "clam"
- Color palette stored in module-level `C` dict (bg, surface, border, primary, primary_dk, accent, danger, text, text_sub, row_even, row_odd, header_bg, avg_bg, total_bg)
- Primary blue: #2D7DD2 / dark: #1F5FAA; accent green: #4CAF50; danger red: #E53935
- App header banner: solid primary-blue tk.Frame (height=54) with "🥗 NutriTrack" title — sits above the Notebook
- Font: "Helvetica Neue" throughout (12 body, 11 controls/small, 18 bold for app title)
- Button styles: Primary.TButton (blue, white text), Danger.TButton (light red bg + red text), Small.TButton (compact, gray)
- Treeview row striping: "odd"=white, "even"=#F9FAFB — applied via enumerate on data rows only; special tags (meal_header, subtotal, total, avg, empty, time_row) override striping
- total row bg: #FFF8E7; avg row bg: #F0FDF4; meal_header bg: #EEF2FF
- Scrollbar: width=8, arrowsize=0 (slim, no arrows)
- Window geometry: "880x680" (was 880x660 before theme — header adds ~20px)

**Established UX conventions:**
- Quick-select date buttons ("오늘"/"어제") placed immediately after date Entry fields, before the action button — use Small.TButton style
- Tab 3 convention: start-date gets "어제", end-date gets "오늘" (semantically appropriate defaults)
- Status label colors via C palette: C["text_sub"]=in-progress, C["accent"]=success, C["danger"]=error
- Status messages use emoji prefixes: 🔍 for step 1, 📊 for step 2, ✅ for success, ❌ for error
- Empty state shown as a tree row (tag="empty", foreground C["text_sub"]) — not as an external label
- Delete confirmation dialog lists affected records (date + meal_type + kcal), max 5, then "외 N개"
- Window minsize: (800, 580); first nutrition column width: 210px
- Only standard tkinter/ttk widgets — no external UI libraries
- Preview label shows placeholder text "이미지를 선택하면 미리보기가 표시됩니다" in text_sub color when no image selected
- LabelFrame sections in Tab 1 use padding=14 and pady=(12, 6) for card-like feel
- _apply_theme() called at start of __init__, before header and notebook construction

**How to apply:** Follow these conventions when designing or reviewing any new tab or UI change in app.py. The _log_status_lbl widget (not just StringVar) must be held as an instance variable to allow foreground color changes at runtime. Always use C[] palette constants rather than hardcoded hex strings for consistency.
