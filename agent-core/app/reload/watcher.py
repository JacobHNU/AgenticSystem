import logging
from pathlib import Path
from watchdog.events import FileSystemEventHandler
from typing import Callable, List

logger = logging.getLogger(__name__)


class SkillFileHandler(FileSystemEventHandler):
    """Watch skill directory for changes"""

    def __init__(self, callback: Callable):
        self.callback = callback
        self._debounce_files = set()

    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(('.yaml', '.jinja2', '.md')):
            self._debounce_files.add(event.src_path)
            logger.info(f"Skill file changed: {event.src_path}")

    def on_created(self, event):
        self.on_modified(event)

    def flush(self) -> List[str]:
        files = list(self._debounce_files)
        self._debounce_files.clear()
        return files


class WorkflowFileHandler(FileSystemEventHandler):
    """Watch workflow directory for changes"""

    def __init__(self, callback: Callable):
        self.callback = callback
        self._debounce_files = set()

    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith('.yaml'):
            self._debounce_files.add(event.src_path)
            logger.info(f"Workflow file changed: {event.src_path}")

    def on_created(self, event):
        self.on_modified(event)

    def flush(self) -> List[str]:
        files = list(self._debounce_files)
        self._debounce_files.clear()
        return files
