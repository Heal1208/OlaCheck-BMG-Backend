from flask import Blueprint, request, jsonify
from database import get_db
from utils import token_required, role_required, ALL_FIELD_ROLES, MANAGER_AND_ABOVE

checkins_bp = Blueprint("checkins", __name__, url_prefix="/api")

NEAR_EXPIRY_DAYS = 30


# ================================================================
# A-07: Store Check-in
# ================================================================

@checkins_bp.route("/checkins", methods=["POST"])
@token_required
@role_required(*ALL_FIELD_ROLES)
def create_checkin(current_user):
    data = request.get_json()

    if not data or not data.get("store_id"):
        return jsonify({"success": False, "message": "store_id is required."}), 400

    conn = get_db()

    store = conn.execute(
        "SELECT store_id, store_name, assigned_staff_id FROM stores WHERE store_id = ? AND is_active = 1",
        (data["store_id"],)
    ).fetchone()

    if not store:
        conn.close()
        return jsonify({"success": False, "message": "Store not found."}), 404

    # Admin và Manager có thể check-in bất kỳ store nào
    # Staff chỉ check-in store được giao
    if current_user["role"] == "Staff":
        if store["assigned_staff_id"] != current_user["user_id"]:
            conn.close()
            return jsonify({"success": False, "message": "You are not assigned to this store."}), 403

    from datetime import datetime
    import base64
    import uuid
    import os

    check_time = None
    raw_time = data.get("check_time")
    if raw_time:
        try:
            check_time = datetime.strptime(raw_time, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            conn.close()
            return jsonify({"success": False, "message": "check_time must be in format YYYY-MM-DD HH:MM:SS."}), 400

    photo_path = None
    photo_data = data.get("photo_data")
    if photo_data:
        try:
            if "base64," in photo_data:
                header, encoded = photo_data.split("base64,", 1)
            else:
                encoded = photo_data
            img_bytes = base64.b64decode(encoded)
            upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads")
            os.makedirs(upload_dir, exist_ok=True)
            filename = f"checkin_{uuid.uuid4().hex}.jpg"
            filepath = os.path.join(upload_dir, filename)
            with open(filepath, "wb") as f:
                f.write(img_bytes)
            photo_path = f"/static/uploads/{filename}"
        except Exception as e:
            conn.close()
            return jsonify({"success": False, "message": f"Failed to save photo: {e}"}), 400

    if check_time:
        cursor = conn.execute(
            "INSERT INTO store_checks (store_id, staff_id, note, status, check_time, photo_path) VALUES (?, ?, ?, 'completed', ?, ?)",
            (data["store_id"], current_user["user_id"], data.get("note"), check_time, photo_path)
        )
    else:
        cursor = conn.execute(
            "INSERT INTO store_checks (store_id, staff_id, note, status, photo_path) VALUES (?, ?, ?, 'completed', ?)",
            (data["store_id"], current_user["user_id"], data.get("note"), photo_path)
        )

    conn.commit()
    check_id = cursor.lastrowid
    conn.close()

    return jsonify({
        "success": True,
        "message": "Check-in successful.",
        "data": {
            "check_id":   check_id,
            "store_name": store["store_name"],
        }
    }), 201


@checkins_bp.route("/checkins", methods=["GET"])
@token_required
@role_required(*ALL_FIELD_ROLES)
def list_checkins(current_user):
    store_id = request.args.get("store_id")
    date     = request.args.get("date")

    query = """
        SELECT  c.check_id, c.store_id, c.staff_id,
                c.check_time, c.note, c.status,
                s.store_name, u.full_name AS staff_name
        FROM    store_checks c
        JOIN    stores s ON c.store_id = s.store_id
        JOIN    users  u ON c.staff_id = u.user_id
        WHERE   1=1
    """
    params = []

    if current_user["role"] == "Staff":
        query += " AND c.staff_id = ?"
        params.append(current_user["user_id"])

    if store_id:
        query += " AND c.store_id = ?"
        params.append(store_id)

    if date:
        query += " AND DATE(c.check_time) = ?"
        params.append(date)

    query += " ORDER BY c.check_time DESC LIMIT 50"

    conn   = get_db()
    checks = conn.execute(query, params).fetchall()
    conn.close()

    return jsonify({"success": True, "data": [dict(c) for c in checks]}), 200


@checkins_bp.route("/checkins/<int:check_id>", methods=["GET"])
@token_required
@role_required(*ALL_FIELD_ROLES)
def get_checkin(current_user, check_id):
    conn  = get_db()
    check = conn.execute(
        """
        SELECT  c.*, s.store_name, u.full_name AS staff_name
        FROM    store_checks c
        JOIN    stores s ON c.store_id = s.store_id
        JOIN    users  u ON c.staff_id = u.user_id
        WHERE   c.check_id = ?
        """,
        (check_id,)
    ).fetchone()
    conn.close()

    if not check:
        return jsonify({"success": False, "message": "Check-in not found."}), 404

    return jsonify({"success": True, "data": dict(check)}), 200


@checkins_bp.route("/checkins/<int:check_id>/complete", methods=["PUT"])
@token_required
@role_required(*ALL_FIELD_ROLES)
def complete_checkin(current_user, check_id):
    conn  = get_db()
    check = conn.execute(
        "SELECT check_id, staff_id FROM store_checks WHERE check_id = ?",
        (check_id,)
    ).fetchone()

    if not check:
        conn.close()
        return jsonify({"success": False, "message": "Check-in not found."}), 404

    if check["staff_id"] != current_user["user_id"]:
        conn.close()
        return jsonify({"success": False, "message": "You can only complete your own check-ins."}), 403

    conn.execute(
        "UPDATE store_checks SET status = 'completed' WHERE check_id = ?",
        (check_id,)
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Check-in completed."}), 200


# ================================================================
# A-08: Stock Entry
# ================================================================

@checkins_bp.route("/checkins/<int:check_id>/stock-entries", methods=["POST"])
@token_required
@role_required(*ALL_FIELD_ROLES)
def create_stock_entries(current_user, check_id):
    data = request.get_json()

    if not data or not data.get("entries"):
        return jsonify({"success": False, "message": "entries array is required."}), 400

    conn  = get_db()
    check = conn.execute(
        "SELECT check_id, store_id, staff_id FROM store_checks WHERE check_id = ?",
        (check_id,)
    ).fetchone()

    if not check:
        conn.close()
        return jsonify({"success": False, "message": "Check-in not found."}), 404

    if check["staff_id"] != current_user["user_id"]:
        conn.close()
        return jsonify({"success": False, "message": "You can only add entries to your own check-ins."}), 403

    inserted  = []
    low_stock = []
    store_id  = check["store_id"]

    for entry in data["entries"]:
        product_id = entry.get("product_id")
        quantity   = entry.get("quantity_on_shelf", 0)

        if product_id is None:
            continue

        product = conn.execute(
            "SELECT product_id, product_name, low_stock_threshold FROM products WHERE product_id = ? AND is_active = 1",
            (product_id,)
        ).fetchone()

        if not product:
            continue

        existing = conn.execute(
            "SELECT entry_id FROM stock_entries WHERE check_id = ? AND product_id = ?",
            (check_id, product_id)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE stock_entries SET quantity_on_shelf = ? WHERE entry_id = ?",
                (quantity, existing["entry_id"])
            )
            entry_id = existing["entry_id"]
        else:
            cursor   = conn.execute(
                "INSERT INTO stock_entries (check_id, product_id, quantity_on_shelf) VALUES (?, ?, ?)",
                (check_id, product_id, quantity)
            )
            entry_id = cursor.lastrowid

        inserted.append({"entry_id": entry_id, "product_id": product_id, "quantity_on_shelf": quantity})

        threshold = product["low_stock_threshold"]
        if quantity < threshold:
            existing_alert = conn.execute(
                "SELECT alert_id FROM stock_alerts WHERE check_id = ? AND product_id = ? AND alert_type = 'low_stock'",
                (check_id, product_id)
            ).fetchone()

            if not existing_alert:
                conn.execute(
                    "INSERT INTO stock_alerts (store_id, product_id, check_id, quantity_at_alert, alert_type) VALUES (?, ?, ?, ?, 'low_stock')",
                    (store_id, product_id, check_id, quantity)
                )
                low_stock.append({
                    "product_id":   product_id,
                    "product_name": product["product_name"],
                    "quantity":     quantity,
                    "threshold":    threshold
                })

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"{len(inserted)} stock entries saved.",
        "data": {
            "entries":          inserted,
            "low_stock_alerts": low_stock
        }
    }), 201


@checkins_bp.route("/checkins/<int:check_id>/stock-entries", methods=["GET"])
@token_required
@role_required(*ALL_FIELD_ROLES)
def get_stock_entries(current_user, check_id):
    conn    = get_db()
    entries = conn.execute(
        """
        SELECT  se.entry_id, se.product_id, se.quantity_on_shelf, se.created_at,
                p.product_name, p.sku, p.unit, p.low_stock_threshold
        FROM    stock_entries se
        JOIN    products p ON se.product_id = p.product_id
        WHERE   se.check_id = ?
        ORDER BY p.product_name
        """,
        (check_id,)
    ).fetchall()
    conn.close()

    return jsonify({"success": True, "data": [dict(e) for e in entries]}), 200


# ================================================================
# A-09: Expiry Date Check
# ================================================================

@checkins_bp.route("/stock-entries/<int:entry_id>/expiry-records", methods=["POST"])
@token_required
@role_required(*ALL_FIELD_ROLES)
def create_expiry_record(current_user, entry_id):
    data = request.get_json()

    required = ["batch_code", "production_date", "expiry_date", "quantity"]
    missing  = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"success": False, "message": f"Missing required fields: {', '.join(missing)}"}), 400

    conn  = get_db()
    entry = conn.execute(
        """
        SELECT  se.entry_id, se.check_id, sc.staff_id, sc.store_id
        FROM    stock_entries se
        JOIN    store_checks  sc ON se.check_id = sc.check_id
        WHERE   se.entry_id = ?
        """,
        (entry_id,)
    ).fetchone()

    if not entry:
        conn.close()
        return jsonify({"success": False, "message": "Stock entry not found."}), 404

    if entry["staff_id"] != current_user["user_id"]:
        conn.close()
        return jsonify({"success": False, "message": "You can only add expiry records to your own entries."}), 403

    from datetime import date, datetime
    today          = date.today()
    expiry_date    = datetime.strptime(data["expiry_date"], "%Y-%m-%d").date()
    days_left      = (expiry_date - today).days
    is_near_expiry = 1 if 0 <= days_left <= NEAR_EXPIRY_DAYS else 0

    cursor    = conn.execute(
        "INSERT INTO expiry_records (entry_id, batch_code, production_date, expiry_date, quantity, is_near_expiry) VALUES (?, ?, ?, ?, ?, ?)",
        (entry_id, data["batch_code"], data["production_date"], data["expiry_date"], data["quantity"], is_near_expiry)
    )
    expiry_id = cursor.lastrowid

    if is_near_expiry:
        product_id = conn.execute(
            "SELECT product_id FROM stock_entries WHERE entry_id = ?", (entry_id,)
        ).fetchone()["product_id"]

        existing_alert = conn.execute(
            "SELECT alert_id FROM stock_alerts WHERE check_id = ? AND product_id = ? AND alert_type = 'near_expiry'",
            (entry["check_id"], product_id)
        ).fetchone()

        if not existing_alert:
            conn.execute(
                "INSERT INTO stock_alerts (store_id, product_id, check_id, quantity_at_alert, alert_type) VALUES (?, ?, ?, ?, 'near_expiry')",
                (entry["store_id"], product_id, entry["check_id"], data["quantity"])
            )

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Expiry record saved.",
        "data": {
            "expiry_id":      expiry_id,
            "is_near_expiry": bool(is_near_expiry),
            "days_left":      days_left
        }
    }), 201


@checkins_bp.route("/stock-entries/<int:entry_id>/expiry-records", methods=["GET"])
@token_required
@role_required(*ALL_FIELD_ROLES)
def get_expiry_records(current_user, entry_id):
    conn    = get_db()
    records = conn.execute(
        "SELECT * FROM expiry_records WHERE entry_id = ? ORDER BY expiry_date",
        (entry_id,)
    ).fetchall()
    conn.close()

    return jsonify({"success": True, "data": [dict(r) for r in records]}), 200


# ================================================================
# A-10: Low Stock Alerts  — Admin + Manager có thể xem và resolve
# ================================================================

@checkins_bp.route("/alerts", methods=["GET"])
@token_required
@role_required(*MANAGER_AND_ABOVE)
def list_alerts(current_user):
    store_id    = request.args.get("store_id")
    alert_type  = request.args.get("alert_type")
    is_resolved = request.args.get("is_resolved", "0")

    query = """
        SELECT  a.alert_id, a.store_id, a.product_id, a.check_id,
                a.quantity_at_alert, a.alert_type,
                a.is_resolved, a.resolved_by, a.resolved_at, a.created_at,
                s.store_name, s.district, s.city,
                p.product_name, p.sku, p.low_stock_threshold,
                u.full_name AS resolved_by_name
        FROM    stock_alerts a
        JOIN    stores   s ON a.store_id   = s.store_id
        JOIN    products p ON a.product_id = p.product_id
        LEFT JOIN users  u ON a.resolved_by = u.user_id
        WHERE   1=1
    """
    params = []

    if store_id:
        query += " AND a.store_id = ?"
        params.append(store_id)

    if alert_type in ("low_stock", "near_expiry"):
        query += " AND a.alert_type = ?"
        params.append(alert_type)

    if is_resolved in ("0", "1"):
        query += " AND a.is_resolved = ?"
        params.append(int(is_resolved))

    query += " ORDER BY a.created_at DESC LIMIT 100"

    conn   = get_db()
    alerts = conn.execute(query, params).fetchall()
    conn.close()

    return jsonify({"success": True, "data": {"total": len(alerts), "alerts": [dict(a) for a in alerts]}}), 200


@checkins_bp.route("/alerts/<int:alert_id>/resolve", methods=["PUT"])
@token_required
@role_required(*MANAGER_AND_ABOVE)
def resolve_alert(current_user, alert_id):
    conn  = get_db()
    alert = conn.execute(
        "SELECT alert_id, is_resolved FROM stock_alerts WHERE alert_id = ?",
        (alert_id,)
    ).fetchone()

    if not alert:
        conn.close()
        return jsonify({"success": False, "message": "Alert not found."}), 404

    if alert["is_resolved"]:
        conn.close()
        return jsonify({"success": False, "message": "Alert already resolved."}), 400

    conn.execute(
        "UPDATE stock_alerts SET is_resolved = 1, resolved_by = ?, resolved_at = CURRENT_TIMESTAMP WHERE alert_id = ?",
        (current_user["user_id"], alert_id)
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Alert resolved."}), 200


# GET /api/products
@checkins_bp.route("/products", methods=["GET"])
@token_required
@role_required(*ALL_FIELD_ROLES)
def list_products(current_user):
    conn     = get_db()
    products = conn.execute(
        "SELECT product_id, product_name, sku, category, unit, low_stock_threshold FROM products WHERE is_active = 1 ORDER BY product_name"
    ).fetchall()
    conn.close()

    return jsonify({"success": True, "data": [dict(p) for p in products]}), 200


# POST /api/products
@checkins_bp.route("/products", methods=["POST"])
@token_required
@role_required(*MANAGER_AND_ABOVE)
def create_product(current_user):
    data    = request.get_json()
    required = ["product_name", "sku", "category"]
    missing  = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"success": False, "message": f"Missing required fields: {', '.join(missing)}"}), 400

    conn = get_db()
    if conn.execute("SELECT product_id FROM products WHERE sku = ?", (data["sku"],)).fetchone():
        conn.close()
        return jsonify({"success": False, "message": "SKU already exists."}), 409

    cursor = conn.execute(
        "INSERT INTO products (product_name, sku, category, unit, low_stock_threshold) VALUES (?, ?, ?, ?, ?)",
        (data["product_name"], data["sku"], data["category"], data.get("unit", "bottle"), data.get("low_stock_threshold", 10))
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return jsonify({"success": True, "message": "Product created.", "data": {"product_id": new_id}}), 201


# PUT /api/products/<product_id>
@checkins_bp.route("/products/<int:product_id>", methods=["PUT"])
@token_required
@role_required(*MANAGER_AND_ABOVE)
def update_product(current_user, product_id):
    data = request.get_json()
    conn = get_db()

    product = conn.execute(
        "SELECT product_id FROM products WHERE product_id = ? AND is_active = 1",
        (product_id,)
    ).fetchone()

    if not product:
        conn.close()
        return jsonify({"success": False, "message": "Product not found."}), 404

    updatable = ["product_name", "sku", "category", "unit", "low_stock_threshold"]
    fields = [f"{f} = ?" for f in updatable if f in data]
    values = [data[f] for f in updatable if f in data]

    if not fields:
        conn.close()
        return jsonify({"success": False, "message": "No fields to update."}), 400

    values.append(product_id)
    conn.execute(f"UPDATE products SET {', '.join(fields)} WHERE product_id = ?", values)
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Product updated successfully."}), 200