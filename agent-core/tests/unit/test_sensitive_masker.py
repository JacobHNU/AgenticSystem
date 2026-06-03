import pytest
from app.context.masker import SensitiveFieldMasker

class TestSensitiveFieldMasker:
    @pytest.mark.parametrize("field, value, expected", [
        ("phone", "13812345678", "138****5678"),
        ("id_card", "110101199001011234", "110101********1234"),
        ("email", "zhangsan@company.com", "zh***@company.com"),
        ("bank_card", "6222021234567890123", "6222 **** **** 0123"),
    ])
    def test_builtin_masking(self, field, value, expected):
        masker = SensitiveFieldMasker(fields_to_mask=[field])
        result = masker.mask({field: value})
        assert result[field] == expected

    def test_field_not_in_mask_list(self):
        masker = SensitiveFieldMasker(fields_to_mask=["phone"])
        result = masker.mask({"name": "zhangsan"})
        assert result["name"] == "zhangsan"

    def test_custom_pattern(self):
        masker = SensitiveFieldMasker(
            fields_to_mask=["employee_code"],
            custom_patterns={"employee_code": (r'^(EMP)(\d+)$', r'EMP***')}
        )
        result = masker.mask({"employee_code": "EMP001"})
        assert result["employee_code"] == "EMP***"

    def test_non_string_value_untouched(self):
        masker = SensitiveFieldMasker(fields_to_mask=["age"])
        result = masker.mask({"age": 25})
        assert result["age"] == 25

    def test_fallback_masking_for_unknown_field(self):
        masker = SensitiveFieldMasker(fields_to_mask=["secret"])
        result = masker.mask({"secret": "verylongsecret"})
        assert result["secret"] != "verylongsecret"
        assert "*" in result["secret"]
