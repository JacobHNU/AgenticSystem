import os
import pytest
from app.core.config import load_config

def test_load_base_config():
    config = load_config("config/settings.yaml")
    assert config["app"]["name"] == "agent-core"
    assert config["agent"]["max_iterations"] == 10

def test_env_var_override(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "test-secret")
    config = load_config("config/settings.yaml")
    assert config["app"]["admin_api_key"] == "test-secret"

def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent.yaml")
