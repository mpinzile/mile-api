# app/models/transaction.py
import uuid
from datetime import datetime
from sqlalchemy import Column, Text, DateTime, Numeric, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.enums import Category, TransactionType


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("providers.id"), nullable=False)
    recorded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    category = Column(Enum(Category, name="category"), nullable=False)
    type = Column(Enum(TransactionType, name="transaction_type"), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    commission = Column(Numeric(15, 2), default=0, nullable=False)
    reference = Column(Text, nullable=False)
    customer_identifier = Column(Text, nullable=False)
    receipt_image_url = Column(Text)
    notes = Column(Text)
    transaction_date = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    shop = relationship("Shop", backref="transactions")
    provider = relationship("Provider", backref="transactions")
    recorder = relationship("User", backref="transactions")
