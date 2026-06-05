import json
import logging
from typing import List, Dict, Any, Optional

from ..workflow.models import WorkflowDefinition, WorkflowStep, StepType
from ..core.llm_client import LLMClient

logger = logging.getLogger(__name__)


class DynamicWorkflowBuilder:
    """Builder to generate WorkflowDefinition from business process description"""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    async def build_workflow(
        self,
        skill_name: str,
        description: str,
        available_tools: List[Dict[str, Any]],
        trace_id: str = None
    ) -> Optional[WorkflowDefinition]:
        """Use LLM to interpret description and map to tools"""
        
        tools_summary = "\n".join([
            f"- {t['name']}: {t['description']} (Actions: {', '.join(t.get('tools', []))})"
            for t in available_tools
        ])

        prompt = f"""## Business Process Description
{description}

## Available Tools
{tools_summary}

## Task
Interpret the process description and create a structured workflow using the available tools.
Identify steps, tool mappings, parameters, and dependencies for parallel execution.

## Output Format (JSON)
Return a WorkflowDefinition JSON:
{{
  "name": "{skill_name}_dynamic",
  "version": "1.0.0",
  "description": "Auto-generated workflow",
  "steps": [
    {{
      "name": "step_name",
      "type": "mcp_tool",
      "mcp_tool": "tool_name",
      "action": "action_name",
      "input_template": {{ "param": "{{{{ var }}}}" }},
      "output_key": "result_key",
      "depends_on": ["previous_step_name"]
    }}
  ]
}}
"""

        try:
            response = await self.llm_client.complete(
                messages=[{"role": "user", "content": prompt}],
                system="You are an expert workflow architect. Output ONLY valid JSON."
            )
            
            # Clean response if needed (remove markdown backticks)
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:-3].strip()
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:-3].strip()

            data = json.loads(cleaned)
            return WorkflowDefinition(**data)
            
        except Exception as e:
            logger.error(f"[{trace_id}] Failed to build dynamic workflow: {e}")
            return None
