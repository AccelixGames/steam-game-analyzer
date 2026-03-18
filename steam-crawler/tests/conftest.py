import sqlite3
import pytest
from pathlib import Path


@pytest.fixture
def db_path(tmp_path):
    """Provides a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def db_conn(db_path):
    """Provides a fresh database connection with schema initialized."""
    from steam_crawler.db.schema import init_db

    conn = init_db(str(db_path))
    yield conn
    conn.close()
