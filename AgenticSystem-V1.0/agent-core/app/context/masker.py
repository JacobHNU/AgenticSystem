import re
import yaml
from typing import Any, Dict, List, Optional, Tuple


class SensitiveFieldMasker:
    """Sensitive field masker with configurable rules"""

    BUILTIN_PATTERNS = {
        "phone": (r'(\d{3})\d{4}(\d{4})', r'\1****\2'),
        "id_card": (r'(\d{6})\d{8}(\d{4})', r'\1********\2'),
        "email": (r'(.{2}).+(@.+)', r'\1***\2'),
        "bank_card": (r'(\d{4})\d+(\d{4})', r'\1 **** **** \2'),
    }

    def __init__(
        self,
        fields_to_mask: List[str] = None,
        custom_patterns: Dict[str, Tuple[str, str]] = None,
        pattern_config_path: str = None
    ):
        self.fields_to_mask = fields_to_mask or []
        self.patterns = dict(self.BUILTIN_PATTERNS)
        if custom_patterns:
            self.patterns.update(custom_patterns)
        if pattern_config_path:
            self._load_from_config(pattern_config_path)

    def _load_from_config(self, config_path: str):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        for rule in config.get("masking_rules", []):
            self.patterns[rule["name"]] = (rule["regex"], rule["replacement"])

    def mask(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            key: self._mask_value(key, value) if key in self.fields_to_mask else value
            for key, value in data.items()
        }

    def _mask_value(self, field_name: str, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        for pattern_name, (regex, replacement) in self.patterns.items():
            if pattern_name in field_name.lower():
                return re.sub(regex, replacement, value)
        # Fallback: generic masking
        if len(value) > 6:
            return value[:2] + "*" * (len(value) - 4) + value[-2:]
        return "***"
