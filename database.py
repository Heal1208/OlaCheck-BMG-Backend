import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "BMG_schema.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
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
        {"full_name": "Director",          "email": "director@bmg.com",         "phone": "0901000001", "password": "123", "role_name": "Director"},
        {"full_name": "Deputy Director",   "email": "deputydirector@bmg.com",   "phone": "0901000002", "password": "123", "role_name": "Deputy_Director"},
        {"full_name": "Sales Manager",     "email": "salesmanager@bmg.com",     "phone": "0901000003", "password": "123", "role_name": "Sales_Manager"},
        {"full_name": "Sales Executive",   "email": "salesexecutive@bmg.com",   "phone": "0901000004", "password": "123", "role_name": "Sales_Executive"},
        {"full_name": "Sales Admin",       "email": "salesadmin@bmg.com",       "phone": "0901000005", "password": "123", "role_name": "Sales_Admin"},
        {"full_name": "Warehouse Manager", "email": "warehousemanager@bmg.com", "phone": "0901000006", "password": "123", "role_name": "Warehouse_Manager"},
        {"full_name": "Delivery",          "email": "delivery@bmg.com",         "phone": "0901000007", "password": "123", "role_name": "Delivery"},
        {"full_name": "Accountant",        "email": "accountant@bmg.com",       "phone": "0901000008", "password": "123", "role_name": "Accountant"},
        {"full_name": "HR Admin",          "email": "hradmin@bmg.com",          "phone": "0901000009", "password": "123", "role_name": "HR_Admin"},
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

    # Lấy user_id của Sales Executive và Sales Admin để gán stores
    exec_user  = conn.execute("SELECT user_id FROM users WHERE email = 'salesexecutive@bmg.com'").fetchone()
    admin_user = conn.execute("SELECT user_id FROM users WHERE email = 'salesadmin@bmg.com'").fetchone()

    if exec_user and admin_user:
        STORES = [
            {
                "store_name":        "Tạp hóa Bà Lan",
                "store_type":        "grocery",
                "owner_name":        "Nguyễn Thị Lan",
                "phone":             "0911000001",
                "address":           "12 Nguyễn Trãi",
                "district":          "Thanh Xuân",
                "city":              "Hà Nội",
                "latitude":          21.0023,
                "longitude":         105.8412,
                "assigned_staff_id": exec_user["user_id"]
            },
            {
                "store_name":        "Tạp hóa Minh Đức",
                "store_type":        "grocery",
                "owner_name":        "Trần Minh Đức",
                "phone":             "0911000002",
                "address":           "45 Lê Văn Lương",
                "district":          "Cầu Giấy",
                "city":              "Hà Nội",
                "latitude":          21.0301,
                "longitude":         105.7923,
                "assigned_staff_id": exec_user["user_id"]
            },
            {
                "store_name":        "WinMart Cầu Giấy",
                "store_type":        "supermarket",
                "owner_name":        "WinMart",
                "phone":             "0911000003",
                "address":           "102 Xuân Thủy",
                "district":          "Cầu Giấy",
                "city":              "Hà Nội",
                "latitude":          21.0378,
                "longitude":         105.7845,
                "assigned_staff_id": admin_user["user_id"]
            },
            {
                "store_name":        "WinMart Thanh Xuân",
                "store_type":        "supermarket",
                "owner_name":        "WinMart",
                "phone":             "0911000004",
                "address":           "230 Nguyễn Trãi",
                "district":          "Thanh Xuân",
                "city":              "Hà Nội",
                "latitude":          20.9956,
                "longitude":         105.8201,
                "assigned_staff_id": admin_user["user_id"]
            },
            {
                "store_name":        "Đại lý Hoàng Phát",
                "store_type":        "agency",
                "owner_name":        "Lê Hoàng Phát",
                "phone":             "0911000005",
                "address":           "78 Giải Phóng",
                "district":          "Hoàng Mai",
                "city":              "Hà Nội",
                "latitude":          20.9812,
                "longitude":         105.8534,
                "assigned_staff_id": exec_user["user_id"]
            },
            {
                "store_name":        "Tạp hóa Thu Hương",
                "store_type":        "grocery",
                "owner_name":        "Phạm Thu Hương",
                "phone":             "0911000006",
                "address":           "33 Đội Cấn",
                "district":          "Ba Đình",
                "city":              "Hà Nội",
                "latitude":          21.0440,
                "longitude":         105.8339,
                "assigned_staff_id": exec_user["user_id"]
            },
            {
                "store_name":        "Đại lý Phúc Thịnh",
                "store_type":        "agency",
                "owner_name":        "Nguyễn Văn Phúc",
                "phone":             "0911000007",
                "address":           "156 Bạch Mai",
                "district":          "Hai Bà Trưng",
                "city":              "Hà Nội",
                "latitude":          21.0020,
                "longitude":         105.8500,
                "assigned_staff_id": admin_user["user_id"]
            },
        ]

        for s in STORES:
            conn.execute(
                """
                INSERT OR IGNORE INTO stores
                    (store_name, store_type, owner_name, phone,
                     address, district, city,
                     latitude, longitude, assigned_staff_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    s["store_name"], s["store_type"], s["owner_name"], s["phone"],
                    s["address"],   s["district"],   s["city"],
                    s["latitude"],  s["longitude"],  s["assigned_staff_id"]
                )
            )
            print(f"  + Store: {s['store_name']} ({s['store_type']}) — {s['district']}")

    # Seed products
    PRODUCTS = [
        {"product_name": "Olasun Sunflower Oil 1L",  "sku": "OLA-1L",  "category": "Sunflower Oil", "unit": "bottle", "low_stock_threshold": 10},
        {"product_name": "Olasun Sunflower Oil 2L",  "sku": "OLA-2L",  "category": "Sunflower Oil", "unit": "bottle", "low_stock_threshold": 8},
        {"product_name": "Olasun Sunflower Oil 5L",  "sku": "OLA-5L",  "category": "Sunflower Oil", "unit": "bottle", "low_stock_threshold": 5},
        {"product_name": "Olasun Sunflower Oil 500ml","sku": "OLA-500ML","category": "Sunflower Oil","unit": "bottle", "low_stock_threshold": 15},
    ]

    for p in PRODUCTS:
        conn.execute(
            "INSERT OR IGNORE INTO products (product_name, sku, category, unit, low_stock_threshold) VALUES (?, ?, ?, ?, ?)",
            (p["product_name"], p["sku"], p["category"], p["unit"], p["low_stock_threshold"])
        )
        print(f"  + Product: {p['product_name']}")

    conn.execute("INSERT INTO seed_log (event) VALUES ('initial_seed')")
    conn.commit()
    conn.close()
    print("Seed complete — will not run again.")