---
name: project-sqlite-conn-idiom
description: Leak-free SQLite connection pattern in this app — closing() is required because the connection's own context manager does not close
metadata:
  type: project
---

In this meal-tracker app, DB access goes through `get_conn()` in `step3_history.py`, which returns a plain `sqlite3.Connection`.

Fact: `with conn:` (the connection's own context manager) commits on success / rolls back on exception but does **NOT** close the connection — it leaks the handle. To close reliably, wrap in `contextlib.closing`.

**Why:** A code review flagged 5 connection-leak sites in `app.py` (`_log_done`, `_do_show`, `_do_summary`, `_load_records`, `_do_delete`) where `conn.close()` was skipped on exceptions. The original fix suggestion was a bare `with get_conn()`, which would have masked the leak rather than fixing it.

**How to apply:**
- Read-only paths: `with closing(get_conn()) as conn:`
- Write paths (need commit + close): `with closing(get_conn()) as conn, conn:` — the second `conn` is the transaction context (commit/rollback), the outer `closing` guarantees the handle is closed.

Related: DDL in `get_conn()` is now guarded by a module-level `_db_initialized` flag so CREATE TABLE / ALTER TABLE run only once per process.
