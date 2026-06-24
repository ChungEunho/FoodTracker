---
name: project-patterns
description: Recurring anti-patterns and conventions observed in this codebase during first review
metadata:
  type: project
---

## Established conventions (correct, follow)
- SQL parameterization: always uses `?` placeholders — never f-string SQL. Correct and consistent.
- Thread-safe UI: uses `queue.Queue` + `_poll` pattern to marshal results back to main thread in `app.py`.
- API key loading: via `python-dotenv` from `.env` (renamed from `.env.txt`). Never hardcoded.
- Model IDs: should live in `model.txt` per CLAUDE.md — but currently violated (see anti-patterns below).

## Recurring anti-patterns (flag in future reviews)
- **Connection leak pattern**: `conn = get_conn()` ... `conn.close()` without try/finally appears in 5 places in `app.py`. Any exception between open and close leaks the connection.
- **KeyError on LLM JSON**: after `json.loads()`, keys are accessed directly (e.g., `result["items"]`) without `.get()` guard. LLMs can return valid JSON with unexpected structure.
- **Duplicate markdown fence stripping**: identical 3-line block duplicated in `step1_recognize.py` and `step2_nutrition.py`. Should be extracted to `utils.py`.
- **DDL in connection factory**: `get_conn()` runs `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE` on every call — DDL should run once at startup.
- **Hardcoded model IDs in step files**: violates project convention (model.txt). Both `step1_recognize.py` and `step2_nutrition.py` hardcode model strings.
- **Unused imports**: `import sys` in both step files; `from step1_recognize import recognize` in `step2_nutrition.py`.
- **Integer division for averages**: `_do_summary` in `app.py` uses `//` — silently truncates nutritional averages.
- **No API timeout or retry**: `client.chat.completions.create()` has no `timeout` parameter — worker thread can hang indefinitely.

**Why:** Most of these are first-draft prototype habits. Flag them in every review since the codebase is iterating actively.
**How to apply:** In future reviews of any file in this project, immediately check for these patterns before looking for novel issues.
