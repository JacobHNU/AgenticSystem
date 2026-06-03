from typing import Dict, Any, Optional


class AuthManager:
    """MCP tool authentication manager"""

    def __init__(self):
        self._credentials: Dict[str, Dict[str, str]] = {}

    def register(self, tool_name: str, auth_type: str, credentials: Dict[str, str]):
        self._credentials[tool_name] = {"type": auth_type, **credentials}

    def get_auth(self, tool_name: str) -> Optional[Dict[str, str]]:
        return self._credentials.get(tool_name)

    def get_headers(self, tool_name: str) -> Dict[str, str]:
        auth = self.get_auth(tool_name)
        if not auth:
            return {}
        if auth["type"] == "bearer":
            return {"Authorization": f"Bearer {auth['token']}"}
        if auth["type"] == "api_key":
            return {"X-API-Key": auth["key"]}
        return {}
