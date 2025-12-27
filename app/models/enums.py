# app/models/enums.py
import enum


class Category(enum.Enum):
    mobile = "mobile"
    bank = "bank"


class TransactionType(enum.Enum):
    deposit = "deposit"
    withdrawal = "withdrawal"
    airtime = "airtime"
    bundle = "bundle"
    electricity = "electricity"
    water = "water"
    tv = "tv"
    other_utility = "other_utility"
    bank_deposit = "bank_deposit"
    bank_withdrawal = "bank_withdrawal"
    bill_payment = "bill_payment"
    funds_transfer = "funds_transfer"
    account_to_wallet = "account_to_wallet"
    wallet_to_account = "wallet_to_account"


class FloatOperationType(enum.Enum):
    top_up = "top_up"
    withdraw = "withdraw"


class AppRole(enum.Enum):
    superadmin = "superadmin"
    cashier = "cashier"


class AuditAction(enum.Enum):
    create = "create"
    update = "update"
    delete = "delete"
    login = "login"
    logout = "logout"
    float_top_up = "float_top_up"
    float_withdraw = "float_withdraw"
    import_ = "import"
    export = "export"
    settings_change = "settings_change"
