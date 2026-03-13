"""
database.py – Lightweight SQLite persistence layer using SQLModel.
"""

from sqlmodel import SQLModel, create_engine, Session

DATABASE_URL = "sqlite:///./educator.db"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


def init_db() -> None:
    """Create all tables defined in SQLModel metadata."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency that yields a database session."""
    with Session(engine) as session:
        yield session
