# app/models/cash_balance.py
import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, Numeric
from sqlalchemy.dialects.postgresql import UUID
from db.base import Base


class CashBalance(Base):
    __tablename__ = "cash_balances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), unique=True, nullable=False)
    balance = Column(Numeric(15, 2), default=0, nullable=False)
    opening_balance = Column(Numeric(15, 2), default=0, nullable=False)
    last_updated = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
