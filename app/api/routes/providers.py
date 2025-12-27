from fastapi import APIRouter, Request, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
from decimal import Decimal
from app.db.get_db import get_db
from app.models.provider import Provider
from app.models.enums import Category
from app.utils.auth import get_current_user
from app.models.user import User
from app.utils.helpers import success_response, error_response
from app.utils.error_codes import ERROR_CODES

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
