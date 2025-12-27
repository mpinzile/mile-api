# app/db/get_db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core import config  

engine = create_engine(config.DATABASE_URL, echo=False, future=True)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
