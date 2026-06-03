from typing import Optional
from jinja2 import Environment, StrictUndefined

from .models import (
    LayerType, ContextBuildRequest, ContextBuildResult, ContextLayerResult
)
from .loaders import LayerLoaders, _count_tokens
from .merger import MergeEngine
from .trimmer import TokenTrimmer


class ContextBuilder:
    """Six-layer context builder"""

    def __init__(self, mcp_client=None):
        self.mcp_client = mcp_client
        self.loaders = LayerLoaders()
        self.merger = MergeEngine()
        self.token_trimmer = TokenTrimmer()

    async def build(self, request: ContextBuildRequest) -> ContextBuildResult:
        layer_results = []

        loader_map = {
            LayerType.BASE: self.loaders.load_base,
            LayerType.BUSINESS: self.loaders.load_business,
            LayerType.DYNAMIC: self.loaders.load_dynamic,
            LayerType.HISTORY: self.loaders.load_history,
            LayerType.TOOLS: lambda c, r: self.loaders.load_tools(c, r, self.mcp_client),
            LayerType.OUTPUT: self.loaders.load_output,
        }

        for layer_type in LayerType:
            config = request.layers_config.get(layer_type.value)
            if not config:
                continue

            loader = loader_map.get(layer_type)
            if not loader:
                continue

            content = await loader(config, request)
            if content and content.strip():
                token_count = _count_tokens(content)
                layer_results.append(ContextLayerResult(
                    layer=layer_type,
                    content=content,
                    token_count=token_count,
                    priority=config.priority
                ))

        layer_results.sort(key=lambda r: r.priority)

        # Token trimming
        total_tokens = sum(r.token_count for r in layer_results)
        trimmed = False
        trimmed_layers = []

        if total_tokens > request.token_limit:
            layer_results, trimmed_layers = self.token_trimmer.trim_layers(
                layer_results, request.token_limit
            )
            trimmed = True
            total_tokens = sum(r.token_count for r in layer_results)

        prompt = "\n\n".join(r.content for r in layer_results)

        return ContextBuildResult(
            prompt=prompt,
            total_tokens=total_tokens,
            layer_details=layer_results,
            trimmed=trimmed,
            trimmed_layers=trimmed_layers
        )
