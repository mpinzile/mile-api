from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from datetime import datetime
import uuid

from db.get_db import get_db
from models.cashier import Cashier
from models.user import User
from models.shop import Shop
from utils.helpers import hash_password, success_response, error_response
from utils.validation_functions import validate_email, validate_tanzanian_phone
from utils.auth import get_current_user
from utils.error_codes import ERROR_CODES

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


@router.put("/{cashier_id}")
async def update_cashier(cashier_id: str, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    body = await request.json()
    cashier = db.query(Cashier).filter(Cashier.id == cashier_id).first()
    if not cashier:
        raise HTTPException(status_code=404, detail="Cashier not found")

    if "name" in body:
        cashier.user.full_name = body["name"]
    if "email" in body:
        if not validate_email(body["email"]):
            return JSONResponse(
                status_code=400,
                content=error_response(ERROR_CODES["VALIDATION_ERROR"], "Invalid email format")
            )
        cashier.user.email = body["email"]
    if "phone" in body:
        try:
            cashier.user.phone = validate_tanzanian_phone(body["phone"])
        except ValueError as e:
            return JSONResponse(
                status_code=400,
                content=error_response(ERROR_CODES["VALIDATION_ERROR"], str(e))
            )

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
