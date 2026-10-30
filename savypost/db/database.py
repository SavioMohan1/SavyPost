"""Database initialization and session context for SavyPost."""

from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from savypost.config import DB_PATH
from savypost.db.models import Base

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create tables if they do not exist."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db():
    """Provide a transactional database session."""
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
