# app/utils/validation_functions.py
import re
from models.enums import AppRole

def validate_email(email: str) -> bool:
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def validate_tanzanian_phone(phone: str) -> str:
    """
    Validates and formats a Tanzanian phone number into international format (without +).
    Accepts:
        - 0653750805
        - 653750805
        - 255653750805
        - +255653750805
    Returns formatted number like: 255653750805
    Raises ValueError if invalid.
    """
    phone = phone.strip().replace(" ", "").replace("-", "")

    # Remove leading +
    if phone.startswith("+"):
        phone = phone[1:]

    # Remove leading 0 if present in local format
    if phone.startswith("0") and len(phone) == 10:
        phone = phone[1:]

    # Add country code if missing
    if phone.startswith("6") or phone.startswith("7"):
        phone = "255" + phone

    # Must now match pattern: 255 + 9 digits starting with 6 or 7
    if re.fullmatch(r"255[67]\d{8}", phone):
        return phone

    raise ValueError(
        "Invalid Tanzanian phone number. Must start with 6 or 7 after country code "
        "and contain 9 digits after the country code"
    )


def validate_password_strength(password: str) -> bool:
    """
    Strong password rules:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """
    if len(password) < 8:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'\d', password):
        return False
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False
    return True

def validate_username(username: str) -> bool:
    """
    Valid usernames can only contain letters, numbers, and underscores.
    Must be between 3 and 30 characters.
    """
    if not 3 <= len(username) <= 30:
        return False
    pattern = r'^[A-Za-z0-9_]+$'
    return re.fullmatch(pattern, username) is not None

def validate_admin_role(role: str) -> bool:
    """
    Checks if the provided role exists in AdminRole enum.
    Returns True if valid, False otherwise.
    """
    return role in AppRole._value2member_map_