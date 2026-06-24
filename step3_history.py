import argparse
import json
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

from step1_recognize import recognize
from step2_nutrition import analyze
from _paths import data_dir

DB_PATH = data_dir() / "history.db"
MEAL_TYPES = ("아침", "점심", "저녁", "간식")

_db_initialized = False


def get_conn() -> sqlite3.Connection:
    global _db_initialized
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if not _db_initialized:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL,
                meal_type   TEXT NOT NULL,
                image_path  TEXT,
                items_json  TEXT NOT NULL,
                total_json  TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                meal_time   TEXT
            )
        """)
        try:
            conn.execute("ALTER TABLE meals ADD COLUMN meal_time TEXT")
        except sqlite3.OperationalError:
            pass
        conn.commit()
        _db_initialized = True
    return conn
