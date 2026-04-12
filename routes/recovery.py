from flask import Blueprint, request, jsonify
from database import get_db
from utils import token_required, role_required, hash_password, MANAGER_AND_ABOVE
import secrets, string

recovery_bp = Blueprint("recovery", __name__, url_prefix="/api/recovery")

# Staff gửi yêu cầu khôi phục (không cần auth)
@recovery_bp.route("/request", methods=["POST"])
def create_recovery_request():
    data = request.get_json()
    if not data or not data.get("email"):
        return jsonify({"success": False, "message": "Email is required."}), 400

    conn = get_db()
    user = conn.execute(
        "SELECT user_id, full_name, phone FROM users WHERE email = ? AND is_active = 1",
        (data["email"],)
    ).fetchone()

    if not user:
        conn.close()
        return jsonify({"success": False, "message": "Tài khoản không tồn tại trong hệ thống."}), 404

    # Tạo bảng nếu chưa có
    conn.execute("""
        CREATE TABLE IF NOT EXISTS password_recovery_requests (
            request_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            status      TEXT DEFAULT 'pending',
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Kiểm tra có request pending chưa
    existing = conn.execute(
        "SELECT request_id FROM password_recovery_requests WHERE user_id = ? AND status = 'pending'",
        (user["user_id"],)
    ).fetchone()

    if existing:
        conn.close()
        return jsonify({"success": True, "message": "Yêu cầu của bạn đã được gửi tới Admin. Vui lòng chờ phản hồi qua số điện thoại."}), 200

    conn.execute(
        "INSERT INTO password_recovery_requests (user_id) VALUES (?)",
        (user["user_id"],)
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Yêu cầu của bạn đã được gửi tới Admin. Vui lòng chờ phản hồi qua số điện thoại."}), 201


# Admin xem danh sách yêu cầu
@recovery_bp.route("/requests", methods=["GET"])
@token_required
@role_required(*MANAGER_AND_ABOVE)
def list_requests(current_user):
    conn = get_db()
    try:
        reqs = conn.execute("""
            SELECT pr.request_id, pr.status, pr.created_at, pr.resolved_at,
                   u.full_name, u.email, u.phone
            FROM password_recovery_requests pr
            JOIN users u ON pr.user_id = u.user_id
            ORDER BY pr.created_at DESC LIMIT 50
        """).fetchall()
    except Exception:
        conn.close()
        return jsonify({"success": True, "data": []}), 200

    conn.close()
    return jsonify({"success": True, "data": [dict(r) for r in reqs]}), 200


# Admin resolve: tạo mật khẩu tạm
@recovery_bp.route("/requests/<int:request_id>/resolve", methods=["PUT"])
@token_required
@role_required(*MANAGER_AND_ABOVE)
def resolve_request(current_user, request_id):
    conn = get_db()
    req = conn.execute(
        "SELECT * FROM password_recovery_requests WHERE request_id = ?", (request_id,)
    ).fetchone()

    if not req:
        conn.close()
        return jsonify({"success": False, "message": "Request not found."}), 404
    if req["status"] == "resolved":
        conn.close()
        return jsonify({"success": False, "message": "Already resolved."}), 400

    alphabet = string.ascii_letters + string.digits
    temp_pw  = "".join(secrets.choice(alphabet) for _ in range(10))

    conn.execute("UPDATE users SET password_hash = ? WHERE user_id = ?",
                 (hash_password(temp_pw), req["user_id"]))
    conn.execute(
        "UPDATE password_recovery_requests SET status='resolved', resolved_at=CURRENT_TIMESTAMP WHERE request_id=?",
        (request_id,)
    )
    conn.commit()
    user = conn.execute(
        "SELECT full_name, phone FROM users WHERE user_id=?", (req["user_id"],)
    ).fetchone()
    conn.close()

    return jsonify({"success": True, "message": "Password reset.",
                    "data": {"temp_password": temp_pw, "staff_name": user["full_name"], "staff_phone": user["phone"]}}), 200