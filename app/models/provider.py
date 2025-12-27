# app/models/provider.py
import uuid
from datetime import datetime
from sqlalchemy import Column, Text, DateTime, Numeric, Enum
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
from app.models.enums import Category


class Provider(Base):
    __tablename__ = "providers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), nullable=False)
    name = Column(Text, nullable=False)
    category = Column(Enum(Category, name="category"), nullable=False)
    agent_code = Column(Text)
    opening_balance = Column(Numeric(15, 2), default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
