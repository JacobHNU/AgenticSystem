import pytest
from app.context.trimmer import SmartHistoryTrimmer

class TestSmartHistoryTrimmer:
    @pytest.fixture
    def trimmer(self):
        return SmartHistoryTrimmer()

    @pytest.fixture
    def count_fn(self):
        return lambda text: len(text) // 2

    @pytest.mark.parametrize("history, max_tokens, expected_steps", [
        (
            [{"step": "a", "status": "COMPLETED"}],
            1000,
            ["a"]
        ),
        (
            [
                {"step": "a", "status": "COMPLETED"},
                {"step": "b", "status": "FAILED"},
                {"step": "c", "status": "COMPLETED"},
            ],
            20,
            ["b", "c"]
        ),
        (
            [
                {"step": "a", "status": "COMPLETED"},
                {"step": "b", "status": "FAILED"},
                {"step": "c", "status": "COMPLETED"},
                {"step": "d", "status": "COMPLETED"},
                {"step": "e", "status": "FAILED"},
            ],
            25,
            ["b", "d", "e"]
        ),
        ([], 1000, []),
        (
            [
                {"step": "a", "status": "FAILED"},
                {"step": "b", "status": "FAILED"},
            ],
            10,
            ["a", "b"]
        ),
        (
            [
                {"step": "a", "status": "COMPLETED"},
                {"step": "b", "status": "SKIPPED"},
                {"step": "c", "status": "COMPLETED"},
            ],
            20,
            ["b", "c"]
        ),
    ])
    def test_trim(self, trimmer, count_fn, history, max_tokens, expected_steps):
        result = trimmer.trim(history, max_tokens, count_fn)
        assert [s["step"] for s in result] == expected_steps
