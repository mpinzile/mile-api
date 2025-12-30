import uuid
from fastapi import APIRouter, Request, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.db.get_db import get_db
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.enums import AppRole
from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES, MAX_COOKIE_AGE, REFRESH_TOKEN_EXPIRE_DAYS, RESET_PASSWORD_CODE_EXPIRE_MINUTES
from app.utils.helpers import create_refresh_token_entry, generate_reset_code, hash_password, mask_email, send_verification_email, success_response, error_response
from app.utils.validation_functions import (
    validate_email,
    validate_password_strength,
    validate_tanzanian_phone
)
from app.utils.auth import create_access_token, get_current_user
from app.utils.error_codes import ERROR_CODES
from app.models.cashier import Cashier
from app.models.password_reset import PasswordResetHistory, PasswordResetToken

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
            # Check if cashier is disabled
            if not cashier.is_active:
                return JSONResponse(
                    status_code=403,
                    content=error_response(
                        ERROR_CODES["FORBIDDEN"],
                        "Your account is disabled. Please contact your shop administrator."
                    )
                )
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
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    shop_id = None
    if user.role == AppRole.cashier:
        cashier = db.query(Cashier).filter(Cashier.user_id == user.id).first()
        if cashier:
            shop_id = str(cashier.shop_id)

    return success_response(
        data={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "avatar_url": None,
            "role": user.role.value,
            "shop_id": shop_id,
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

@router.post("/change-password")
async def change_password(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    body = await request.json()
    current_password = body.get("current_password")
    new_password = body.get("new_password")

    if not current_password or not new_password:
        return JSONResponse(
            status_code=400,
            content=error_response(
                ERROR_CODES["VALIDATION_ERROR"],
                "Current password and new password are required"
            )
        )

    # Verify current password
    if current_user.hashed_password != hash_password(current_password):
        return JSONResponse(
            status_code=401,
            content=error_response(
                ERROR_CODES["FORBIDDEN"],
                "Current password is incorrect"
            )
        )

    # Validate new password strength
    if not validate_password_strength(new_password):
        return JSONResponse(
            status_code=400,
            content=error_response(
                ERROR_CODES["VALIDATION_ERROR"],
                "New password is too weak"
            )
        )

    # Prevent reuse of same password
    if hash_password(new_password) == current_user.hashed_password:
        return JSONResponse(
            status_code=400,
            content=error_response(
                ERROR_CODES["VALIDATION_ERROR"],
                "New password must be different from current password"
            )
        )

    # Update password
    current_user.hashed_password = hash_password(new_password)
    current_user.updated_at = datetime.utcnow()

    # Invalidate old refresh tokens
    db.query(RefreshToken).filter(
        RefreshToken.user_id == current_user.id
    ).delete()

    db.commit()

    return success_response(
        message="Password changed successfully"
    )

@router.post("/forgot-password")
async def forgot_password(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    identifier = body.get("identifier")
    if not identifier:
        return JSONResponse(
            status_code=400,
            content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Missing identifier")
        )

    user = db.query(User).filter(
        (User.email == identifier) | (User.username == identifier) | (User.phone == identifier),
        User.deleted_at.is_(None),
        User.is_active.is_(True)
    ).first()

    if not user:
        return JSONResponse(
            status_code=404,
            content=error_response(ERROR_CODES["NOT_FOUND"], "User not found")
        )

    if user.role == AppRole.cashier:
        return JSONResponse(
            status_code=403,
            content=error_response(ERROR_CODES["FORBIDDEN"], "Cashiers cannot request password reset")
        )

    existing_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > datetime.utcnow()
    ).order_by(PasswordResetToken.created_at.desc()).first()

    if existing_token:
        return JSONResponse(
            status_code=429,
            content=error_response(ERROR_CODES["TOO_MANY_REQUESTS"], "A reset code was recently sent. Please wait until it expires.")
        )

    reset_code = generate_reset_code()
    reset_code_hash = hash_password(reset_code)
    expires_at = datetime.utcnow() + timedelta(minutes=RESET_PASSWORD_CODE_EXPIRE_MINUTES)

    token_entry = PasswordResetToken(
        user_id=user.id,
        reset_code_hash=reset_code_hash,
        expires_at=expires_at,
        attempt_count=0,
        max_attempts=5,
        created_at=datetime.utcnow()
    )
    db.add(token_entry)
    db.commit()
    db.refresh(token_entry)

    try:
        send_verification_email(user.email, reset_code, user.full_name)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=error_response(ERROR_CODES["SERVER_ERROR"], f"Failed to send reset code: {str(e)}")
        )

    masked_email = mask_email(user.email)
    return success_response(message=f"Password reset code has been sent to {masked_email}")


@router.post("/verify-reset-token")
async def verify_reset_token(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    token = body.get("token")
    if not token:
        return JSONResponse(status_code=400, content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Missing token"))

    token_hash = hash_password(token)
    token_entry = db.query(PasswordResetToken).filter(
        PasswordResetToken.reset_code_hash == token_hash,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > datetime.utcnow()
    ).first()

    if not token_entry:
        return JSONResponse(status_code=400, content=error_response(ERROR_CODES["INVALID_TOKEN"], "Invalid or expired token"))

    return success_response(message="Token is valid")

@router.post("/reset-password")
async def reset_password(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    token = body.get("token")
    new_password = body.get("new_password")

    if not token or not new_password:
        return JSONResponse(status_code=400, content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Missing token or new password"))

    if not validate_password_strength(new_password):
        return JSONResponse(status_code=400, content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Password is too weak"))

    token_hash = hash_password(token)
    token_entry = db.query(PasswordResetToken).filter(
        PasswordResetToken.reset_code_hash == token_hash,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > datetime.utcnow()
    ).first()

    if not token_entry:
        return JSONResponse(status_code=400, content=error_response(ERROR_CODES["INVALID_TOKEN"], "Invalid or expired token"))

    user = db.query(User).filter(User.id == token_entry.user_id).first()
    if not user:
        return JSONResponse(status_code=404, content=error_response(ERROR_CODES["NOT_FOUND"], "User not found"))

    # Update password
    user.hashed_password = hash_password(new_password)
    db.commit()

    # Mark token as used
    token_entry.used_at = datetime.utcnow()
    db.commit()

    # Log history
    history = PasswordResetHistory(
        user_id=user.id,
        success=True,
        ip_address=str(request.client.host) if request.client else None,
        user_agent=request.headers.get("user-agent"),
        attempted_code=token,
        created_at=datetime.utcnow()
    )
    db.add(history)
    db.commit()

    return success_response(message="Password has been reset successfully")