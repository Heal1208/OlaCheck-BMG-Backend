import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "BMG_schema.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn