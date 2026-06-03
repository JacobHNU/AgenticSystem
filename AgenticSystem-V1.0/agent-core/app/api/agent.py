import uuid
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

router = APIRouter(prefix="/api/v1/agents")

class TaskRequest(BaseModel):
    task: str
    context: Dict[str, Any] = {}

@router.post("/{agent_id}/tasks")
async def create_task(agent_id: str, request: TaskRequest, background_tasks: BackgroundTasks):
    task_id = uuid.uuid4().hex
    return {"task_id": task_id, "agent_id": agent_id, "status": "accepted"}

@router.get("/{agent_id}/tasks/{task_id}")
async def get_task_status(agent_id: str, task_id: str):
    return {"task_id": task_id, "status": "pending"}

@router.get("/{agent_id}/state")
async def get_agent_state(agent_id: str):
    return {"agent_id": agent_id, "status": "running"}
