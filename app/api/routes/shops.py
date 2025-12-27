from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.get_db import get_db
from app.models.cashier import Cashier
from app.models.shop import Shop
from app.models.user import User
from app.utils.helpers import hash_password, success_response, error_response
from app.utils.auth import get_current_user
from app.utils.error_codes import ERROR_CODES
from app.utils.validation_functions import validate_email, validate_tanzanian_phone

router = APIRouter()


@router.post("/")
async def create_shop(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    body = await request.json()
    name = body.get("name")
    location = body.get("location")

    if not all([name, location]):
        return JSONResponse(
            status_code=400,
            content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Missing required fields")
        )

    shop = Shop(
        name=name,
        location=location,
        owner_id=current_user.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(shop)
    db.commit()
    db.refresh(shop)

    return success_response(
        data={
            "id": str(shop.id),
            "name": shop.name,
            "location": shop.location,
            "owner_id": str(shop.owner_id),
            "created_at": shop.created_at.isoformat(),
            "updated_at": shop.updated_at.isoformat()
        },
        message="Shop created successfully"
    )


@router.put("/{shop_id}")
async def update_shop(shop_id: str, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    body = await request.json()
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    if "name" in body:
        shop.name = body["name"]
    if "location" in body:
        shop.location = body["location"]
    if "is_active" in body:
        shop.is_active = body["is_active"]

    shop.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(shop)

    return success_response(
        data={
            "id": str(shop.id),
            "name": shop.name,
            "location": shop.location,
            "is_active": getattr(shop, "is_active", True),
            "owner_id": str(shop.owner_id),
            "created_at": shop.created_at.isoformat(),
            "updated_at": shop.updated_at.isoformat()
        },
        message="Shop updated successfully"
    )


@router.delete("/{shop_id}")
def delete_shop(shop_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    db.delete(shop)
    db.commit()

    return success_response(message="Shop deleted successfully")

@router.get("/{shop_id}/cashiers")
def list_cashiers(
    shop_id: str,
    request: Request,
    page: int = 1,
    limit: int = 20,
    is_active: bool = None,
    search: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Cashier).join(User).filter(Cashier.shop_id == shop_id)

    if is_active is not None:
        query = query.filter(Cashier.is_active == is_active)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(or_(
            User.full_name.ilike(search_pattern),
            User.username.ilike(search_pattern),
            User.phone.ilike(search_pattern)
        ))

    total_items = query.count()
    cashiers = query.offset((page - 1) * limit).limit(limit).all()

    data = []
    for cashier in cashiers:
        today = datetime.utcnow().date()
        today_transactions = 0  # Placeholder: compute from transactions table
        today_commissions = 0.0  # Placeholder: compute sum of commissions

        data.append({
            "id": str(cashier.id),
            "shop_id": str(cashier.shop_id),
            "name": cashier.user.full_name,
            "phone": cashier.user.phone,
            "email": cashier.user.email,
            "username": cashier.user.username,
            "is_active": cashier.is_active,
            "created_at": cashier.created_at.isoformat(),
            "updated_at": cashier.updated_at.isoformat(),
            "shop": {
                "id": str(cashier.shop_id),
                "name": getattr(cashier.user, "shop_name", None)
            },
            "stats": {
                "today_transactions": today_transactions,
                "today_commissions": today_commissions
            }
        })

    return success_response(
        data=data,
        message="Cashiers retrieved successfully"
    )

@router.post("/shops/{shop_id}/cashiers")
async def create_cashier(shop_id: str, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    body = await request.json()
    name = body.get("name")
    phone = body.get("phone")
    email = body.get("email")
    username = body.get("username")
    password = body.get("password")

    if not all([name, phone, email, username, password]):
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

    if db.query(User).filter(or_(User.email == email, User.username == username, User.phone == phone)).first():
        return JSONResponse(
            status_code=400,
            content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Email, username, or phone already exists")
        )

    user = User(
        username=username,
        full_name=name,
        email=email,
        phone=phone,
        hashed_password=hash_password(password),
        role="cashier",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    cashier = Cashier(
        shop_id=shop_id,
        user_id=user.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(cashier)
    db.commit()
    db.refresh(cashier)

    return success_response(
        data={
            "id": str(cashier.id),
            "shop_id": shop_id,
            "name": name,
            "phone": phone,
            "email": email,
            "username": username,
            "is_active": cashier.is_active,
            "created_at": cashier.created_at.isoformat(),
            "updated_at": cashier.updated_at.isoformat()
        },
        message="Cashier created successfully"
    )
