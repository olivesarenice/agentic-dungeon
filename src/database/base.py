"""
Database base configuration and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

# Base class for all database models
Base = declarative_base()


def init_database(db_path: str = "game.db") -> Session:
    """
    Initialize the database and return a session.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        SQLAlchemy session
    """
    # Create engine
    engine = create_engine(f"sqlite:///{db_path}", echo=False)

    # Create all tables
    Base.metadata.create_all(engine)

    # Create session factory
    SessionFactory = sessionmaker(bind=engine)

    # Return a new session
    return SessionFactory()


def get_session(db_path: str = "game.db") -> Session:
    """
    Get a database session (without creating tables).

    Args:
        db_path: Path to the SQLite database file

    Returns:
        SQLAlchemy session
    """
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SessionFactory = sessionmaker(bind=engine)
    return SessionFactory()
