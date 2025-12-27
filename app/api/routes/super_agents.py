from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.get_db import get_db
from app.models.super_agent import SuperAgent
from app.utils.auth import get_current_user
from app.utils.helpers import success_response, error_response
from app.utils.error_codes import ERROR_CODES

router = APIRouter()

@router.get("/{super_agent_id}")
def get_super_agent(super_agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(SuperAgent).filter(SuperAgent.id == super_agent_id).first()
    if not agent:
        return JSONResponse(
            status_code=404,
            content=error_response(ERROR_CODES["NOT_FOUND"], "Super agent not found")
        )

    data = {
        "id": str(agent.id),
        "name": agent.name,
        "reference": agent.reference,
        "shop_id": str(agent.shop_id),
        "created_at": agent.created_at.isoformat(),
        "updated_at": agent.updated_at.isoformat()
    }
    return success_response(data=data)


@router.put("/{super_agent_id}")
async def update_super_agent(super_agent_id: str, request: Request, db: Session = Depends(get_db)):
    agent = db.query(SuperAgent).filter(SuperAgent.id == super_agent_id).first()
    if not agent:
        return JSONResponse(
            status_code=404,
            content=error_response(ERROR_CODES["NOT_FOUND"], "Super agent not found")
        )

    body = await request.json()
    if "name" in body:
        agent.name = body["name"]
    if "reference" in body:
        agent.reference = body["reference"]

    agent.updated_at = datetime.utcnow()
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
    return success_response(data=data, message="Super agent updated successfully")


@router.delete("/{super_agent_id}")
def delete_super_agent(super_agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(SuperAgent).filter(SuperAgent.id == super_agent_id).first()
    if not agent:
        return JSONResponse(
            status_code=404,
            content=error_response(ERROR_CODES["NOT_FOUND"], "Super agent not found")
        )

    db.delete(agent)
    db.commit()
    return success_response(message="Super agent deleted successfully")
