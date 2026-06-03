import pytest
from app.core.cache import Cache

def test_cache_init():
    cache = Cache(host="localhost", port=6379, db=0, ttl=3600)
    assert cache.host == "localhost"
    assert cache.ttl == 3600
    assert cache.client is None
