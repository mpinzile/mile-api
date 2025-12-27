# app/utils/auth.py

import hashlib
import jwt
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, Request, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from db.get_db import get_db
from models.user import User
from core.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY

security = HTTPBearer()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session_id: str = Cookie(None),
    db: Session = Depends(get_db)
) -> User:
    """
    Retrieve the current user either via JWT token or session cookie.
    Priority: JWT token > session cookie
    """
    user = None

    # 1️⃣ Try JWT token first
    if credentials:
        token = credentials.credentials
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("user_id")

            if user_id:
                user = db.query(User).filter(
                    User.id == user_id,
                    User.deleted_at.is_(None),
                    User.is_active.is_(True)
                ).first()

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

    # 2️⃣ Fallback to session cookie
    if not user and session_id:
        user = db.query(User).filter(
            User.id == session_id,
            User.deleted_at.is_(None),
            User.is_active.is_(True)
        ).first()

    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return user


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compare plain password with SHA256 hashed password"""
    return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """
    Generate JWT token for user
    Expect data to contain: {"user_id": <uuid>, "role": <AppRole>}
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token


def get_user_by_credential(db: Session, credential: str) -> User:
    """
    Fetch user by username, email, or phone
    """
    return db.query(User).filter(
        (
            (User.email == credential) |
            (User.phone == credential) |
            (User.username == credential)
        ),
        User.deleted_at.is_(None),
        User.is_active.is_(True)
    ).first()
