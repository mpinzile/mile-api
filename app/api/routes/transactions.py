from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from decimal import Decimal
from app.db.get_db import get_db
from app.models.user import User
from app.models.shop import Shop
from app.models.provider import Provider
from app.models.transaction import Transaction, TransactionType
from app.models.cash_balance import CashBalance
from app.models.float import FloatBalance
from app.models.cashier import Cashier
from app.utils.auth import get_current_user
from app.utils.helpers import success_response, error_response
from app.utils.error_codes import ERROR_CODES
from app.core.config import WITHDRAWAL_TYPES

router = APIRouter()
@router.put("/{transaction_id}")
async def update_transaction(
    transaction_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    body = await request.json()
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Check if current user has access (owner or cashier of shop)
    cashier_shop_ids = db.query(Cashier.shop_id).filter(Cashier.user_id == current_user.id).subquery()
    shop = db.query(Shop).filter(
        Shop.id == transaction.shop_id,
        (Shop.owner_id == current_user.id) | (Shop.id.in_(cashier_shop_ids))
    ).first()
    if not shop:
        raise HTTPException(status_code=403, detail="You do not have access to update this transaction")

    # Fetch float & cash balances
    float_balance = db.query(FloatBalance).filter(
        FloatBalance.shop_id == transaction.shop_id,
        FloatBalance.provider_id == transaction.provider_id,
        FloatBalance.category == transaction.category
    ).first()

    cash_balance = db.query(CashBalance).filter(CashBalance.shop_id == transaction.shop_id).first()

    prev_float = float(float_balance.balance)
    prev_cash = float(cash_balance.balance)

    # Reverse previous transaction effect
    txn_type = transaction.type
    amount = transaction.amount

    if txn_type in WITHDRAWAL_TYPES:
        float_balance.balance -= amount
        cash_balance.balance += amount
    else:
        float_balance.balance += amount
        cash_balance.balance -= amount

    # Apply new values
    new_amount = Decimal(body.get("amount", transaction.amount))
    new_commission = Decimal(body.get("commission", transaction.commission))

    if txn_type in WITHDRAWAL_TYPES:
        float_balance.balance += new_amount
        cash_balance.balance -= new_amount
    else:
        float_balance.balance -= new_amount
        cash_balance.balance += new_amount

    # Update transaction fields
    transaction.amount = new_amount
    transaction.commission = new_commission
    transaction.reference = body.get("reference", transaction.reference)
    transaction.customer_identifier = body.get("customer_identifier", transaction.customer_identifier)
    transaction.notes = body.get("notes", transaction.notes)
    transaction.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(transaction)
    db.refresh(float_balance)
    db.refresh(cash_balance)

    return success_response(
        data={
            "id": str(transaction.id),
            "amount": float(transaction.amount),
            "commission": float(transaction.commission),
            "reference": transaction.reference,
            "customer_identifier": transaction.customer_identifier,
            "balance_updates": {
                "float_balance": {
                    "previous": prev_float,
                    "current": float(float_balance.balance),
                    "change": float(float_balance.balance - prev_float)
                },
                "cash_balance": {
                    "previous": prev_cash,
                    "current": float(cash_balance.balance),
                    "change": float(cash_balance.balance - prev_cash)
                }
            }
        },
        message="Transaction updated successfully"
    )

@router.delete("/{transaction_id}")
def delete_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Check access
    cashier_shop_ids = db.query(Cashier.shop_id).filter(Cashier.user_id == current_user.id).subquery()
    shop = db.query(Shop).filter(
        Shop.id == transaction.shop_id,
        (Shop.owner_id == current_user.id) | (Shop.id.in_(cashier_shop_ids))
    ).first()
    if not shop:
        raise HTTPException(status_code=403, detail="You do not have access to delete this transaction")

    # Reverse balances
    float_balance = db.query(FloatBalance).filter(
        FloatBalance.shop_id == transaction.shop_id,
        FloatBalance.provider_id == transaction.provider_id,
        FloatBalance.category == transaction.category
    ).first()

    cash_balance = db.query(CashBalance).filter(CashBalance.shop_id == transaction.shop_id).first()

    if transaction.type in WITHDRAWAL_TYPES:
        float_balance.balance -= transaction.amount
        cash_balance.balance += transaction.amount
    else:
        float_balance.balance += transaction.amount
        cash_balance.balance -= transaction.amount

    db.delete(transaction)
    db.commit()

    return success_response(message="Transaction deleted successfully")

@router.get("/types")
def get_transaction_types():
    # Define mapping
    types = {
        "mobile": [
            {"value": "deposit", "label": "Deposit", "affects_float": "decrement", "affects_cash": "increment"},
            {"value": "withdrawal", "label": "Withdrawal", "affects_float": "increment", "affects_cash": "decrement"},
            {"value": "airtime", "label": "Airtime", "affects_float": "decrement", "affects_cash": "increment"},
            {"value": "bundle", "label": "Bundle", "affects_float": "decrement", "affects_cash": "increment"},
            {"value": "electricity", "label": "Electricity", "affects_float": "decrement", "affects_cash": "increment"},
            {"value": "water", "label": "Water", "affects_float": "decrement", "affects_cash": "increment"},
            {"value": "tv", "label": "TV", "affects_float": "decrement", "affects_cash": "increment"},
            {"value": "other_utility", "label": "Other Utility", "affects_float": "decrement", "affects_cash": "increment"}
        ],
        "bank": [
            {"value": "bank_deposit", "label": "Bank Deposit", "affects_float": "decrement", "affects_cash": "increment"},
            {"value": "bank_withdrawal", "label": "Bank Withdrawal", "affects_float": "increment", "affects_cash": "decrement"},
            {"value": "bill_payment", "label": "Bill Payment", "affects_float": "decrement", "affects_cash": "increment"},
            {"value": "funds_transfer", "label": "Funds Transfer", "affects_float": "decrement", "affects_cash": "increment"},
            {"value": "account_to_wallet", "label": "Account to Wallet", "affects_float": "decrement", "affects_cash": "none"},
            {"value": "wallet_to_account", "label": "Wallet to Account", "affects_float": "increment", "affects_cash": "none"}
        ]
    }
    return success_response(data=types)
