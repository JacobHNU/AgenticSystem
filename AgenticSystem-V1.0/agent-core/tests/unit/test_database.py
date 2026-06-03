import pytest
from app.core.database import Database

def test_database_init():
    db = Database(host="localhost", port=3306, database="test", user="root", password="")
    assert db.host == "localhost"
    assert db.pool is None

def test_database_dsn():
    db = Database(host="localhost", port=3306, database="test", user="root", password="pw")
    assert "localhost" in db.dsn
