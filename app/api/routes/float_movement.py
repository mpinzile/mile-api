from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from decimal import Decimal
from app.db.get_db import get_db
from app.models.float import FloatMovement
from app.models.user import User
from app.utils.auth import get_current_user
from app.utils.helpers import success_response, update_balances, verify_shop_access
from app.models.enums import FloatOperationType

router = APIRouter()


@router.put("/{movement_id}")
async def update_float_movement(movement_id: str, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    body = await request.json()
    movement = db.query(FloatMovement).filter(FloatMovement.id == movement_id).first()
    if not movement:
        raise HTTPException(status_code=404, detail="Float movement not found")

     # Verify access
    verify_shop_access(db, movement.shop_id, current_user)
    
    prev_amount = float(movement.amount)
    operation_type = movement.type
    is_new_capital = movement.is_new_capital

    # Reverse previous effect
    if operation_type == FloatOperationType.top_up:
        update_balances(db, movement.shop_id, movement.provider_id, movement.category, Decimal(prev_amount), "withdraw")
    else:
        update_balances(db, movement.shop_id, movement.provider_id, movement.category, Decimal(prev_amount), "top_up", is_new_capital)

    # Apply new values
    new_amount = Decimal(body.get("amount", movement.amount))
    movement.amount = new_amount
    movement.reference = body.get("reference", movement.reference)
    movement.notes = body.get("notes", movement.notes)
    movement.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(movement)

    # Apply new effect
    if operation_type == FloatOperationType.top_up:
        balances = update_balances(db, movement.shop_id, movement.provider_id, movement.category, new_amount, "top_up", is_new_capital)
    else:
        balances = update_balances(db, movement.shop_id, movement.provider_id, movement.category, new_amount, "withdraw")

    return success_response(
        data={
            "id": str(movement.id),
            "type": movement.type.value,
            "category": movement.category,
            "amount": float(movement.amount),
            "balance_updates": balances
        },
        message="Float movement updated successfully"
    )

@router.delete("/{movement_id}")
def delete_float_movement(movement_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    movement = db.query(FloatMovement).filter(FloatMovement.id == movement_id).first()
    if not movement:
        raise HTTPException(status_code=404, detail="Float movement not found")

    # Verify access
    verify_shop_access(db, movement.shop_id, current_user)
    
    prev_amount = float(movement.amount)
    operation_type = movement.type

    # Reverse effect before deletion
    if operation_type == FloatOperationType.top_up:
        update_balances(db, movement.shop_id, movement.provider_id, movement.category, Decimal(prev_amount), "withdraw")
    else:
        update_balances(db, movement.shop_id, movement.provider_id, movement.category, Decimal(prev_amount), "top_up")

    db.delete(movement)
    db.commit()

    return success_response(message="Float movement deleted successfully")
