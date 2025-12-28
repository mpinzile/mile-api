# app/api/routes/shops.py

from decimal import Decimal
from fastapi import APIRouter, Query, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import asc, desc, func, or_
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from app.db.get_db import get_db
from app.models.cashier import Cashier
from app.models.shop import Shop
from app.models.user import User
from app.utils.helpers import hash_password, success_response, error_response, update_balances, verify_shop_access
from app.utils.auth import get_current_user
from app.utils.error_codes import ERROR_CODES
from app.utils.validation_functions import validate_email, validate_tanzanian_phone
from app.models.enums import Category, FloatOperationType
from app.models.provider import Provider
from app.models.cash_balance import CashBalance
from app.models.super_agent import SuperAgent
from app.models.transaction import Transaction
from app.models.float import FloatBalance, FloatMovement
from app.core.config import WITHDRAWAL_TYPES

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
    cashier_shop_ids = db.query(Cashier.shop_id).filter(Cashier.user_id == current_user.id).subquery()

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

@router.get("/{shop_id}")
def get_single_shop(
    shop_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Permission check: owner OR cashier
    cashier_shop_ids = (
        db.query(Cashier.shop_id)
        .filter(Cashier.user_id == current_user.id)
        .subquery()
    )

    shop = (
        db.query(Shop)
        .filter(
            Shop.id == shop_id,
            or_(
                Shop.owner_id == current_user.id,
                Shop.id.in_(cashier_shop_ids)
            )
        )
        .first()
    )

    if not shop:
        raise HTTPException(status_code=403, detail="You do not have access to this shop")

    # 👤 Owner info
    owner = db.query(User).filter(User.id == shop.owner_id).first()

    # Stats
    total_cashiers = db.query(Cashier).filter(Cashier.shop_id == shop.id).count()
    active_cashiers = db.query(Cashier).filter(
        Cashier.shop_id == shop.id,
        Cashier.is_active == True
    ).count()

    total_providers = db.query(Provider).filter(Provider.shop_id == shop.id).count()
    total_super_agents = db.query(SuperAgent).filter(SuperAgent.shop_id == shop.id).count()

    cash_balance_obj = db.query(CashBalance).filter(CashBalance.shop_id == shop.id).first()
    cash_balance = float(cash_balance_obj.balance) if cash_balance_obj else 0.0

    total_float_balance = (
        db.query(func.coalesce(func.sum(FloatBalance.balance), 0))
        .filter(FloatBalance.shop_id == shop.id)
        .scalar()
    )

    # Today stats
    today = date.today()

    today_transactions = (
        db.query(Transaction)
        .filter(
            Transaction.shop_id == shop.id,
            func.date(Transaction.transaction_date) == today
        )
        .count()
    )

    today_commissions = (
        db.query(func.coalesce(func.sum(Transaction.commission), 0))
        .filter(
            Transaction.shop_id == shop.id,
            func.date(Transaction.transaction_date) == today
        )
        .scalar()
    )

    return success_response(
        data={
            "id": str(shop.id),
            "name": shop.name,
            "location": shop.location,
            "owner_id": str(shop.owner_id),
            "is_active": getattr(shop, "is_active", True),
            "created_at": shop.created_at.isoformat(),
            "updated_at": shop.updated_at.isoformat(),
            "owner": {
                "id": str(owner.id),
                "full_name": owner.full_name,
                "email": owner.email
            } if owner else None,
            "stats": {
                "total_cashiers": total_cashiers,
                "active_cashiers": active_cashiers,
                "total_providers": total_providers,
                "total_super_agents": total_super_agents,
                "cash_balance": cash_balance,
                "total_float_balance": float(total_float_balance),
                "today_transactions": today_transactions,
                "today_commissions": float(today_commissions)
            }
        },
        message="Shop retrieved successfully"
    )

@router.get("/{shop_id}/stats")
def get_shop_stats(
    shop_id: str,
    start_date: str = Query(None, description="YYYY-MM-DD"),
    end_date: str = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Permission check
    cashier_shop_ids = (
        db.query(Cashier.shop_id)
        .filter(Cashier.user_id == current_user.id)
        .subquery()
    )

    shop = (
        db.query(Shop)
        .filter(
            Shop.id == shop_id,
            or_(
                Shop.owner_id == current_user.id,
                Shop.id.in_(cashier_shop_ids)
            )
        )
        .first()
    )

    if not shop:
        raise HTTPException(status_code=403, detail="You do not have access to this shop")

    # Date range
    tx_filters = [Transaction.shop_id == shop_id]
    float_filters = [FloatMovement.shop_id == shop_id]

    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        tx_filters.append(Transaction.transaction_date >= start)
        float_filters.append(FloatMovement.transaction_date >= start)

    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d")
        tx_filters.append(Transaction.transaction_date <= end)
        float_filters.append(FloatMovement.transaction_date <= end)

    # Transactions
    total_transactions = db.query(Transaction).filter(*tx_filters).count()

    total_transaction_amount = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(*tx_filters)
        .scalar()
    )

    total_commissions = (
        db.query(func.coalesce(func.sum(Transaction.commission), 0))
        .filter(*tx_filters)
        .scalar()
    )

    # Float movements
    total_float_movements = db.query(FloatMovement).filter(*float_filters).count()

    total_float_amount = (
        db.query(func.coalesce(func.sum(FloatMovement.amount), 0))
        .filter(*float_filters)
        .scalar()
    )

    # Cash balance
    cash_balance_obj = db.query(CashBalance).filter(CashBalance.shop_id == shop_id).first()
    cash_balance = float(cash_balance_obj.balance) if cash_balance_obj else 0.0

    # Float balances by category
    float_balances = (
        db.query(
            FloatBalance.category,
            func.coalesce(func.sum(FloatBalance.balance), 0)
        )
        .filter(FloatBalance.shop_id == shop_id)
        .group_by(FloatBalance.category)
        .all()
    )

    float_balance_map = {
        fb.category.value: float(fb[1])
        for fb in float_balances
    }

    # Commission by category
    commission_by_category = (
        db.query(
            Transaction.category,
            func.coalesce(func.sum(Transaction.commission), 0)
        )
        .filter(*tx_filters)
        .group_by(Transaction.category)
        .all()
    )

    commission_category_map = {
        row.category.value: float(row[1])
        for row in commission_by_category
    }

    # Transactions by type
    transaction_by_type = (
        db.query(
            Transaction.type,
            func.count(Transaction.id)
        )
        .filter(*tx_filters)
        .group_by(Transaction.type)
        .all()
    )

    transaction_type_map = {
        row.type.value: row[1]
        for row in transaction_by_type
    }

    return success_response(
        data={
            "total_transactions": total_transactions,
            "total_transaction_amount": float(total_transaction_amount),
            "total_commissions": float(total_commissions),
            "total_float_movements": total_float_movements,
            "total_float_amount": float(total_float_amount),
            "cash_balance": cash_balance,
            "float_balances": float_balance_map,
            "commission_by_category": commission_category_map,
            "transaction_by_type": transaction_type_map
        },
        message="Shop statistics retrieved successfully"
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
def list_super_agents(
    shop_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if user owns the shop or is a cashier
    cashier_shop_ids = db.query(Cashier.shop_id).filter(Cashier.user_id == current_user.id).subquery()
    shop = db.query(Shop).filter(
        Shop.id == shop_id,
        or_(
            Shop.owner_id == current_user.id,
            Shop.id.in_(cashier_shop_ids)
        )
    ).first()

    if not shop:
        raise HTTPException(status_code=403, detail="You do not have access to this shop")

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
    return success_response(data=data, message="Super agents retrieved successfully")

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


@router.post("/{shop_id}/transactions")
async def create_transaction(
    shop_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    body = await request.json()
    required_fields = ["category", "type", "provider_id", "amount", "reference", "customer_identifier", "transaction_date"]
    if not all(f in body for f in required_fields):
        return error_response(ERROR_CODES["VALIDATION_ERROR"], "Missing required fields")

    # Validate shop access (owner or cashier)
    cashier_shop_ids = db.query(Cashier.shop_id).filter(Cashier.user_id == current_user.id).subquery()
    shop = db.query(Shop).filter(
        Shop.id == shop_id,
        Shop.id.in_(cashier_shop_ids) | (Shop.owner_id == current_user.id)
    ).first()
    if not shop:
        raise HTTPException(status_code=403, detail="You do not have access to this shop")

    # Fetch provider
    provider = db.query(Provider).filter(Provider.id == body["provider_id"], Provider.shop_id == shop_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found in this shop")

    # Convert amount and commission
    amount = Decimal(body["amount"])
    commission = Decimal(body.get("commission", 0))

    # Fetch or create FloatBalance for this provider and category
    float_balance_obj = db.query(FloatBalance).filter(
        FloatBalance.shop_id == shop_id,
        FloatBalance.provider_id == provider.id,
        FloatBalance.category == body["category"]
    ).first()

    if not float_balance_obj:
        float_balance_obj = FloatBalance(
            shop_id=shop_id,
            provider_id=provider.id,
            category=body["category"],
            balance=0,
            last_updated=datetime.utcnow()
        )
        db.add(float_balance_obj)
        db.commit()
        db.refresh(float_balance_obj)

    prev_float = float(float_balance_obj.balance)

    # Fetch or create CashBalance for the shop
    cash_balance_obj = db.query(CashBalance).filter(CashBalance.shop_id == shop_id).first()
    if not cash_balance_obj:
        cash_balance_obj = CashBalance(shop_id=shop_id, balance=0)
        db.add(cash_balance_obj)
        db.commit()
        db.refresh(cash_balance_obj)

    prev_cash = float(cash_balance_obj.balance)

    txn_type = body["type"]

    # Logic: withdrawal -> add to provider, deduct from cash; else deduct provider, add cash
    if txn_type in WITHDRAWAL_TYPES:
        float_balance_obj.balance += amount
        cash_balance_obj.balance -= amount
    else:
        float_balance_obj.balance -= amount
        cash_balance_obj.balance += amount

    float_balance_obj.last_updated = datetime.utcnow()
    cash_balance_obj.updated_at = datetime.utcnow()

    # Record transaction
    transaction = Transaction(
        shop_id=shop_id,
        provider_id=provider.id,
        recorded_by=current_user.id,
        category=body["category"],
        type=txn_type,
        amount=amount,
        commission=commission,
        reference=body["reference"],
        customer_identifier=body["customer_identifier"],
        receipt_image_url=body.get("receipt_image"),
        notes=body.get("notes"),
        transaction_date=datetime.fromisoformat(body["transaction_date"])
    )

    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    db.refresh(float_balance_obj)
    db.refresh(cash_balance_obj)

    return success_response(
        data={
            "id": str(transaction.id),
            "category": transaction.category,
            "type": transaction.type,
            "amount": float(transaction.amount),
            "commission": float(transaction.commission),
            "reference": transaction.reference,
            "customer_identifier": transaction.customer_identifier,
            "shop_id": shop_id,
            "provider_id": provider.id,
            "recorded_by": current_user.id,
            "transaction_date": transaction.transaction_date.isoformat(),
            "created_at": transaction.created_at.isoformat(),
            "balance_updates": {
                "float_balance": {
                    "previous": prev_float,
                    "current": float(float_balance_obj.balance),
                    "change": float(float_balance_obj.balance - prev_float)
                },
                "cash_balance": {
                    "previous": prev_cash,
                    "current": float(cash_balance_obj.balance),
                    "change": float(cash_balance_obj.balance - prev_cash)
                }
            }
        },
        message="Transaction recorded successfully"
    )

@router.get("/{shop_id}/transactions")
def list_transactions(
    shop_id: str,
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: str = Query(None),
    type: str = Query(None),
    provider_id: str = Query(None),
    recorded_by: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    min_amount: float = Query(None),
    max_amount: float = Query(None),
    search: str = Query(None),
    sort_by: str = Query("transaction_date"),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check user access: owner or cashier
    cashier_shop_ids = db.query(Cashier.shop_id).filter(Cashier.user_id == current_user.id).subquery()
    shop = db.query(Shop).filter(
        Shop.id == shop_id,
        or_(Shop.owner_id == current_user.id, Shop.id.in_(cashier_shop_ids))
    ).first()
    if not shop:
        raise HTTPException(status_code=403, detail="You do not have access to this shop")

    query = db.query(Transaction).filter(Transaction.shop_id == shop_id)

    if category:
        query = query.filter(Transaction.category == category)
    if type:
        query = query.filter(Transaction.type == type)
    if provider_id:
        query = query.filter(Transaction.provider_id == provider_id)
    if recorded_by:
        query = query.filter(Transaction.recorded_by == recorded_by)
    if start_date:
        query = query.filter(Transaction.transaction_date >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(Transaction.transaction_date <= datetime.fromisoformat(end_date))
    if min_amount:
        query = query.filter(Transaction.amount >= Decimal(min_amount))
    if max_amount:
        query = query.filter(Transaction.amount <= Decimal(max_amount))
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(
            Transaction.reference.ilike(pattern),
            Transaction.customer_identifier.ilike(pattern)
        ))

    if sort_by not in ["transaction_date", "amount", "created_at"]:
        sort_by = "transaction_date"
    sort_column = getattr(Transaction, sort_by)
    query = query.order_by(asc(sort_column) if sort_order.lower() == "asc" else desc(sort_column))

    total_items = query.count()
    total_pages = (total_items + limit - 1) // limit
    transactions = query.offset((page - 1) * limit).limit(limit).all()

    data = []
    total_amount = Decimal(0)
    total_commission = Decimal(0)

    for txn in transactions:
        provider = db.query(Provider).filter(Provider.id == txn.provider_id).first()
        user = db.query(User).filter(User.id == txn.recorded_by).first()
        total_amount += txn.amount
        total_commission += txn.commission

        data.append({
            "id": str(txn.id),
            "category": txn.category,
            "type": txn.type,
            "amount": float(txn.amount),
            "commission": float(txn.commission),
            "reference": txn.reference,
            "customer_identifier": txn.customer_identifier,
            "receipt_image": getattr(txn, "receipt_image_url", None),
            "notes": txn.notes,
            "shop_id": str(txn.shop_id),
            "provider_id": str(txn.provider_id),
            "recorded_by": str(txn.recorded_by) if txn.recorded_by else None,
            "transaction_date": txn.transaction_date.isoformat(),
            "created_at": txn.created_at.isoformat(),
            "updated_at": txn.updated_at.isoformat(),
            "provider": {
                "id": str(provider.id),
                "name": provider.name,
                "category": provider.category.value
            } if provider else None,
            "recorded_by_user": {
                "id": str(user.id),
                "full_name": user.full_name
            } if user else None
        })

    return success_response(
        data=data,
        pagination={
            "page": page,
            "limit": limit,
            "total_items": total_items,
            "total_pages": total_pages
        },
        summary={
            "total_amount": float(total_amount),
            "total_commission": float(total_commission),
            "transaction_count": total_items
        }
    )

@router.post("/{shop_id}/float-movements/top-up")
async def create_float_topup(shop_id: str, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    body = await request.json()

    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    verify_shop_access(db, shop_id, current_user)

    movement = FloatMovement(
        shop_id=shop_id,
        provider_id=body["provider_id"],
        super_agent_id=body["super_agent_id"],
        recorded_by=current_user.id,
        type=FloatOperationType.top_up,
        category=body["category"],
        amount=Decimal(body["amount"]),
        reference=body["reference"],
        is_new_capital=body.get("is_new_capital", False),
        receipt_image_url=body.get("receipt_image"),
        notes=body.get("notes"),
        transaction_date=datetime.fromisoformat(body["transaction_date"])
    )

    db.add(movement)
    db.commit()
    db.refresh(movement)

    balances = update_balances(db, shop_id, body["provider_id"], body["category"], Decimal(body["amount"]), "top_up", movement.is_new_capital)

    return success_response(
        data={
            "id": str(movement.id),
            "type": "top_up",
            "category": movement.category,
            "amount": float(movement.amount),
            "is_new_capital": movement.is_new_capital,
            "balance_updates": balances
        },
        message="Float top-up recorded successfully"
    )

@router.post("/{shop_id}/float-movements/withdraw")
async def create_float_withdraw(shop_id: str, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    body = await request.json()

    # Just verify access, no need to assign
    verify_shop_access(db, shop_id, current_user)


    movement = FloatMovement(
        shop_id=shop_id,
        provider_id=body["provider_id"],
        super_agent_id=body["super_agent_id"],
        recorded_by=current_user.id,
        type=FloatOperationType.withdraw,
        category=body["category"],
        amount=Decimal(body["amount"]),
        reference=body["reference"],
        receipt_image_url=body.get("receipt_image"),
        notes=body.get("notes"),
        transaction_date=datetime.fromisoformat(body["transaction_date"])
    )

    db.add(movement)
    db.commit()
    db.refresh(movement)

    balances = update_balances(db, shop_id, body["provider_id"], body["category"], Decimal(body["amount"]), "withdraw")

    return success_response(
        data={
            "id": str(movement.id),
            "type": "withdraw",
            "category": movement.category,
            "amount": float(movement.amount),
            "balance_updates": balances
        },
        message="Float withdrawal recorded successfully"
    )

@router.get("/{shop_id}/balances")
def get_shop_balances(
    shop_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_shop_access(db, shop_id, current_user)

    cash = db.query(CashBalance).filter(CashBalance.shop_id == shop_id).first()
    if not cash:
        cash = CashBalance(shop_id=shop_id)
        db.add(cash)
        db.commit()
        db.refresh(cash)

    float_rows = (
        db.query(FloatBalance, Provider)
        .join(Provider, Provider.id == FloatBalance.provider_id)
        .filter(FloatBalance.shop_id == shop_id)
        .all()
    )

    float_data = []
    total_mobile = 0
    total_bank = 0

    for fb, provider in float_rows:
        balance = float(fb.balance)
        if provider.category.value == "mobile":
            total_mobile += balance
        else:
            total_bank += balance

        float_data.append({
            "provider_id": str(provider.id),
            "provider_name": provider.name,
            "category": provider.category.value,
            "balance": balance,
            "opening_balance": float(provider.opening_balance),
            "last_updated": fb.last_updated.isoformat()
        })

    total_float = total_mobile + total_bank
    total_cash = float(cash.balance)

    return success_response(
        data={
            "cash_balance": {
                "balance": total_cash,
                "opening_balance": float(cash.opening_balance),
                "last_updated": cash.last_updated.isoformat()
            },
            "float_balances": float_data,
            "totals": {
                "total_cash": total_cash,
                "total_mobile_float": total_mobile,
                "total_bank_float": total_bank,
                "total_float": total_float,
                "grand_total": total_cash + total_float
            }
        }
    )


@router.get("/{shop_id}/balances/cash")
def get_cash_balance(
    shop_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_shop_access(db, shop_id, current_user)

    cash = db.query(CashBalance).filter(CashBalance.shop_id == shop_id).first()
    if not cash:
        cash = CashBalance(shop_id=shop_id)
        db.add(cash)
        db.commit()
        db.refresh(cash)

    return success_response(
        data={
            "balance": float(cash.balance),
            "opening_balance": float(cash.opening_balance),
            "last_updated": cash.last_updated.isoformat()
        }
    )

@router.put("/{shop_id}/balances/cash")
async def set_cash_opening_balance(
    shop_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_shop_access(db, shop_id, current_user)

    body = await request.json()
    try:
        opening_balance = Decimal(body["opening_balance"])
    except:
        raise HTTPException(status_code=400, detail="Invalid opening_balance")

    cash = db.query(CashBalance).filter(CashBalance.shop_id == shop_id).first()
    if not cash:
        cash = CashBalance(shop_id=shop_id)

    cash.opening_balance = opening_balance
    cash.balance = opening_balance
    cash.last_updated = datetime.utcnow()

    db.add(cash)
    db.commit()
    db.refresh(cash)

    return success_response(
        data={
            "balance": float(cash.balance),
            "opening_balance": float(cash.opening_balance),
            "last_updated": cash.last_updated.isoformat()
        },
        message="Cash opening balance set successfully"
    )

@router.post("/{shop_id}/balances/cash/adjust")
async def adjust_cash_balance(
    shop_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_shop_access(db, shop_id, current_user)

    body = await request.json()

    try:
        amount = Decimal(body["amount"])
        if amount <= 0:
            raise ValueError
    except:
        raise HTTPException(status_code=400, detail="Invalid amount")

    adjustment_type = body.get("adjustment_type")
    if adjustment_type not in ["add", "subtract"]:
        raise HTTPException(status_code=400, detail="Invalid adjustment_type")

    cash = db.query(CashBalance).filter(CashBalance.shop_id == shop_id).first()
    if not cash:
        cash = CashBalance(shop_id=shop_id)
        db.add(cash)

    previous = float(cash.balance)

    if adjustment_type == "add":
        cash.balance += amount
    else:
        cash.balance -= amount

    cash.last_updated = datetime.utcnow()

    db.commit()
    db.refresh(cash)

    return success_response(
        data={
            "previous_balance": previous,
            "current_balance": float(cash.balance),
            "change": float(cash.balance - previous),
            "reason": body.get("reason")
        },
        message="Cash balance adjusted successfully"
    )

@router.get("/{shop_id}/dashboard")
def get_dashboard(
    shop_id: str,
    period: str = Query("today", regex="^(today|week|month)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check shop exists
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    # Determine period range
    now = datetime.utcnow()
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start = now - timedelta(days=now.weekday())  # start of week
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = now

    # --- Balances ---
    cash_balance_obj = db.query(CashBalance).filter(CashBalance.shop_id == shop_id).first()
    cash_balance = float(cash_balance_obj.balance) if cash_balance_obj else 0.0

    float_balances = db.query(FloatBalance).filter(FloatBalance.shop_id == shop_id).all()
    mobile_float = sum([float(f.balance) for f in float_balances if f.category.value == "mobile"])
    bank_float = sum([float(f.balance) for f in float_balances if f.category.value == "bank"])
    total_balance = cash_balance + mobile_float + bank_float

    # --- Today/period summary ---
    txn_summary = db.query(
        func.count(Transaction.id),
        func.coalesce(func.sum(Transaction.amount), 0),
        func.coalesce(func.sum(Transaction.commission), 0)
    ).filter(
        Transaction.shop_id == shop_id,
        Transaction.transaction_date >= start,
        Transaction.transaction_date <= end
    ).first()
    transactions_count, transaction_amount, commissions = txn_summary

    # Float top-ups and withdrawals
    float_summary = db.query(
        func.coalesce(func.sum(FloatMovement.amount), 0),
        func.coalesce(func.sum(FloatMovement.amount), 0)
    ).filter(
        FloatMovement.shop_id == shop_id,
        FloatMovement.transaction_date >= start,
        FloatMovement.transaction_date <= end
    ).all()

    float_top_ups = db.query(func.coalesce(func.sum(FloatMovement.amount), 0)).filter(
        FloatMovement.shop_id == shop_id,
        FloatMovement.type == FloatMovement.type.top_up,
        FloatMovement.transaction_date >= start,
        FloatMovement.transaction_date <= end
    ).scalar() or 0

    float_withdrawals = db.query(func.coalesce(func.sum(FloatMovement.amount), 0)).filter(
        FloatMovement.shop_id == shop_id,
        FloatMovement.type == FloatMovement.type.withdraw,
        FloatMovement.transaction_date >= start,
        FloatMovement.transaction_date <= end
    ).scalar() or 0

    # --- Growth: previous period same length ---
    period_length = end - start
    prev_start = start - period_length
    prev_end = start

    prev_summary = db.query(
        func.count(Transaction.id),
        func.coalesce(func.sum(Transaction.amount), 0),
        func.coalesce(func.sum(Transaction.commission), 0)
    ).filter(
        Transaction.shop_id == shop_id,
        Transaction.transaction_date >= prev_start,
        Transaction.transaction_date <= prev_end
    ).first()
    prev_count, _, prev_commission = prev_summary

    def calc_percentage(current, previous):
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 2)

    # --- Recent transactions ---
    recent_transactions = db.query(Transaction).filter(
        Transaction.shop_id == shop_id
    ).order_by(desc(Transaction.created_at)).limit(5).all()

    recent_txns_list = [
        {
            "id": str(txn.id),
            "type": txn.type.value,
            "amount": float(txn.amount),
            "customer_identifier": txn.customer_identifier,
            "created_at": txn.created_at.isoformat()
        }
        for txn in recent_transactions
    ]

    # --- Top providers by transaction count ---
    top_providers = db.query(
        Transaction.provider_id,
        Provider.name,
        func.count(Transaction.id).label("transaction_count"),
        func.coalesce(func.sum(Transaction.commission), 0).label("commission")
    ).join(Provider, Transaction.provider_id == Provider.id
    ).filter(Transaction.shop_id == shop_id
    ).group_by(Transaction.provider_id, Provider.name
    ).order_by(desc("transaction_count")).limit(5).all()

    top_providers_list = [
        {
            "provider_id": str(tp.provider_id),
            "provider_name": tp.name,
            "transaction_count": tp.transaction_count,
            "commission": float(tp.commission)
        }
        for tp in top_providers
    ]

    return success_response(
        data={
            "balances": {
                "cash": cash_balance,
                "mobile_float": mobile_float,
                "bank_float": bank_float,
                "total": total_balance
            },
            "today": {
                "transactions": transactions_count,
                "transaction_amount": float(transaction_amount),
                "commissions": float(commissions),
                "float_top_ups": float(float_top_ups),
                "float_withdrawals": float(float_withdrawals)
            },
            "growth": {
                "transactions": {
                    "current": transactions_count,
                    "previous": prev_count,
                    "percentage": calc_percentage(transactions_count, prev_count)
                },
                "commissions": {
                    "current": float(commissions),
                    "previous": float(prev_commission),
                    "percentage": calc_percentage(float(commissions), float(prev_commission))
                }
            },
            "recent_transactions": recent_txns_list,
            "top_providers": top_providers_list
        }
    )