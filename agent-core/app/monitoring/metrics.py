from prometheus_client import Counter, Histogram, Gauge


class MetricsCollector:
    """Prometheus metrics collector"""

    def __init__(self):
        # Agent metrics
        self.agent_iterations = Counter(
            'agent_iterations_total', 'Agent loop iterations',
            ['agent_id', 'status']
        )
        self.agent_task_duration = Histogram(
            'agent_task_duration_seconds', 'Task execution time'
        )
        self.active_agents = Gauge(
            'active_agents', 'Number of active agents'
        )

        # Skill metrics
        self.skill_executions = Counter(
            'skill_executions_total', 'Skill executions',
            ['skill_name', 'status']
        )
        self.skill_duration = Histogram(
            'skill_duration_seconds', 'Skill execution time',
            ['skill_name']
        )

        # Workflow metrics
        self.workflow_step_duration = Histogram(
            'workflow_step_duration_seconds', 'Step execution time',
            ['step_type']
        )
        self.workflow_degradations = Counter(
            'workflow_degradations_total', 'Degradation events',
            ['workflow_name', 'fallback_workflow']
        )

        # MCP metrics
        self.mcp_call_duration = Histogram(
            'mcp_call_duration_seconds', 'MCP tool call time',
            ['tool_name', 'action']
        )
        self.mcp_circuit_state = Gauge(
            'mcp_circuit_state', 'Circuit breaker state (0=closed, 1=open, 2=half_open)',
            ['tool_name']
        )
        self.mcp_call_errors = Counter(
            'mcp_call_errors_total', 'MCP call errors',
            ['tool_name', 'error_type']
        )
