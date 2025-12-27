# app/models/float.py
import uuid
from datetime import datetime
from sqlalchemy import Column, Text, DateTime, Numeric, Boolean, Enum, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import Base
from models.enums import Category, FloatOperationType


class FloatMovement(Base):
    __tablename__ = "float_movements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("providers.id"), nullable=False)
    super_agent_id = Column(UUID(as_uuid=True), ForeignKey("super_agents.id"), nullable=False)
    recorded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    type = Column(Enum(FloatOperationType, name="float_operation_type"), nullable=False)
    category = Column(Enum(Category, name="category"), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    reference = Column(Text, nullable=False)
    is_new_capital = Column(Boolean, default=False, nullable=False)
    receipt_image_url = Column(Text)
    notes = Column(Text)
    transaction_date = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    shop = relationship("Shop", backref="float_movements")
    provider = relationship("Provider", backref="float_movements")
    super_agent = relationship("SuperAgent", backref="float_movements")
    recorder = relationship("User", backref="float_movements")


class FloatBalance(Base):
    __tablename__ = "float_balances"
    __table_args__ = (UniqueConstraint("shop_id", "provider_id", "category"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("providers.id"), nullable=False)
    category = Column(Enum(Category, name="category"), nullable=False)
    balance = Column(Numeric(15, 2), default=0, nullable=False)
    last_updated = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    shop = relationship("Shop", backref="float_balances")
    provider = relationship("Provider", backref="float_balances")
