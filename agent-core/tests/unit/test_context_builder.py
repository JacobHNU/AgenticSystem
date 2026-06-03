import pytest
from app.context.builder import ContextBuilder
from app.context.models import LayerConfig, LayerType, MergeStrategy, ContextBuildRequest

class TestContextBuilder:
    @pytest.fixture
    def builder(self):
        return ContextBuilder()

    @pytest.mark.asyncio
    async def test_build_with_base_layer(self, builder):
        request = ContextBuildRequest(
            layers_config={
                "L1_base": LayerConfig(
                    priority=1,
                    template_content="You are a helpful assistant.",
                    merge_strategy=MergeStrategy.REPLACE
                )
            }
        )
        result = await builder.build(request)
        assert "helpful assistant" in result.prompt
        assert result.total_tokens > 0

    @pytest.mark.asyncio
    async def test_build_empty_layers(self, builder):
        request = ContextBuildRequest(layers_config={})
        result = await builder.build(request)
        assert result.prompt == ""
        assert result.total_tokens == 0

    @pytest.mark.asyncio
    async def test_build_multiple_layers(self, builder):
        request = ContextBuildRequest(
            layers_config={
                "L1_base": LayerConfig(priority=1, template_content="Base role"),
                "L6_output": LayerConfig(priority=6, template_content="Return JSON"),
            }
        )
        result = await builder.build(request)
        assert "Base role" in result.prompt
        assert "Return JSON" in result.prompt
        assert len(result.layer_details) == 2
