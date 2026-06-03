import pytest
from app.core.llm_client import LLMClient

def test_llm_client_init():
    client = LLMClient(model="claude-sonnet-4-20250514")
    assert client.model == "claude-sonnet-4-20250514"
