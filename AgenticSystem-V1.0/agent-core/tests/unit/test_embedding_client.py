import pytest
from app.core.embedding_client import EmbeddingClient

def test_embedding_client_init():
    client = EmbeddingClient(api_url="http://localhost:8081/embed", api_key="test")
    assert client.api_url == "http://localhost:8081/embed"
