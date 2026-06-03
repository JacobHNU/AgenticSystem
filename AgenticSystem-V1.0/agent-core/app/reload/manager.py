import asyncio
import logging
from typing import List, Optional
from watchdog.observers import Observer

from .watcher import SkillFileHandler, WorkflowFileHandler

logger = logging.getLogger(__name__)


class ReloadResult:
    def __init__(self, success: bool, count: int = 0, errors: List[str] = None):
        self.success = success
        self.count = count
        self.errors = errors or []


class HotReloadManager:
    """Hot reload manager with file watcher and API trigger"""

    def __init__(self, skill_engine, workflow_engine, skills_dir: str = "skills", workflows_dir: str = "workflows"):
        self.skill_engine = skill_engine
        self.workflow_engine = workflow_engine
        self.skills_dir = skills_dir
        self.workflows_dir = workflows_dir
        self.observer = Observer()
        self._reload_lock = asyncio.Lock()
        self._skill_handler = None
        self._workflow_handler = None

    def start(self):
        self._skill_handler = SkillFileHandler(self._on_skill_change)
        self.observer.schedule(self._skill_handler, self.skills_dir, recursive=True)

        self._workflow_handler = WorkflowFileHandler(self._on_workflow_change)
        self.observer.schedule(self._workflow_handler, self.workflows_dir, recursive=True)

        self.observer.start()
        logger.info(f"Hot reload watching: {self.skills_dir}, {self.workflows_dir}")

    def stop(self):
        self.observer.stop()
        self.observer.join()

    def _on_skill_change(self, event):
        logger.info(f"Skill file change detected: {event.src_path}")

    def _on_workflow_change(self, event):
        logger.info(f"Workflow file change detected: {event.src_path}")

    async def reload_skills(self, changed_files: List[str] = None) -> ReloadResult:
        async with self._reload_lock:
            try:
                if self.skill_engine:
                    await self.skill_engine.reload(changed_files)
                    count = self.skill_engine.registry.count()
                    return ReloadResult(success=True, count=count)
                return ReloadResult(success=False, errors=["Skill engine not configured"])
            except Exception as e:
                logger.error(f"Skill reload failed: {e}")
                return ReloadResult(success=False, errors=[str(e)])

    async def reload_workflows(self, changed_files: List[str] = None) -> ReloadResult:
        async with self._reload_lock:
            try:
                if self.workflow_engine and hasattr(self.workflow_engine, 'reload'):
                    await self.workflow_engine.reload(changed_files)
                    return ReloadResult(success=True, count=len(self.workflow_engine.definitions))
                return ReloadResult(success=False, errors=["Workflow engine not configured"])
            except Exception as e:
                logger.error(f"Workflow reload failed: {e}")
                return ReloadResult(success=False, errors=[str(e)])

    async def reload_all(self):
        wf = await self.reload_workflows()
        sk = await self.reload_skills()
        return {"workflows": {"success": wf.success, "count": wf.count},
                "skills": {"success": sk.success, "count": sk.count}}
