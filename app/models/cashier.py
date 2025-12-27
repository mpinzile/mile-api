import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.user import User


class Cashier(Base):
    __tablename__ = "cashiers"
    __table_args__ = (UniqueConstraint("user_id", "shop_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    shop_id = Column(UUID(as_uuid=True), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    user = relationship("User", backref="cashier_profiles")
