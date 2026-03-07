import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "BMG_schema.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def is_seeded(conn):
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'seed_log'"
    ).fetchone()
    if not table:
        return False
    return conn.execute(
        "SELECT id FROM seed_log WHERE event = 'initial_seed'"
    ).fetchone() is not None

def init_seed():
    from utils import hash_password

    conn = get_db()

    if is_seeded(conn):
        print("Database already seeded — skipping.")
        conn.close()
        return

    print("First run — seeding database...")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seed_log (
            id         INTEGER   PRIMARY KEY AUTOINCREMENT,
            event      TEXT      NOT NULL UNIQUE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    USERS = [
        {"full_name": "Director",         "email": "director@bmg.com",         "phone": "0901000001", "password": "123", "role_name": "Director"},
        {"full_name": "Deputy Director",  "email": "deputydirector@bmg.com",   "phone": "0901000002", "password": "123", "role_name": "Deputy_Director"},
        {"full_name": "Sales Manager",    "email": "salesmanager@bmg.com",     "phone": "0901000003", "password": "123", "role_name": "Sales_Manager"},
        {"full_name": "Sales Executive",  "email": "salesexecutive@bmg.com",   "phone": "0901000004", "password": "123", "role_name": "Sales_Executive"},
        {"full_name": "Sales Admin",      "email": "salesadmin@bmg.com",       "phone": "0901000005", "password": "123", "role_name": "Sales_Admin"},
        {"full_name": "Warehouse Manager","email": "warehousemanager@bmg.com", "phone": "0901000006", "password": "123", "role_name": "Warehouse_Manager"},
        {"full_name": "Delivery",         "email": "delivery@bmg.com",         "phone": "0901000007", "password": "123", "role_name": "Delivery"},
        {"full_name": "Accountant",       "email": "accountant@bmg.com",       "phone": "0901000008", "password": "123", "role_name": "Accountant"},
        {"full_name": "HR Admin",         "email": "hradmin@bmg.com",          "phone": "0901000009", "password": "123", "role_name": "HR_Admin"},
    ]

    for u in USERS:
        role = conn.execute(
            "SELECT role_id FROM roles WHERE role_name = ?", (u["role_name"],)
        ).fetchone()

        if not role:
            print(f"  ! Role '{u['role_name']}' not found — skipped.")
            continue

        conn.execute(
            "INSERT OR IGNORE INTO users (full_name, email, phone, password_hash, role_id) VALUES (?, ?, ?, ?, ?)",
            (u["full_name"], u["email"], u["phone"], hash_password(u["password"]), role["role_id"])
        )
        print(f"  + {u['role_name']:20} | {u['email']:35} | pass: {u['password']}")

    conn.execute("INSERT INTO seed_log (event) VALUES ('initial_seed')")
    conn.commit()
    conn.close()
    print("Seed complete — will not run again.")