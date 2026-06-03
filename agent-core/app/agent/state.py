import json
import logging
from typing import Optional
from datetime import datetime

from .models import AgentState

logger = logging.getLogger(__name__)


class StateStore:
    """Agent state store: Redis (hot) + MySQL (cold)"""

    def __init__(self, cache, database):
        self.cache = cache
        self.database = database

    async def save(self, state: AgentState):
        """Save state to Redis (hot) and periodically to MySQL (cold)"""
        state.version += 1
        key = f"agent:state:{state.agent_id}"

        # Always save to Redis
        await self.cache.set(key, state.model_dump(), ttl=3600)

        # Periodic MySQL checkpoint (every 5 versions)
        if state.version % 5 == 0:
            await self._save_to_mysql(state)

    async def load(self, agent_id: str) -> Optional[AgentState]:
        """Load state: try Redis first, fall back to MySQL"""
        key = f"agent:state:{agent_id}"
        data = await self.cache.get(key)
        if data:
            return AgentState(**data)

        # Fall back to MySQL
        row = await self.database.fetchone(
            "SELECT * FROM agent_states WHERE agent_id = %s", (agent_id,)
        )
        if row:
            state = self._row_to_state(row)
            # Warm up Redis
            await self.cache.set(key, state.model_dump(), ttl=3600)
            return state
        return None

    async def _save_to_mysql(self, state: AgentState):
        """Save state snapshot to MySQL"""
        try:
            await self.database.execute(
                """INSERT INTO agent_states (agent_id, session_id, skill_set, memory,
                   task_stack, workflow_context, current_step, scratch_pad, status,
                   version, created_at, last_checkpoint)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE
                   session_id=VALUES(session_id), skill_set=VALUES(skill_set),
                   memory=VALUES(memory), task_stack=VALUES(task_stack),
                   workflow_context=VALUES(workflow_context), current_step=VALUES(current_step),
                   scratch_pad=VALUES(scratch_pad), status=VALUES(status),
                   version=VALUES(version), last_checkpoint=VALUES(last_checkpoint)""",
                (
                    state.agent_id, state.session_id,
                    json.dumps(state.skill_set),
                    json.dumps([m for m in state.memory]),
                    json.dumps([t.model_dump() for t in state.task_stack]),
                    json.dumps(state.workflow_context) if state.workflow_context else None,
                    state.current_step,
                    json.dumps(state.scratch_pad),
                    "running",
                    state.version,
                    datetime.now(),
                    datetime.now()
                )
            )
        except Exception as e:
            logger.error(f"Failed to save state to MySQL: {e}")

    def _row_to_state(self, row: dict) -> AgentState:
        from .models import TaskFrame
        return AgentState(
            agent_id=row["agent_id"],
            session_id=row["session_id"],
            skill_set=json.loads(row["skill_set"]) if row["skill_set"] else [],
            memory=json.loads(row["memory"]) if row["memory"] else [],
            task_stack=[TaskFrame(**t) for t in json.loads(row["task_stack"])] if row["task_stack"] else [],
            workflow_context=json.loads(row["workflow_context"]) if row["workflow_context"] else None,
            current_step=row.get("current_step", 0),
            scratch_pad=json.loads(row["scratch_pad"]) if row["scratch_pad"] else {},
            version=row.get("version", 1)
        )

    async def delete(self, agent_id: str):
        key = f"agent:state:{agent_id}"
        await self.cache.delete(key)
        await self.database.execute(
            "UPDATE agent_states SET status = 'terminated' WHERE agent_id = %s", (agent_id,)
        )
