# app/models/user_setting.py
import uuid
from datetime import datetime
from sqlalchemy import Column, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class UserSetting(Base):
    __tablename__ = "user_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), unique=True, nullable=False)
    currency_name = Column(Text, default="Tanzanian Shilling", nullable=False)
    currency_code = Column(Text, default="TZS", nullable=False)
    theme = Column(Text, default="system")
    preferences = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
