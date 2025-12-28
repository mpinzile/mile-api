from http.client import HTTPException
from fastapi import APIRouter, Request, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime
from decimal import Decimal
from app.db.get_db import get_db
from app.models.provider import Provider
from app.models.enums import Category, FloatOperationType
from app.utils.auth import get_current_user
from app.models.user import User
from app.utils.helpers import success_response, error_response, verify_shop_access
from app.utils.error_codes import ERROR_CODES
from app.models.float import FloatBalance, FloatMovement
from app.models.transaction import Transaction

router = APIRouter()

@router.put("/{provider_id}")
async def update_provider(
    provider_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    body = await request.json()
    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if not provider:
        return JSONResponse(
            status_code=404,
            content=error_response(ERROR_CODES["NOT_FOUND"], "Provider not found")
        )

    if "name" in body:
        provider.name = body["name"]
    if "agent_code" in body:
        provider.agent_code = body["agent_code"]

    provider.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(provider)

    return success_response(
        data={
            "id": str(provider.id),
            "name": provider.name,
            "agent_code": provider.agent_code,
            "updated_at": provider.updated_at.isoformat()
        },
        message="Provider updated successfully"
    )


@router.delete("/{provider_id}")
async def delete_provider(
    provider_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if not provider:
        return JSONResponse(
            status_code=404,
            content=error_response(ERROR_CODES["NOT_FOUND"], "Provider not found")
        )

    db.delete(provider)
    db.commit()
    return success_response(message="Provider deleted successfully")


@router.get("/{provider_id}/balance")
def get_provider_balance(provider_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    # Optional: verify current_user is owner or cashier of the provider's shop
    shop = verify_shop_access(db, provider.shop_id, current_user)

    # Get float balance
    float_balance = db.query(FloatBalance).filter_by(
        shop_id=provider.shop_id,
        provider_id=provider.id,
        category=provider.category
    ).first()

    balance = float(float_balance.balance) if float_balance else 0.0

    return success_response(
        data={
            "provider_id": str(provider.id),
            "provider_name": provider.name,
            "category": provider.category.value,
            "balance": balance,
            "opening_balance": float(provider.opening_balance),
            "last_updated": float_balance.last_updated.isoformat() if float_balance else None
        }
    )

@router.put("/{provider_id}/balance")
async def set_provider_opening_balance(provider_id: str, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    body = await request.json()
    new_opening_balance = Decimal(body.get("opening_balance", 0))

    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    # Optional: verify current_user is owner or cashier
    shop = verify_shop_access(db, provider.shop_id, current_user)

    provider.opening_balance = new_opening_balance
    provider.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(provider)

    return success_response(
        data={
            "provider_id": str(provider.id),
            "provider_name": provider.name,
            "category": provider.category.value,
            "opening_balance": float(provider.opening_balance),
            "updated_at": provider.updated_at.isoformat()
        },
        message="Provider opening balance updated successfully"
    )


# --- Get single provider ---
@router.get("/{provider_id}")
def get_provider(provider_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    # Verify user has access to provider's shop
    shop = verify_shop_access(db, provider.shop_id, current_user)

    float_balance = db.query(FloatBalance).filter_by(
        shop_id=provider.shop_id,
        provider_id=provider.id,
        category=provider.category
    ).first()

    # Provider stats
    txn_summary = db.query(
        func.count(Transaction.id),
        func.coalesce(func.sum(Transaction.amount), 0),
        func.coalesce(func.sum(Transaction.commission), 0)
    ).filter(Transaction.provider_id == provider.id).first()

    total_transactions, total_amount, total_commissions = txn_summary or (0, 0, 0)

    float_summary = db.query(
        func.count(FloatMovement.id).filter(FloatMovement.type == FloatOperationType.top_up),
        func.count(FloatMovement.id).filter(FloatMovement.type == FloatOperationType.withdraw)
    ).filter(FloatMovement.provider_id == provider.id).first() or (0, 0)

    total_float_top_ups, total_float_withdrawals = float_summary

    return success_response(
        data={
            "id": str(provider.id),
            "name": provider.name,
            "category": provider.category.value,
            "agent_code": provider.agent_code,
            "shop_id": str(provider.shop_id),
            "opening_balance": float(provider.opening_balance),
            "created_at": provider.created_at.isoformat(),
            "updated_at": provider.updated_at.isoformat(),
            "shop": {
                "id": str(shop.id),
                "name": shop.name
            },
            "float_balance": {
                "balance": float(float_balance.balance) if float_balance else 0.0,
                "last_updated": float_balance.last_updated.isoformat() if float_balance else None
            },
            "stats": {
                "total_transactions": total_transactions,
                "total_transaction_amount": float(total_amount),
                "total_commissions": float(total_commissions),
                "total_float_top_ups": total_float_top_ups,
                "total_float_withdrawals": total_float_withdrawals
            }
        }
    )