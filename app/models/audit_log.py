# app/models/audit_log.py
import uuid
from datetime import datetime
from sqlalchemy import Column, Text, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.enums import AuditAction
from app.models.user import User


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    action = Column(Enum(AuditAction, name="audit_action"), nullable=False)
    entity_type = Column(Text)
    entity_id = Column(UUID(as_uuid=True))
    details = Column(JSON)
    ip_address = Column(INET)
    user_agent = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    user = relationship("User", backref="audit_logs")

