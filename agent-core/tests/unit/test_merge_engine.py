import pytest
from app.context.merger import MergeEngine, MergeStrategy

class TestMergeEngine:
    def setup_method(self):
        self.engine = MergeEngine()

    def test_replace(self):
        result = self.engine.merge("old content", "new content", MergeStrategy.REPLACE)
        assert result == "new content"

    def test_append(self):
        result = self.engine.merge("existing", "new", MergeStrategy.APPEND)
        assert result == "existing\nnew"

    def test_append_empty_existing(self):
        result = self.engine.merge("", "new", MergeStrategy.APPEND)
        assert result == "new"

    def test_union_dedup(self):
        existing = "line1\nline2\nline3"
        new = "line2\nline3\nline4"
        result = self.engine.merge(existing, new, MergeStrategy.UNION)
        lines = [l for l in result.split("\n") if l.strip()]
        assert len(lines) == 4
        assert "line4" in lines
