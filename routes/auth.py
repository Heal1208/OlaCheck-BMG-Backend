# routes/auth.py
# ---------------------------------------------------------------
# A-01  Sign In
# A-02  Sign Out
# A-04  Modify Password
# ---------------------------------------------------------------
from flask import Blueprint, request, jsonify
from database import get_db
from utils import token_required, generate_token, hash_password, check_password

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


# ---------------------------------------------------------------
# A-01: Sign In
# POST /api/auth/login
# Body: { "email": "...", "password": "..." }
# ---------------------------------------------------------------
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    if not data or not data.get("email") or not data.get("password"):
        return jsonify({
            "success": False,
            "message": "Email và mật khẩu không được để trống"
        }), 400

    conn = get_db()
    user = conn.execute(
        """
        SELECT  u.user_id, u.full_name, u.email,
                u.password_hash, u.is_active,
                r.role_name
        FROM    users u
        JOIN    roles r ON u.role_id = r.role_id
        WHERE   u.email = ?
        """,
        (data["email"],)
    ).fetchone()
    conn.close()

    if not user:
        return jsonify({
            "success": False,
            "message": "Email hoặc mật khẩu không đúng"
        }), 401

    if not user["is_active"]:
        return jsonify({
            "success": False,
            "message": "Tài khoản đã bị vô hiệu hóa. Vui lòng liên hệ quản trị viên"
        }), 403

    if not check_password(data["password"], user["password_hash"]):
        return jsonify({
            "success": False,
            "message": "Email hoặc mật khẩu không đúng"
        }), 401

    token = generate_token(user["user_id"], user["role_name"])

    return jsonify({
        "success": True,
        "message": "Đăng nhập thành công",
        "data": {
            "token": token,
            "user": {
                "user_id":   user["user_id"],
                "full_name": user["full_name"],
                "email":     user["email"],
                "role":      user["role_name"]
            }
        }
    }), 200


# ---------------------------------------------------------------
# A-02: Sign Out
# POST /api/auth/logout
# Header: Authorization: Bearer <token>
# ---------------------------------------------------------------
@auth_bp.route("/logout", methods=["POST"])
@token_required
def logout(current_user):
    conn = get_db()
    conn.execute(
        "UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
        (current_user["user_id"],)
    )
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Đăng xuất thành công"
    }), 200


# ---------------------------------------------------------------
# A-04: Modify Password
# PUT /api/auth/change-password
# Header: Authorization: Bearer <token>
# Body: { "current_password": "...", "new_password": "..." }
# ---------------------------------------------------------------
@auth_bp.route("/change-password", methods=["PUT"])
@token_required
def change_password(current_user):
    data = request.get_json()

    if not data or not data.get("current_password") or not data.get("new_password"):
        return jsonify({
            "success": False,
            "message": "Vui lòng nhập mật khẩu hiện tại và mật khẩu mới"
        }), 400

    if len(data["new_password"]) < 8:
        return jsonify({
            "success": False,
            "message": "Mật khẩu mới phải có ít nhất 8 ký tự"
        }), 400

    if data["current_password"] == data["new_password"]:
        return jsonify({
            "success": False,
            "message": "Mật khẩu mới không được trùng mật khẩu hiện tại"
        }), 400

    conn = get_db()
    user = conn.execute(
        "SELECT password_hash FROM users WHERE user_id = ?",
        (current_user["user_id"],)
    ).fetchone()

    if not check_password(data["current_password"], user["password_hash"]):
        conn.close()
        return jsonify({
            "success": False,
            "message": "Mật khẩu hiện tại không đúng"
        }), 401

    conn.execute(
        """
        UPDATE users
        SET    password_hash = ?,
               updated_at    = CURRENT_TIMESTAMP
        WHERE  user_id = ?
        """,
        (hash_password(data["new_password"]), current_user["user_id"])
    )
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Đổi mật khẩu thành công"
    }), 200