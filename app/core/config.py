# app/core/config.py

import os
from dotenv import load_dotenv
from app.models.enums import TransactionType

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
JWT_SECRET = os.getenv("JWT_SECRET")
DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"
MAX_FILE_SIZE = 0.5 * 1024 * 1024 
MAX_COOKIE_AGE = 60 * 60 * 24
APP_ENV = os.getenv("APP_ENV", "development")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 
REFRESH_TOKEN_EXPIRE_DAYS = 30
IS_PRODUCTION = APP_ENV == "production"
if APP_ENV == "production":
    COOKIE_DOMAIN = "mile.sewmrtechnologies.com"
else:
    COOKIE_DOMAIN = None 
WITHDRAWAL_TYPES = [TransactionType.withdrawal.value, TransactionType.bank_withdrawal.value]
RESET_PASSWORD_CODE_EXPIRE_MINUTES = 15