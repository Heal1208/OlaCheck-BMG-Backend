from flask import Blueprint, request, jsonify
from database import get_db
from utils import token_required, generate_token, hash_password, check_password

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"success": False, "message": "Email and password are required."}), 400

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
        return jsonify({"success": False, "message": "Invalid email or password."}), 401

    if not user["is_active"]:
        return jsonify({"success": False, "message": "Account is disabled. Please contact your administrator."}), 403

    if not check_password(data["password"], user["password_hash"]):
        return jsonify({"success": False, "message": "Invalid email or password."}), 401

    token = generate_token(user["user_id"], user["role_name"])

    return jsonify({
        "success": True,
        "message": "Login successful.",
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
    return jsonify({"success": True, "message": "Logged out successfully."}), 200


@auth_bp.route("/change-password", methods=["PUT"])
@token_required
def change_password(current_user):
    data = request.get_json()

    if not data or not data.get("current_password") or not data.get("new_password"):
        return jsonify({"success": False, "message": "Current password and new password are required."}), 400

    if len(data["new_password"]) < 8:
        return jsonify({"success": False, "message": "New password must be at least 8 characters."}), 400

    if data["current_password"] == data["new_password"]:
        return jsonify({"success": False, "message": "New password must be different from the current password."}), 400

    conn = get_db()
    user = conn.execute(
        "SELECT password_hash FROM users WHERE user_id = ?",
        (current_user["user_id"],)
    ).fetchone()

    if not check_password(data["current_password"], user["password_hash"]):
        conn.close()
        return jsonify({"success": False, "message": "Current password is incorrect."}), 401

    conn.execute(
        "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
        (hash_password(data["new_password"]), current_user["user_id"])
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Password changed successfully."}), 200