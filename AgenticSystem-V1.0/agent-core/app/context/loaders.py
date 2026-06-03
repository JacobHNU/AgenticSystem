import json
from typing import Any, Dict, List
from jinja2 import Environment, StrictUndefined

from .models import LayerConfig, ContextBuildRequest
from .masker import SensitiveFieldMasker
from .trimmer import SmartHistoryTrimmer


def _count_tokens(text: str) -> int:
    """Simple token estimation: ~2 chars per token for mixed CJK/EN"""
    return len(text) // 2


class LayerLoaders:
    """L1-L6 layer loaders"""

    def __init__(self):
        self.jinja_env = Environment(undefined=StrictUndefined, autoescape=False)
        self.jinja_env.filters['to_json'] = lambda v: json.dumps(v, ensure_ascii=False)
        self.jinja_env.filters['default_if_none'] = lambda v, d: d if v is None else v

    async def load_base(self, config: LayerConfig, request: ContextBuildRequest) -> str:
        if not config.template_content:
            return ""
        template = self.jinja_env.from_string(config.template_content)
        return template.render()

    async def load_business(self, config: LayerConfig, request: ContextBuildRequest) -> str:
        if not config.template_content:
            return ""
        template = self.jinja_env.from_string(config.template_content)
        return template.render(domain=request.domain)

    async def load_dynamic(self, config: LayerConfig, request: ContextBuildRequest) -> str:
        user_info = request.user_info or {}
        if request.mask_sensitive and user_info:
            masker = SensitiveFieldMasker(
                fields_to_mask=request.sensitive_fields,
                pattern_config_path=request.masking_config_path
            )
            user_info = masker.mask(user_info)

        if not user_info:
            return ""

        if config.template_content:
            template = self.jinja_env.from_string(config.template_content)
            return template.render(**request.variables, user=user_info)

        return "\n".join(f"- {k}: {v}" for k, v in user_info.items())

    async def load_history(self, config: LayerConfig, request: ContextBuildRequest) -> str:
        history = request.history or []
        if not history:
            return ""

        history_token_budget = int(request.token_limit * 0.3)
        trimmer = SmartHistoryTrimmer()
        history = trimmer.trim(history, history_token_budget, _count_tokens)

        if config.template_content:
            template = self.jinja_env.from_string(config.template_content)
            return template.render(history=history)

        lines = ["已执行步骤："]
        for step in history:
            status = step.get("status", "unknown")
            name = step.get("step", "unknown")
            icon = {"COMPLETED": "✓", "FAILED": "✗", "SKIPPED": "○"}.get(status, "?")
            line = f"- {icon} {name}: {status}"
            output = step.get("output")
            if output and status == "COMPLETED":
                line += f" → {str(output)[:200]}"
            elif output and status == "FAILED":
                line += f" → 错误: {output}"
            lines.append(line)
        return "\n".join(lines)

    async def load_tools(self, config: LayerConfig, request: ContextBuildRequest, mcp_client=None) -> str:
        tools = request.available_tools or []
        if not tools and mcp_client and request.domain:
            tools = await mcp_client.list_tools(domain=request.domain)
        if not tools:
            return ""

        if config.template_content:
            template = self.jinja_env.from_string(config.template_content)
            return template.render(tools=tools)

        lines = ["可用工具："]
        for tool in tools:
            name = tool.get("name", "unknown")
            desc = tool.get("description", "")
            actions = tool.get("tools", [])
            lines.append(f"- {name}: {desc}")
            if actions:
                lines.append(f"  操作: {', '.join(actions)}")
        return "\n".join(lines)

    async def load_output(self, config: LayerConfig, request: ContextBuildRequest) -> str:
        if not config.template_content:
            return ""
        template = self.jinja_env.from_string(config.template_content)
        return template.render()
