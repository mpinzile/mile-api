# app/models/shop.py
import uuid
from datetime import datetime
from sqlalchemy import Column, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class Shop(Base):
    __tablename__ = "shops"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    location = Column(Text, nullable=False)
    owner_id = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
