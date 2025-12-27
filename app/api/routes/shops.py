# app/api/routes/shops.py

from decimal import Decimal
from fastapi import APIRouter, Query, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import asc, desc, or_
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
from app.models.enums import Category
from app.models.provider import Provider
from app.models.cash_balance import CashBalance
from app.models.super_agent import SuperAgent

router = APIRouter()

# List all shops managed by current user
@router.get("/")
def list_shops(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Get shop IDs where user is a cashier
    cashier_shop_ids = db.query(Cashier.shop_id).filter(Cashier.user_id == current_user.id).subquery()

    # Query shops: either owned or where user is cashier
    query = db.query(Shop).filter(
        or_(
            Shop.owner_id == current_user.id,
            Shop.id.in_(cashier_shop_ids)
        )
    )

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(or_(
            Shop.name.ilike(search_pattern),
            Shop.location.ilike(search_pattern)
        ))

    if sort_by not in ["name", "location", "created_at"]:
        sort_by = "created_at"

    sort_column = getattr(Shop, sort_by)
    if sort_order.lower() == "asc":
        query = query.order_by(asc(sort_column))
    else:
        query = query.order_by(desc(sort_column))

    total_items = query.count()
    total_pages = (total_items + limit - 1) // limit

    shops = query.offset((page - 1) * limit).limit(limit).all()
    data = []

    for shop in shops:
        total_cashiers = db.query(Cashier).filter(Cashier.shop_id == shop.id).count()
        total_providers = db.query(Provider).filter(Provider.shop_id == shop.id).count()
        cash_balance_obj = db.query(CashBalance).filter(CashBalance.shop_id == shop.id).first()
        cash_balance = float(cash_balance_obj.balance) if cash_balance_obj else 0.0

        data.append({
            "id": str(shop.id),
            "name": shop.name,
            "location": shop.location,
            "owner_id": str(shop.owner_id) if shop.owner_id else None,
            "is_active": getattr(shop, "is_active", True),
            "created_at": shop.created_at.isoformat(),
            "updated_at": shop.updated_at.isoformat(),
            "stats": {
                "total_cashiers": total_cashiers,
                "total_providers": total_providers,
                "cash_balance": cash_balance
            }
        })

    return success_response(
        data=data,
        message="Shops retrieved successfully",
        pagination={
            "page": page,
            "limit": limit,
            "total_items": total_items,
            "total_pages": total_pages
        }
    )

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

@router.post("/{shop_id}/cashiers")
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

    # Check for duplicate email
    if db.query(User).filter(User.email == email).first():
        return JSONResponse(
            status_code=400,
            content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Email already registered")
        )

    # Check for duplicate username
    if db.query(User).filter(User.username == username).first():
        return JSONResponse(
            status_code=400,
            content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Username already exists")
        )

    # Check for duplicate phone
    if db.query(User).filter(User.phone == phone).first():
        return JSONResponse(
            status_code=400,
            content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Phone number already registered")
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

@router.post("/{shop_id}/providers")
async def create_provider(
    shop_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    body = await request.json()
    name = body.get("name")
    category = body.get("category")
    agent_code = body.get("agent_code")
    opening_balance = body.get("opening_balance", 0)

    if not all([name, category]):
        return JSONResponse(
            status_code=400,
            content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Name and category are required")
        )

    if category not in Category.__members__:
        return JSONResponse(
            status_code=400,
            content=error_response(ERROR_CODES["VALIDATION_ERROR"], f"Invalid category. Allowed: {list(Category.__members__.keys())}")
        )

    try:
        opening_balance = Decimal(opening_balance)
        if opening_balance < 0:
            raise ValueError
    except:
        return JSONResponse(
            status_code=400,
            content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Invalid opening_balance")
        )

    provider = Provider(
        shop_id=shop_id,
        name=name,
        category=Category[category],
        agent_code=agent_code,
        opening_balance=opening_balance,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)

    return success_response(
        data={
            "id": str(provider.id),
            "shop_id": provider.shop_id,
            "name": provider.name,
            "category": provider.category.value,
            "agent_code": provider.agent_code,
            "opening_balance": float(provider.opening_balance),
            "created_at": provider.created_at.isoformat(),
            "updated_at": provider.updated_at.isoformat()
        },
        message="Provider created successfully"
    )


@router.get("/{shop_id}/super-agents")
def list_super_agents(shop_id: str, db: Session = Depends(get_db)):
    agents = db.query(SuperAgent).filter(SuperAgent.shop_id == shop_id).all()
    data = [
        {
            "id": str(agent.id),
            "name": agent.name,
            "reference": agent.reference,
            "shop_id": str(agent.shop_id),
            "created_at": agent.created_at.isoformat(),
            "updated_at": agent.updated_at.isoformat()
        }
        for agent in agents
    ]
    return success_response(data=data)

@router.post("/{shop_id}/super-agents")
async def create_super_agent(shop_id: str, request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    name = body.get("name")
    reference = body.get("reference")

    if not all([name, reference]):
        return JSONResponse(
            status_code=400,
            content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Missing required fields: name, reference")
        )

    agent = SuperAgent(
        shop_id=shop_id,
        name=name,
        reference=reference,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    data = {
        "id": str(agent.id),
        "name": agent.name,
        "reference": agent.reference,
        "shop_id": str(agent.shop_id),
        "created_at": agent.created_at.isoformat(),
        "updated_at": agent.updated_at.isoformat()
    }
    return success_response(data=data, message="Super agent created successfully")