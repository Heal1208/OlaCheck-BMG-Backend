import jwt
import hashlib
import secrets
from functools import wraps
from flask import request, jsonify
from datetime import datetime, timedelta
import os

SECRET_KEY  = os.environ.get("SECRET_KEY", "bmg-secret-key-change-in-production")
TOKEN_EXPIRY = int(os.environ.get("TOKEN_EXPIRY_HOURS", 24))


# ----------------------------------------------------------------
# Password  (sha256 + salt — thay bcrypt do môi trường offline)
# Production nên dùng bcrypt hoặc argon2
# ----------------------------------------------------------------
def hash_password(plain: str) -> str:
    salt = secrets.token_hex(16)
    h    = hashlib.sha256(f"{salt}{plain}".encode()).hexdigest()
    return f"{salt}:{h}"

def check_password(plain: str, hashed: str) -> bool:
    try:
        salt, h = hashed.split(":", 1)
        return hashlib.sha256(f"{salt}{plain}".encode()).hexdigest() == h
    except Exception:
        return False


# ----------------------------------------------------------------
# JWT
# ----------------------------------------------------------------
def generate_token(user_id: int, role: str) -> str:
    payload = {
        "user_id": user_id,
        "role":    role,
        "exp":     datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])


# ----------------------------------------------------------------
# Decorators
# ----------------------------------------------------------------
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        if not token:
            return jsonify({
                "success": False,
                "message": "Token không tồn tại. Vui lòng đăng nhập"
            }), 401

        try:
            current_user = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({
                "success": False,
                "message": "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại"
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                "success": False,
                "message": "Token không hợp lệ"
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
                    "message": "Bạn không có quyền thực hiện thao tác này"
                }), 403
            return f(current_user, *args, **kwargs)
        return decorated
    return decorator