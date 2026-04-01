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

    # ─── 3 roles mới ─────────────────────────────────────────────────────────
    # Admin   : Director / Deputy_Director / Sales_Manager — toàn quyền
    # Manager : Sales_Admin / Sales_Executive / ... — vận hành & theo dõi
    # Staff   : nhân viên tuyến — chỉ dùng Mobile App
    ROLES = [
        {
            "role_name":   "Admin",
            "description": "Quản trị viên hệ thống / Trưởng phòng kinh doanh — toàn quyền Web Admin, quản lý nhân sự, cấu hình hệ thống, xem báo cáo tổng quan."
        },
        {
            "role_name":   "Manager",
            "description": "Quản lý cấp trung (Sales Admin, Sales Executive, ...) — theo dõi cửa hàng, xem cảnh báo tồn kho, hỗ trợ vận hành, check-in điểm bán."
        },
        {
            "role_name":   "Staff",
            "description": "Nhân viên tuyến — chỉ sử dụng Mobile App để check-in, nhập tồn kho và kiểm tra hạn sử dụng."
        },
    ]

    for r in ROLES:
        conn.execute(
            "INSERT OR IGNORE INTO roles (role_name, description) VALUES (?, ?)",
            (r["role_name"], r["description"])
        )

    # ─── Lấy role_id ─────────────────────────────────────────────────────────
    role_ids = {
        r["role_name"]: r["role_id"]
        for r in conn.execute("SELECT role_id, role_name FROM roles").fetchall()
    }

    # ─── Seed users ──────────────────────────────────────────────────────────
    # Mật khẩu mặc định: bmg@2025 (8+ ký tự)
    USERS = [
        # Admin level
        {"full_name": "Giám đốc",           "email": "director@bmg.com",       "phone": "0901000001", "password": "bmg@2025", "role": "Admin"},
        {"full_name": "Phó Giám đốc",        "email": "deputydirector@bmg.com", "phone": "0901000002", "password": "bmg@2025", "role": "Admin"},
        {"full_name": "Trưởng phòng KD",     "email": "salesmanager@bmg.com",   "phone": "0901000003", "password": "bmg@2025", "role": "Admin"},
        # Manager level
        {"full_name": "Sales Admin Nguyễn",  "email": "salesadmin@bmg.com",     "phone": "0901000004", "password": "bmg@2025", "role": "Manager"},
        {"full_name": "Sales Admin Trần",    "email": "salesadmin2@bmg.com",    "phone": "0901000005", "password": "bmg@2025", "role": "Manager"},
        # Staff level
        {"full_name": "NV Nguyễn Văn An",   "email": "staff1@bmg.com",         "phone": "0901000006", "password": "bmg@2025", "role": "Staff"},
        {"full_name": "NV Trần Thị Bình",   "email": "staff2@bmg.com",         "phone": "0901000007", "password": "bmg@2025", "role": "Staff"},
        {"full_name": "NV Lê Văn Cường",    "email": "staff3@bmg.com",         "phone": "0901000008", "password": "bmg@2025", "role": "Staff"},
    ]

    for u in USERS:
        rid = role_ids.get(u["role"])
        if not rid:
            print(f"  ! Role '{u['role']}' not found — skipped.")
            continue
        conn.execute(
            "INSERT OR IGNORE INTO users (full_name, email, phone, password_hash, role_id) VALUES (?, ?, ?, ?, ?)",
            (u["full_name"], u["email"], u["phone"], hash_password(u["password"]), rid)
        )
        print(f"  + [{u['role']:8}] {u['email']:35} | pass: {u['password']}")

    conn.commit()

    # ─── Lấy user_id để gán stores ───────────────────────────────────────────
    manager1 = conn.execute("SELECT user_id FROM users WHERE email = 'salesadmin@bmg.com'").fetchone()
    manager2 = conn.execute("SELECT user_id FROM users WHERE email = 'salesadmin2@bmg.com'").fetchone()
    staff1   = conn.execute("SELECT user_id FROM users WHERE email = 'staff1@bmg.com'").fetchone()
    staff2   = conn.execute("SELECT user_id FROM users WHERE email = 'staff2@bmg.com'").fetchone()
    staff3   = conn.execute("SELECT user_id FROM users WHERE email = 'staff3@bmg.com'").fetchone()

    if all([manager1, manager2, staff1, staff2, staff3]):
        STORES = [
            {
                "store_name":        "Tạp hóa Bà Lan",
                "store_type":        "grocery",
                "owner_name":        "Nguyễn Thị Lan",
                "phone":             "0911000001",
                "address":           "12 Nguyễn Trãi",
                "district":          "Thanh Xuân",
                "city":              "Hà Nội",
                "assigned_staff_id": staff1["user_id"],
            },
            {
                "store_name":        "Tạp hóa Minh Đức",
                "store_type":        "grocery",
                "owner_name":        "Trần Minh Đức",
                "phone":             "0911000002",
                "address":           "45 Lê Văn Lương",
                "district":          "Cầu Giấy",
                "city":              "Hà Nội",
                "assigned_staff_id": staff1["user_id"],
            },
            {
                "store_name":        "WinMart Cầu Giấy",
                "store_type":        "supermarket",
                "owner_name":        "WinMart",
                "phone":             "0911000003",
                "address":           "102 Xuân Thủy",
                "district":          "Cầu Giấy",
                "city":              "Hà Nội",
                "assigned_staff_id": staff2["user_id"],
            },
            {
                "store_name":        "WinMart Thanh Xuân",
                "store_type":        "supermarket",
                "owner_name":        "WinMart",
                "phone":             "0911000004",
                "address":           "230 Nguyễn Trãi",
                "district":          "Thanh Xuân",
                "city":              "Hà Nội",
                "assigned_staff_id": staff2["user_id"],
            },
            {
                "store_name":        "Đại lý Hoàng Phát",
                "store_type":        "agency",
                "owner_name":        "Lê Hoàng Phát",
                "phone":             "0911000005",
                "address":           "78 Giải Phóng",
                "district":          "Hoàng Mai",
                "city":              "Hà Nội",
                "assigned_staff_id": staff3["user_id"],
            },
            {
                "store_name":        "Tạp hóa Thu Hương",
                "store_type":        "grocery",
                "owner_name":        "Phạm Thu Hương",
                "phone":             "0911000006",
                "address":           "33 Đội Cấn",
                "district":          "Ba Đình",
                "city":              "Hà Nội",
                "assigned_staff_id": staff3["user_id"],
            },
            {
                "store_name":        "Đại lý Phúc Thịnh",
                "store_type":        "agency",
                "owner_name":        "Nguyễn Văn Phúc",
                "phone":             "0911000007",
                "address":           "156 Bạch Mai",
                "district":          "Hai Bà Trưng",
                "city":              "Hà Nội",
                "assigned_staff_id": staff1["user_id"],
            },
        ]

        for s in STORES:
            conn.execute(
                """
                INSERT OR IGNORE INTO stores
                    (store_name, store_type, owner_name, phone,
                     address, district, city, assigned_staff_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    s["store_name"], s["store_type"], s["owner_name"], s["phone"],
                    s["address"],   s["district"],   s["city"],        s["assigned_staff_id"],
                )
            )
            print(f"  + Store: {s['store_name']} ({s['store_type']}) — {s['district']}")

    # ─── Seed products ────────────────────────────────────────────────────────
    PRODUCTS = [
        {"product_name": "Olasun Sunflower Oil 500ml", "sku": "OLA-500ML", "category": "Sunflower", "unit": "bottle", "low_stock_threshold": 15},
        {"product_name": "Olasun Sunflower Oil 1L",    "sku": "OLA-1L",    "category": "Sunflower", "unit": "bottle", "low_stock_threshold": 10},
        {"product_name": "Olasun Sunflower Oil 2L",    "sku": "OLA-2L",    "category": "Sunflower", "unit": "bottle", "low_stock_threshold": 8},
        {"product_name": "Olasun Sunflower Oil 5L",    "sku": "OLA-5L",    "category": "Sunflower", "unit": "bottle", "low_stock_threshold": 5},
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