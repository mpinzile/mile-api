# backend/utils/helpers.py
from datetime import timedelta
import datetime
import hashlib
import random
import uuid
from app.core.config import REFRESH_TOKEN_EXPIRE_DAYS
from app.models.refresh_token import RefreshToken
from app.models.user import User
from sqlalchemy.orm import Session

def success_response(data=None, message="Operation successful"):
    return {"success": True, "data": data, "message": message}

def error_response(code, message, details=None):
    return {"success": False, "error": {"code": code, "message": message, "details": details}}

def mask_email(email: str) -> str:
    try:
        local, domain = email.split("@")
        if len(local) <= 2:
            local_masked = local[0] + "***"
        else:
            local_masked = local[0] + "***" + local[-1]
        return f"{local_masked}@{domain}"
    except Exception:
        return "***"

def mask_phone(phone: str) -> str:
    # Show country code and last 2–3 digits only
    if len(phone) < 6:
        return "***"
    return phone[:4] + "****" + phone[-2:]

def generate_otp(length=6):
    return "".join([str(random.randint(0, 9)) for _ in range(length)])

def get_expiry(minutes=5):
    return datetime.utcnow() + timedelta(minutes=minutes)

def generate_refresh_token() -> str:
    """
    Generate a secure, unique refresh token
    Can be stored in the database linked to a user
    """
    return str(uuid.uuid4())

def create_refresh_token_entry(user: User, db: Session) -> str:
    token_str = generate_refresh_token()
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh = RefreshToken(user_id=user.id, token=token_str, expires_at=expires_at)
    db.add(refresh)
    db.commit()
    db.refresh(refresh)
    return refresh.token


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()