import os
import re
import yaml
from pathlib import Path
from typing import Any, Dict

_ENV_PATTERN = re.compile(r'\$\{(\w+)(?::([^}]*))?\}')


def _resolve_env_vars(value: Any) -> Any:
    """Recursively resolve ${VAR} and ${VAR:default} patterns"""
    if isinstance(value, str):
        def replacer(match):
            var_name = match.group(1)
            default = match.group(2)
            return os.environ.get(var_name, default if default is not None else match.group(0))
        return _ENV_PATTERN.sub(replacer, value)
    elif isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


def load_config(config_path: str, overlay_path: str = None) -> Dict[str, Any]:
    """Load YAML config with optional overlay and env var resolution"""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f) or {}

    if overlay_path:
        overlay = Path(overlay_path)
        if overlay.exists():
            with open(overlay, 'r', encoding='utf-8') as f:
                overlay_config = yaml.safe_load(f) or {}
            config = _deep_merge(config, overlay_config)

    return _resolve_env_vars(config)


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge override into base"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
