from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from datetime import datetime
from app.db.get_db import get_db
from app.models.cashier import Cashier
from app.models.user import User
from app.models.shop import Shop
from app.utils.helpers import hash_password, success_response, error_response
from app.utils.validation_functions import validate_email, validate_tanzanian_phone
from app.utils.auth import get_current_user
from app.utils.error_codes import ERROR_CODES

router = APIRouter()


@router.get("/{cashier_id}")
def get_cashier(cashier_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    cashier = db.query(Cashier).filter(Cashier.id == cashier_id).first()
    if not cashier:
        raise HTTPException(status_code=404, detail="Cashier not found")

    return success_response(
        data={
            "id": str(cashier.id),
            "shop_id": str(cashier.shop_id),
            "name": cashier.user.full_name,
            "phone": cashier.user.phone,
            "email": cashier.user.email,
            "username": cashier.user.username,
            "is_active": cashier.is_active,
            "created_at": cashier.created_at.isoformat(),
            "updated_at": cashier.updated_at.isoformat()
        }
    )

@router.put("/{cashier_id}")
async def update_cashier(
    cashier_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    body = await request.json()
    cashier = db.query(Cashier).filter(Cashier.id == cashier_id).first()
    if not cashier:
        raise HTTPException(status_code=404, detail="Cashier not found")

    if "name" in body:
        cashier.user.full_name = body["name"]

    if "email" in body:
        new_email = body["email"]
        if not validate_email(new_email):
            return JSONResponse(
                status_code=400,
                content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Invalid email format")
            )
        # Check if email already exists
        if db.query(User).filter(User.email == new_email, User.id != cashier.user_id).first():
            return JSONResponse(
                status_code=400,
                content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Email already exists")
            )
        cashier.user.email = new_email

    if "phone" in body:
        try:
            new_phone = validate_tanzanian_phone(body["phone"])
        except ValueError as e:
            return JSONResponse(
                status_code=400,
                content=error_response(ERROR_CODES["VALIDATION_ERROR"], str(e))
            )
        # Check if phone already exists
        if db.query(User).filter(User.phone == new_phone, User.id != cashier.user_id).first():
            return JSONResponse(
                status_code=400,
                content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Phone already exists")
            )
        cashier.user.phone = new_phone

    cashier.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(cashier)

    return success_response(message="Cashier updated successfully")

@router.post("/{cashier_id}/reset-password")
async def reset_cashier_password(cashier_id: str, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    body = await request.json()
    new_password = body.get("new_password")
    if not new_password:
        return JSONResponse(
            status_code=400,
            content=error_response(ERROR_CODES["VALIDATION_ERROR"], "New password is required")
        )

    cashier = db.query(Cashier).filter(Cashier.id == cashier_id).first()
    if not cashier:
        raise HTTPException(status_code=404, detail="Cashier not found")

    cashier.user.hashed_password = hash_password(new_password)
    cashier.updated_at = datetime.utcnow()
    db.commit()

    return success_response(message="Password reset successfully")


@router.post("/{cashier_id}/toggle-status")
def toggle_cashier_status(cashier_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    cashier = db.query(Cashier).filter(Cashier.id == cashier_id).first()
    if not cashier:
        raise HTTPException(status_code=404, detail="Cashier not found")

    cashier.is_active = not cashier.is_active
    cashier.updated_at = datetime.utcnow()
    db.commit()

    message = "Cashier activated successfully" if cashier.is_active else "Cashier deactivated successfully"
    return success_response(
        data={"id": str(cashier.id), "is_active": cashier.is_active},
        message=message
    )


@router.delete("/{cashier_id}")
def delete_cashier(cashier_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    cashier = db.query(Cashier).filter(Cashier.id == cashier_id).first()
    if not cashier:
        raise HTTPException(status_code=404, detail="Cashier not found")

    db.delete(cashier)
    db.commit()
    return success_response(message="Cashier deleted successfully")
