import uuid
from fastapi import APIRouter, Request, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.get_db import get_db
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.enums import AppRole
from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES, MAX_COOKIE_AGE, REFRESH_TOKEN_EXPIRE_DAYS
from app.utils.helpers import create_refresh_token_entry, hash_password, success_response, error_response
from app.utils.validation_functions import (
    validate_email,
    validate_password_strength,
    validate_tanzanian_phone
)
from app.utils.auth import create_access_token, get_current_user
from app.utils.error_codes import ERROR_CODES
from app.models.cashier import Cashier

router = APIRouter()


@router.post("/register")
async def register(request: Request, response: Response, db: Session = Depends(get_db)):
    body = await request.json()
    email = body.get("email")
    password = body.get("password")
    full_name = body.get("full_name")
    phone = body.get("phone")

    if not all([email, password, full_name, phone]):
        return JSONResponse(
            status_code=400,
            content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Missing required fields")
        )

    if not validate_email(email):
        return JSONResponse(
            status_code=400,
            content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Invalid email format")
        )

    try:
        phone = validate_tanzanian_phone(phone)
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content=error_response(ERROR_CODES["VALIDATION_ERROR"], str(e))
        )

    if not validate_password_strength(password):
        return JSONResponse(
            status_code=400,
            content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Password is too weak")
        )

    if db.query(User).filter(User.email == email).first():
        return JSONResponse(
            status_code=400,
            content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Email already registered")
        )
    
    if db.query(User).filter(User.phone == phone).first():
        return JSONResponse(
            status_code=400,
            content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Phone number already registered")
        )
    
    base_username = email.split("@")[0]
    username = base_username
    while db.query(User).filter(User.username == username).first():
        unique_suffix = str(uuid.uuid4())[:8]
        username = f"{base_username}_{unique_suffix}"

    user = User(
        username=username,
        email=email,
        full_name=full_name,
        phone=phone,
        hashed_password=hash_password(password),
        role=AppRole.superadmin,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token({
        "user_id": str(user.id),
        "role": user.role.value
    })
    refresh_token = create_refresh_token_entry(user, db)

    response.set_cookie(
        key="session_id",
        value=str(user.id),
        httponly=True,
        max_age=MAX_COOKIE_AGE,
        samesite="lax"
    )

    return success_response(
        data={
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "phone": user.phone,
                "role": user.role.value,
                "created_at": user.created_at.isoformat()
            },
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
        },
        message="Registration successful"
    )

@router.post("/login")
async def login(request: Request, response: Response, db: Session = Depends(get_db)):
    body = await request.json()
    identifier = body.get("identifier")
    password = body.get("password")

    if not identifier or not password:
        return JSONResponse(
            status_code=400,
            content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Missing login credentials")
        )

    # Normalize phone if identifier looks like a Tanzanian phone number
    try:
        normalized_phone = validate_tanzanian_phone(identifier)
    except ValueError:
        normalized_phone = None  # Not a valid phone

    # Find user by email, username, or phone
    user = db.query(User).filter(
        or_(
            User.email == identifier,
            User.username == identifier,
            User.phone == normalized_phone
        ),
        User.deleted_at.is_(None),
        User.is_active.is_(True)
    ).first()

    if not user or user.hashed_password != hash_password(password):
        return JSONResponse(
            status_code=401,
            content=error_response(ERROR_CODES["FORBIDDEN"], "Invalid credentials")
        )

    # Determine shop_id if user is a cashier
    shop_id = None
    if user.role == AppRole.cashier:
        cashier = db.query(Cashier).filter(Cashier.user_id == user.id).first()
        if cashier:
            shop_id = str(cashier.shop_id)

    # Create tokens
    access_token = create_access_token({
        "user_id": str(user.id),
        "role": user.role.value,
        "shop_id": shop_id  # optional, include in JWT
    })
    refresh_token = create_refresh_token_entry(user, db)

    # Set session cookie
    response.set_cookie(
        key="session_id",
        value=str(user.id),
        httponly=True,
        max_age=MAX_COOKIE_AGE,
        samesite="lax"
    )

    return success_response(
        data={
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value,
                "shop_id": shop_id
            },
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
        },
        message="Login successful"
    )


@router.post("/refresh")
async def refresh_token(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    token_str = body.get("refresh_token")

    if not token_str:
        return JSONResponse(
            status_code=400,
            content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Refresh token required")
        )

    refresh = db.query(RefreshToken).filter(
        RefreshToken.token == token_str,
        RefreshToken.revoked.is_(False),
        RefreshToken.expires_at > datetime.utcnow()
    ).first()

    if not refresh:
        return JSONResponse(
            status_code=401,
            content=error_response(ERROR_CODES["FORBIDDEN"], "Invalid or expired refresh token")
        )

    user = db.query(User).filter(User.id == refresh.user_id).first()
    access_token = create_access_token({
        "user_id": str(user.id),
        "role": user.role.value
    })
    return success_response(
        data={
            "access_token": access_token,
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
    )


@router.post("/logout")
async def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    body = await request.json()
    token_str = body.get("refresh_token")

    if token_str:
        refresh = db.query(RefreshToken).filter(RefreshToken.token == token_str).first()
        if refresh:
            refresh.revoked = True
            db.commit()

    response.delete_cookie(
        key="session_id",
        path="/",
        samesite="lax",
        httponly=True
    )

    return success_response(message="Logged out successfully")


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return success_response(
        data={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "avatar_url": None,
            "role": user.role.value,
            "shop_id": None,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat()
        }
    )


@router.put("/me")
async def update_profile(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role.value == "cashier":
        return JSONResponse(
            status_code=403,
            content=error_response(
                ERROR_CODES["FORBIDDEN"],
                "Cashiers are not allowed to update their profile"
            )
        )

    body = await request.json()

    if "full_name" in body:
        user.full_name = body["full_name"]

    if "phone" in body:
        from utils.validation_functions import validate_tanzanian_phone
        new_phone = validate_tanzanian_phone(body["phone"])

        existing_user = db.query(User).filter(
            User.phone == new_phone,
            User.id != user.id
        ).first()
        if existing_user:
            return JSONResponse(
                status_code=400,
                content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Phone number already in use")
            )
        user.phone = new_phone

    if "email" in body:
        new_email = body["email"].strip().lower()
        existing_user = db.query(User).filter(
            User.email == new_email,
            User.id != user.id
        ).first()
        if existing_user:
            return JSONResponse(
                status_code=400,
                content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Email already in use")
            )
        user.email = new_email

    if "username" in body:
        new_username = body["username"].strip()
        existing_user = db.query(User).filter(
            User.username == new_username,
            User.id != user.id
        ).first()
        if existing_user:
            return JSONResponse(
                status_code=400,
                content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Username already in use")
            )
        user.username = new_username

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    return success_response(message="Profile updated successfully")