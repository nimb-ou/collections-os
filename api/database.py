"""
Database connection management
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Generator
from .config import settings


@contextmanager
def get_db() -> Generator:
    """
    Database connection context manager.
    Yields a psycopg2 connection with RealDictCursor.
    """
    conn = None
    try:
        conn = psycopg2.connect(settings.database_url)
        conn.cursor_factory = RealDictCursor
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()


def get_db_dependency():
    """FastAPI dependency for database connection."""
    with get_db() as conn:
        yield conn
