from flask import Blueprint, request, jsonify
from database import get_db
from utils import token_required, role_required, hash_password

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

ADMIN_ROLES       = ("Sales_Admin", "Sales_Manager", "Director", "Deputy_Director")
MANAGER_ROLES     = ("Sales_Manager", "Director", "Deputy_Director")
VALID_STORE_TYPES = ("grocery", "supermarket", "agency")


@admin_bp.route("/stores", methods=["GET"])
@token_required
@role_required(*ADMIN_ROLES)
def list_stores(current_user):
    page       = max(int(request.args.get("page", 1)), 1)
    per_page   = min(int(request.args.get("per_page", 20)), 100)
    offset     = (page - 1) * per_page
    store_type = request.args.get("store_type", "").strip()
    is_active  = request.args.get("is_active", "")

    query       = """
        SELECT  s.store_id, s.store_name, s.store_type,
                s.owner_name, s.phone,
                s.address, s.district, s.city,
                s.latitude, s.longitude,
                s.is_active, s.created_at, s.updated_at,
                u.full_name AS assigned_staff_name,
                u.user_id   AS assigned_staff_id
        FROM    stores s
        JOIN    users  u ON s.assigned_staff_id = u.user_id
        WHERE   1=1
    """
    count_query  = "SELECT COUNT(*) FROM stores WHERE 1=1"
    params       = []
    count_params = []

    if store_type:
        query       += " AND s.store_type = ?"
        count_query += " AND store_type = ?"
        params.append(store_type)
        count_params.append(store_type)

    if is_active in ("0", "1"):
        query       += " AND s.is_active = ?"
        count_query += " AND is_active = ?"
        params.append(int(is_active))
        count_params.append(int(is_active))

    query += " ORDER BY s.store_id DESC LIMIT ? OFFSET ?"
    params.extend([per_page, offset])

    conn   = get_db()
    total  = conn.execute(count_query, count_params).fetchone()[0]
    stores = conn.execute(query, params).fetchall()
    conn.close()

    return jsonify({"success": True, "data": {"total": total, "page": page, "per_page": per_page, "stores": [dict(s) for s in stores]}}), 200


@admin_bp.route("/stores", methods=["POST"])
@token_required
@role_required(*ADMIN_ROLES)
def create_store(current_user):
    data = request.get_json()

    required = ["store_name", "store_type", "owner_name", "phone", "address", "district", "city", "latitude", "longitude", "assigned_staff_id"]
    missing  = [f for f in required if not data.get(f) and data.get(f) != 0]
    if missing:
        return jsonify({"success": False, "message": f"Missing required fields: {', '.join(missing)}"}), 400

    if data["store_type"] not in VALID_STORE_TYPES:
        return jsonify({"success": False, "message": "store_type must be: grocery, supermarket, or agency."}), 400

    conn  = get_db()
    staff = conn.execute("SELECT user_id FROM users WHERE user_id = ? AND is_active = 1", (data["assigned_staff_id"],)).fetchone()
    if not staff:
        conn.close()
        return jsonify({"success": False, "message": "Assigned staff not found or is inactive."}), 404

    if conn.execute("SELECT store_id FROM stores WHERE phone = ?", (data["phone"],)).fetchone():
        conn.close()
        return jsonify({"success": False, "message": "Phone number already exists."}), 409

    cursor = conn.execute(
        "INSERT INTO stores (store_name, store_type, owner_name, phone, address, district, city, latitude, longitude, assigned_staff_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (data["store_name"], data["store_type"], data["owner_name"], data["phone"], data["address"], data["district"], data["city"], data["latitude"], data["longitude"], data["assigned_staff_id"])
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return jsonify({"success": True, "message": "Store created successfully.", "data": {"store_id": new_id}}), 201


@admin_bp.route("/stores/<int:store_id>", methods=["PUT"])
@token_required
@role_required(*ADMIN_ROLES)
def update_store(current_user, store_id):
    data  = request.get_json()
    conn  = get_db()
    store = conn.execute("SELECT store_id FROM stores WHERE store_id = ?", (store_id,)).fetchone()
    if not store:
        conn.close()
        return jsonify({"success": False, "message": "Store not found."}), 404

    if "store_type" in data and data["store_type"] not in VALID_STORE_TYPES:
        conn.close()
        return jsonify({"success": False, "message": "store_type must be: grocery, supermarket, or agency."}), 400

    if "assigned_staff_id" in data:
        staff = conn.execute("SELECT user_id FROM users WHERE user_id = ? AND is_active = 1", (data["assigned_staff_id"],)).fetchone()
        if not staff:
            conn.close()
            return jsonify({"success": False, "message": "Assigned staff not found or is inactive."}), 404

    updatable = ["store_name", "store_type", "owner_name", "phone", "address", "district", "city", "latitude", "longitude", "assigned_staff_id", "is_active"]
    fields    = [f"{f} = ?" for f in updatable if f in data]
    values    = [data[f]    for f in updatable if f in data]

    if not fields:
        conn.close()
        return jsonify({"success": False, "message": "No fields to update."}), 400

    values.append(store_id)
    conn.execute(f"UPDATE stores SET {', '.join(fields)} WHERE store_id = ?", values)
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Store updated successfully."}), 200


@admin_bp.route("/stores/<int:store_id>", methods=["DELETE"])
@token_required
@role_required(*MANAGER_ROLES)
def delete_store(current_user, store_id):
    conn  = get_db()
    store = conn.execute("SELECT store_id FROM stores WHERE store_id = ? AND is_active = 1", (store_id,)).fetchone()
    if not store:
        conn.close()
        return jsonify({"success": False, "message": "Store not found or already deleted."}), 404

    conn.execute("UPDATE stores SET is_active = 0 WHERE store_id = ?", (store_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Store deleted successfully."}), 200


@admin_bp.route("/staff", methods=["GET"])
@token_required
@role_required(*ADMIN_ROLES)
def list_staff(current_user):
    page      = max(int(request.args.get("page", 1)), 1)
    per_page  = min(int(request.args.get("per_page", 20)), 100)
    offset    = (page - 1) * per_page
    role_name = request.args.get("role", "").strip()
    is_active = request.args.get("is_active", "")

    query       = """
        SELECT  u.user_id, u.full_name, u.email, u.phone,
                u.is_active,
                r.role_id, r.role_name
        FROM    users u
        JOIN    roles r ON u.role_id = r.role_id
        WHERE   1=1
    """
    count_query  = "SELECT COUNT(*) FROM users WHERE 1=1"
    params       = []
    count_params = []

    if role_name:
        query       += " AND r.role_name = ?"
        count_query += " AND role_id = (SELECT role_id FROM roles WHERE role_name = ?)"
        params.append(role_name)
        count_params.append(role_name)

    if is_active in ("0", "1"):
        query       += " AND u.is_active = ?"
        count_query += " AND is_active = ?"
        params.append(int(is_active))
        count_params.append(int(is_active))

    query += " ORDER BY u.user_id DESC LIMIT ? OFFSET ?"
    params.extend([per_page, offset])

    conn  = get_db()
    total = conn.execute(count_query, count_params).fetchone()[0]
    staff = conn.execute(query, params).fetchall()
    conn.close()

    return jsonify({"success": True, "data": {"total": total, "page": page, "per_page": per_page, "staff": [dict(s) for s in staff]}}), 200


@admin_bp.route("/staff", methods=["POST"])
@token_required
@role_required(*ADMIN_ROLES)
def create_staff(current_user):
    data    = request.get_json()
    required = ["full_name", "email", "phone", "password", "role_id"]
    missing  = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"success": False, "message": f"Missing required fields: {', '.join(missing)}"}), 400

    if len(data["password"]) < 8:
        return jsonify({"success": False, "message": "Password must be at least 8 characters."}), 400

    conn = get_db()
    if conn.execute("SELECT user_id FROM users WHERE email = ?", (data["email"],)).fetchone():
        conn.close()
        return jsonify({"success": False, "message": "Email already in use."}), 409

    if conn.execute("SELECT user_id FROM users WHERE phone = ?", (data["phone"],)).fetchone():
        conn.close()
        return jsonify({"success": False, "message": "Phone number already in use."}), 409

    if not conn.execute("SELECT role_id FROM roles WHERE role_id = ?", (data["role_id"],)).fetchone():
        conn.close()
        return jsonify({"success": False, "message": "Role not found."}), 404

    cursor = conn.execute(
        "INSERT INTO users (full_name, email, phone, password_hash, role_id) VALUES (?, ?, ?, ?, ?)",
        (data["full_name"], data["email"], data["phone"], hash_password(data["password"]), data["role_id"])
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return jsonify({"success": True, "message": "Staff account created successfully.", "data": {"user_id": new_id}}), 201


@admin_bp.route("/staff/<int:user_id>", methods=["PUT"])
@token_required
@role_required(*ADMIN_ROLES)
def update_staff(current_user, user_id):
    data = request.get_json()
    conn = get_db()

    if not conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone():
        conn.close()
        return jsonify({"success": False, "message": "Staff not found."}), 404

    if "role_id" in data and not conn.execute("SELECT role_id FROM roles WHERE role_id = ?", (data["role_id"],)).fetchone():
        conn.close()
        return jsonify({"success": False, "message": "Role not found."}), 404

    updatable = ["full_name", "phone", "role_id", "is_active"]
    fields    = [f"{f} = ?" for f in updatable if f in data]
    values    = [data[f]    for f in updatable if f in data]

    if not fields:
        conn.close()
        return jsonify({"success": False, "message": "No fields to update."}), 400

    values.append(user_id)
    conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?", values)
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Staff account updated successfully."}), 200


@admin_bp.route("/staff/<int:user_id>", methods=["DELETE"])
@token_required
@role_required(*MANAGER_ROLES)
def delete_staff(current_user, user_id):
    if user_id == current_user["user_id"]:
        return jsonify({"success": False, "message": "You cannot deactivate your own account."}), 400

    conn = get_db()
    if not conn.execute("SELECT user_id FROM users WHERE user_id = ? AND is_active = 1", (user_id,)).fetchone():
        conn.close()
        return jsonify({"success": False, "message": "Staff not found or already inactive."}), 404

    conn.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Staff account deactivated successfully."}), 200


@admin_bp.route("/roles", methods=["GET"])
@token_required
@role_required(*ADMIN_ROLES)
def list_roles(current_user):
    conn  = get_db()
    roles = conn.execute("SELECT role_id, role_name, description FROM roles ORDER BY role_id").fetchall()
    conn.close()
    return jsonify({"success": True, "data": [dict(r) for r in roles]}), 200