from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from datetime import datetime
from app.models.user_setting import UserSetting
from app.models.user import User
from db import get_db
from utils.auth import get_current_user
from utils.helpers import success_response

router = APIRouter()

@router.get("/settings")
def get_user_settings_endpoint(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    settings = db.query(UserSetting).filter(UserSetting.user_id == current_user.id).first()

    if not settings:
        settings = UserSetting(
            user_id=current_user.id,
            currency_name="Tanzanian Shilling",
            currency_code="TZS",
            theme="system",
            preferences={
                "date_format": "DD/MM/YYYY",
                "time_format": "24h",
                "timezone": "Africa/Dar_es_Salaam",
                "language": "en",
                "notifications_enabled": True,
                "email_notifications": True
            }
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return success_response(
        data={
            "user_id": str(settings.user_id),
            "currency_name": settings.currency_name,
            "currency_code": settings.currency_code,
            "theme": settings.theme,
            **settings.preferences,
            "created_at": settings.created_at.isoformat(),
            "updated_at": settings.updated_at.isoformat()
        }
    )


@router.put("/settings")
async def update_user_settings(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    body = await request.json()
    settings = db.query(UserSetting).filter(UserSetting.user_id == current_user.id).first()

    if not settings:
        settings = UserSetting(user_id=current_user.id)
        db.add(settings)

    # Update fields
    settings.currency_name = body.get("currency_name", settings.currency_name)
    settings.currency_code = body.get("currency_code", settings.currency_code)
    settings.theme = body.get("theme", settings.theme)

    # Update preferences JSON
    preferences = settings.preferences or {}
    preferences["date_format"] = body.get("date_format", preferences.get("date_format", "DD/MM/YYYY"))
    preferences["time_format"] = body.get("time_format", preferences.get("time_format", "24h"))
    preferences["timezone"] = body.get("timezone", preferences.get("timezone", "Africa/Dar_es_Salaam"))
    preferences["language"] = body.get("language", preferences.get("language", "en"))
    preferences["notifications_enabled"] = body.get("notifications_enabled", preferences.get("notifications_enabled", True))
    preferences["email_notifications"] = body.get("email_notifications", preferences.get("email_notifications", True))
    settings.preferences = preferences

    settings.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(settings)

    return success_response(
        data={
            "user_id": str(settings.user_id),
            "currency_name": settings.currency_name,
            "currency_code": settings.currency_code,
            "theme": settings.theme,
            **settings.preferences,
            "created_at": settings.created_at.isoformat(),
            "updated_at": settings.updated_at.isoformat()
        },
        message="User settings updated successfully"
    )
