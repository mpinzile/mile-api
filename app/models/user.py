# app/models/user.py
import uuid
from datetime import datetime
from sqlalchemy import Column, Text, DateTime, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID
from db.base import Base
from models.enums import AppRole


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(Text, unique=True, nullable=False)
    email = Column(Text, unique=True, nullable=False)
    phone = Column(Text)
    full_name = Column(Text, nullable=False)
    hashed_password = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    role = Column(Enum(AppRole, name="app_role"), nullable=False, default=AppRole.superadmin)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
