import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "BMG_schema.db")

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = OFF")

conn.execute("DELETE FROM users")
conn.execute("DROP TABLE IF EXISTS seed_log")

conn.execute("PRAGMA foreign_keys = ON")
conn.commit()
conn.close()

print("Reset hoàn tất — chạy python app.py để seed lại")