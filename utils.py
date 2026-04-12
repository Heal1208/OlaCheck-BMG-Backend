import hashlib
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import request, jsonify

SECRET_KEY = os.environ.get("SECRET_KEY", "bmg-secret-key-change-in-production")
TOKEN_EXPIRY = int(os.environ.get("TOKEN_EXPIRY_HOURS", 24))

# ─── Role constants ───────────────────────────────────────────────────────────
ROLE_ADMIN = "Admin"  # Director / Deputy_Director / Sales_Manager
ROLE_MANAGER = "Manager"  # Sales_Admin / Sales_Executive / ...
ROLE_STAFF = "Staff"  # Nhân viên tuyến

ALL_ROLES = (ROLE_ADMIN, ROLE_MANAGER, ROLE_STAFF)
ADMIN_AND_ABOVE = (ROLE_ADMIN,)
MANAGER_AND_ABOVE = (ROLE_ADMIN, ROLE_MANAGER)
ALL_FIELD_ROLES = (ROLE_ADMIN, ROLE_MANAGER, ROLE_STAFF)


def hash_password(plain: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}{plain}".encode()).hexdigest()
    return f"{salt}:{h}"


def check_password(plain: str, hashed: str) -> bool:
    try:
        salt, h = hashed.split(":", 1)
        return hashlib.sha256(f"{salt}{plain}".encode()).hexdigest() == h
    except Exception:
        return False


def generate_token(user_id: int, role: str) -> str:
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # 1. Đọc từ Authorization header (ưu tiên)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        # 2. Fallback: đọc từ query param ?token=... (dùng cho file download)
        if not token:
            token = request.args.get("token", "").strip() or None

        if not token:
            return jsonify({
                "success": False,
                "message": "Token not found. Please log in."
            }), 401

        try:
            current_user = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({
                "success": False,
                "message": "Session expired. Please log in again."
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                "success": False,
                "message": "Invalid token."
            }), 401

        return f(current_user, *args, **kwargs)

    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(current_user, *args, **kwargs):
            if current_user["role"] not in roles:
                return jsonify({
                    "success": False,
                    "message": "You do not have permission to perform this action."
                }), 403
            return f(current_user, *args, **kwargs)

        return decorated

    return decorator
