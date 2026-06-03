import pytest
from app.reload.manager import HotReloadManager

class TestHotReloadManager:
    def test_init(self):
        manager = HotReloadManager(skill_engine=None, workflow_engine=None)
        assert manager is not None
