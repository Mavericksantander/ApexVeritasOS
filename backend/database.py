from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .core.config import settings
from .models import Base

DATABASE_URL = settings.DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(engine, future=True, expire_on_commit=False)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
