from flask import Blueprint, request, jsonify
from database import get_db
from utils import token_required, role_required, MANAGER_AND_ABOVE, ALL_FIELD_ROLES

stores_bp = Blueprint("stores", __name__, url_prefix="/api/stores")


@stores_bp.route("/assigned", methods=["GET"])
@token_required
@role_required(*ALL_FIELD_ROLES)
def get_assigned_stores(current_user):
    conn = get_db()
    is_admin_or_manager = current_user["role"] in ("Admin", "Manager")

    if is_admin_or_manager:
        # Admin và Manager thấy tất cả stores đang active
        stores = conn.execute(
            """
            SELECT  s.store_id, s.store_name, s.store_type,
                    s.owner_name, s.phone,
                    s.address, s.district, s.city,
                    s.is_active,
                    u.full_name AS assigned_staff_name,
                    u.user_id   AS assigned_staff_id
            FROM    stores s
            JOIN    users  u ON s.assigned_staff_id = u.user_id
            WHERE   s.is_active = 1
            ORDER BY s.city, s.district, s.store_name
            """
        ).fetchall()
    else:
        # Staff chỉ thấy stores được giao cho mình
        stores = conn.execute(
            """
            SELECT  s.store_id, s.store_name, s.store_type,
                    s.owner_name, s.phone,
                    s.address, s.district, s.city,
                    s.is_active,
                    u.full_name AS assigned_staff_name,
                    u.user_id   AS assigned_staff_id
            FROM    stores s
            JOIN    users  u ON s.assigned_staff_id = u.user_id
            WHERE   s.assigned_staff_id = ?
            AND     s.is_active = 1
            ORDER BY s.city, s.district, s.store_name
            """,
            (current_user["user_id"],)
        ).fetchall()

    conn.close()
    return jsonify({"success": True, "data": {"total": len(stores), "stores": [dict(s) for s in stores]}}), 200


@stores_bp.route("/search", methods=["GET"])
@token_required
@role_required(*ALL_FIELD_ROLES)
def search_stores(current_user):
    keyword    = request.args.get("q", "").strip()
    district   = request.args.get("district", "").strip()
    city       = request.args.get("city", "").strip()
    store_type = request.args.get("store_type", "").strip()

    if not any([keyword, district, city, store_type]):
        return jsonify({"success": False, "message": "At least one search criterion is required."}), 400

    if store_type and store_type not in ("grocery", "supermarket", "agency"):
        return jsonify({"success": False, "message": "store_type must be: grocery, supermarket, or agency."}), 400

    query = """
        SELECT  s.store_id, s.store_name, s.store_type,
                s.owner_name, s.phone,
                s.address, s.district, s.city,
                u.full_name AS assigned_staff_name
        FROM    stores s
        JOIN    users  u ON s.assigned_staff_id = u.user_id
        WHERE   s.is_active = 1
    """
    params = []

    if keyword:
        query += " AND (s.store_name LIKE ? OR s.address LIKE ? OR s.owner_name LIKE ? OR s.phone LIKE ?)"
        like   = f"%{keyword}%"
        params.extend([like, like, like, like])

    if district:
        query += " AND s.district LIKE ?"
        params.append(f"%{district}%")

    if city:
        query += " AND s.city LIKE ?"
        params.append(f"%{city}%")

    if store_type:
        query += " AND s.store_type = ?"
        params.append(store_type)

    query += " ORDER BY s.store_name LIMIT 50"

    conn   = get_db()
    stores = conn.execute(query, params).fetchall()
    conn.close()

    return jsonify({"success": True, "data": {"keyword": keyword, "total": len(stores), "stores": [dict(s) for s in stores]}}), 200


@stores_bp.route("/<int:store_id>", methods=["GET"])
@token_required
@role_required(*ALL_FIELD_ROLES)
def get_store_detail(current_user, store_id):
    conn  = get_db()
    store = conn.execute(
        """
        SELECT  s.*, u.full_name AS assigned_staff_name
        FROM    stores s
        JOIN    users  u ON s.assigned_staff_id = u.user_id
        WHERE   s.store_id = ? AND s.is_active = 1
        """,
        (store_id,)
    ).fetchone()
    conn.close()

    if not store:
        return jsonify({"success": False, "message": "Store not found."}), 404

    return jsonify({"success": True, "data": dict(store)}), 200