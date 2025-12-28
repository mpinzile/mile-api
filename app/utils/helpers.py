# app/utils/helpers.py
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
from http.client import HTTPException
import random
import uuid
from app.core.config import REFRESH_TOKEN_EXPIRE_DAYS
from app.models.refresh_token import RefreshToken
from app.models.user import User
from sqlalchemy.orm import Session
from app.models.cash_balance import CashBalance
from app.models.float import FloatBalance
from app.models.cashier import Cashier
from app.models.shop import Shop

def success_response(data=None, message="Operation successful", pagination=None):
    response = {"success": True, "data": data, "message": message}
    if pagination is not None:
        response["pagination"] = pagination
    return response


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

def update_balances(db: Session, shop_id: str, provider_id: str, category: str, amount: Decimal, operation: str, is_new_capital: bool = False):
    # Update float balance
    float_balance = db.query(FloatBalance).filter_by(
        shop_id=shop_id, provider_id=provider_id, category=category
    ).first()
    if not float_balance:
        float_balance = FloatBalance(shop_id=shop_id, provider_id=provider_id, category=category, balance=0)
        db.add(float_balance)

    prev_float = float(float_balance.balance)

    # Update cash balance
    cash_balance = db.query(CashBalance).filter_by(shop_id=shop_id).first()
    if not cash_balance:
        cash_balance = CashBalance(shop_id=shop_id, balance=0, opening_balance=0)
        db.add(cash_balance)

    prev_cash = float(cash_balance.balance)

    if operation == "top_up":
        float_balance.balance += amount
        if not is_new_capital:  # only decrement cash if NOT new capital
            cash_balance.balance -= amount
    elif operation == "withdraw":
        float_balance.balance -= amount
        cash_balance.balance += amount


    float_balance.last_updated = datetime.utcnow()
    cash_balance.last_updated = datetime.utcnow()
    db.commit()
    db.refresh(float_balance)
    db.refresh(cash_balance)

    return {
        "float_balance": {"previous": prev_float, "current": float(float_balance.balance), "change": float(float_balance.balance - prev_float)},
        "cash_balance": {"previous": prev_cash, "current": float(cash_balance.balance), "change": float(cash_balance.balance - prev_cash)}
    }

def verify_shop_access(db: Session, shop_id: str, current_user: User):
    """
    Ensure shop exists (404) and that current_user is owner or cashier (403).
    Returns the shop object on success.
    """
    # 1) Load shop once
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    # 2) If owner, allow
    if shop.owner_id == current_user.id:
        return shop

    # 3) Otherwise check cashier membership
    is_cashier = db.query(Cashier).filter(
        Cashier.shop_id == shop_id,
        Cashier.user_id == current_user.id
    ).first() is not None

    if not is_cashier:
        raise HTTPException(status_code=403, detail="You do not have access to this shop")

    return shop