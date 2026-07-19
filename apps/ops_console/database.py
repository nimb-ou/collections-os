"""
Database connection utilities for Ops Console
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Generator, Dict, Any, List, Optional
import streamlit as st

from config import DATABASE_URL


@contextmanager
def get_db() -> Generator:
    """
    Database connection context manager.

    Yields:
        Connection with RealDictCursor
    """
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
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


@st.cache_data(ttl=60)
def execute_query(query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
    """
    Execute a SELECT query and return results as list of dicts.
    Cached for 60 seconds to improve performance.

    Args:
        query: SQL query string
        params: Query parameters tuple

    Returns:
        List of row dictionaries
    """
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(query, params or ())
        return cur.fetchall()


def execute_mutation(query: str, params: Optional[tuple] = None) -> int:
    """
    Execute an INSERT/UPDATE/DELETE query.

    Args:
        query: SQL query string
        params: Query parameters tuple

    Returns:
        Number of affected rows
    """
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(query, params or ())
        return cur.rowcount


def execute_insert_returning(query: str, params: Optional[tuple] = None) -> Dict[str, Any]:
    """
    Execute an INSERT query with RETURNING clause.

    Args:
        query: SQL query string (must include RETURNING)
        params: Query parameters tuple

    Returns:
        Inserted row as dictionary
    """
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(query, params or ())
        return cur.fetchone()


def test_connection() -> bool:
    """
    Test database connection.

    Returns:
        True if connection successful
    """
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            return True
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        return False
