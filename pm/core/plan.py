"""Plan management for project manager."""

import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any

from .config import Config
from .task import Task, TaskStatus
from ..utils.helpers import load_yaml, save_yaml, get_timestamp, ensure_dir
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PlanStatus(str, Enum):
    """Plan status enumeration."""
    DRAFT = 'draft'
    PENDING = 'pending'
    APPROVED = 'approved'
    EXECUTING = 'executing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'

    def __str__(self):
        return self.value


@dataclass
class Plan:
    """
    Plan representation following the new YAML schema.

    Schema:
        metadata:
          id: UUID
          name: string
          version: semver
          created_at: ISO-8601
          updated_at: ISO-8601
          author: string
          tags: [string]

        summary:
          brief: string (128 chars)
          objectives: [string]
          deliverables: [string]

        status:
          current: draft|pending|approved|executing|completed|failed|cancelled
          is_approved: boolean
          approved_by: string
          approved_at: ISO-8601

        execution:
          started_at: ISO-8601
          completed_at: ISO-8601
          progress: 0-100

        tasks_summary:
          total: number
          completed: number
          in_progress: number
          blocked: number
    """

    # Metadata
    name: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: str = "1.0.0"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    # Summary
    brief: str = ""
    objectives: List[str] = field(default_factory=list)
    deliverables: List[str] = field(default_factory=list)

    # Status
    status: PlanStatus = PlanStatus.DRAFT
    is_approved: bool = False
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None

    # Execution
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: int = 0

    # Tasks (loaded separately)
    _tasks: List[Task] = field(default_factory=list, init=False, repr=False)
    _config: Optional[Config] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Initialize timestamps if not set."""
        if self.created_at is None:
            self.created_at = get_timestamp()
        if self.updated_at is None:
            self.updated_at = get_timestamp()

        # Ensure status is PlanStatus enum
        if isinstance(self.status, str):
            self.status = PlanStatus(self.status)

    def set_config(self, config: Config) -> None:
        """Set configuration instance."""
        self._config = config

    def to_dict(self) -> Dict[str, Any]:
        """Convert plan to dictionary following schema."""
        tasks_summary = self._calculate_tasks_summary()

        return {
            'metadata': {
                'id': self.id,
                'name': self.name,
                'version': self.version,
                'created_at': self.created_at,
                'updated_at': self.updated_at,
                'author': self.author,
                'tags': self.tags
            },
            'summary': {
                'brief': self.brief,
                'objectives': self.objectives,
                'deliverables': self.deliverables
            },
            'status': {
                'current': str(self.status),
                'is_approved': self.is_approved,
                'approved_by': self.approved_by,
                'approved_at': self.approved_at
            },
            'execution': {
                'started_at': self.started_at,
                'completed_at': self.completed_at,
                'progress': self.progress
            },
            'tasks_summary': tasks_summary
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Plan':
        """Create plan from dictionary."""
        metadata = data.get('metadata', {})
        summary = data.get('summary', {})
        status_data = data.get('status', {})
        execution = data.get('execution', {})

        return cls(
            # Metadata
            id=metadata.get('id', str(uuid.uuid4())),
            name=metadata.get('name', ''),
            version=metadata.get('version', '1.0.0'),
            created_at=metadata.get('created_at'),
            updated_at=metadata.get('updated_at'),
            author=metadata.get('author'),
            tags=metadata.get('tags', []),
            # Summary
            brief=summary.get('brief', ''),
            objectives=summary.get('objectives', []),
            deliverables=summary.get('deliverables', []),
            # Status
            status=PlanStatus(status_data.get('current', 'draft')),
            is_approved=status_data.get('is_approved', False),
            approved_by=status_data.get('approved_by'),
            approved_at=status_data.get('approved_at'),
            # Execution
            started_at=execution.get('started_at'),
            completed_at=execution.get('completed_at'),
            progress=execution.get('progress', 0)
        )

    def _calculate_tasks_summary(self) -> Dict[str, int]:
        """Calculate tasks summary statistics."""
        summary = {
            'total': len(self._tasks),
            'completed': 0,
            'in_progress': 0,
            'blocked': 0
        }

        for task in self._tasks:
            if task.status == TaskStatus.COMPLETED:
                summary['completed'] += 1
            elif task.status == TaskStatus.EXECUTING:
                summary['in_progress'] += 1
            elif task.status == TaskStatus.BLOCKED:
                summary['blocked'] += 1

        return summary

    def update_status(self, new_status: PlanStatus) -> None:
        """Update plan status with timestamps."""
        self.status = new_status
        self.updated_at = get_timestamp()

        if new_status == PlanStatus.EXECUTING and self.started_at is None:
            self.started_at = get_timestamp()

        if new_status in [PlanStatus.COMPLETED, PlanStatus.FAILED, PlanStatus.CANCELLED]:
            self.completed_at = get_timestamp()
            if new_status == PlanStatus.COMPLETED:
                self.progress = 100

        logger.info(f"Plan {self.name} status updated to {new_status}")

    def approve(self, approved_by: str) -> None:
        """Approve plan for execution."""
        self.is_approved = True
        self.approved_by = approved_by
        self.approved_at = get_timestamp()
        self.status = PlanStatus.APPROVED
        self.updated_at = get_timestamp()
        logger.info(f"Plan {self.name} approved by {approved_by}")

    def update_progress(self) -> None:
        """Calculate and update plan progress based on tasks."""
        if not self._tasks:
            self.progress = 0
            return

        completed_count = sum(1 for task in self._tasks if task.status == TaskStatus.COMPLETED)
        self.progress = int((completed_count / len(self._tasks)) * 100)
        self.updated_at = get_timestamp()

        if self.progress == 100 and self.status != PlanStatus.COMPLETED:
            self.update_status(PlanStatus.COMPLETED)

    def load_tasks(self, config: Config) -> None:
        """Load all tasks for this plan."""
        self._config = config
        self._tasks.clear()

        tasks_dir = config.get_tasks_dir(self.name)
        if not tasks_dir.exists():
            logger.warning(f"Tasks directory not found: {tasks_dir}")
            return

        task_files = sorted(tasks_dir.glob('task-*.yaml'))
        for task_file in task_files:
            try:
                task = Task.load(str(task_file))
                self._tasks.append(task)
            except Exception as e:
                logger.error(f"Failed to load task from {task_file}: {e}")

        logger.info(f"Loaded {len(self._tasks)} tasks for plan {self.name}")

    def get_tasks(self) -> List[Task]:
        """Get all tasks."""
        return self._tasks.copy()

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        for task in self._tasks:
            if task.id == task_id:
                return task
        return None

    def add_task(self, task: Task) -> None:
        """Add a task to the plan."""
        if not self._config:
            raise ValueError("Config not set. Call set_config() first.")

        self._tasks.append(task)
        self.updated_at = get_timestamp()

        # Save task to file
        task_file = self._config.get_task_file(self.name, task.id)
        task.save(str(task_file))

        logger.info(f"Task {task.id} added to plan {self.name}")

    def remove_task(self, task_id: str) -> bool:
        """Remove a task from the plan."""
        task = self.get_task(task_id)
        if not task:
            return False

        self._tasks.remove(task)
        self.updated_at = get_timestamp()

        # Delete task file
        if self._config:
            task_file = self._config.get_task_file(self.name, task_id)
            if task_file.exists():
                task_file.unlink()

        logger.info(f"Task {task_id} removed from plan {self.name}")
        return True

    def get_ready_tasks(self) -> List[Task]:
        """Get tasks that are ready to execute."""
        completed_task_ids = [task.id for task in self._tasks if task.status == TaskStatus.COMPLETED]

        ready_tasks = []
        for task in self._tasks:
            if task.status == TaskStatus.PENDING and task.is_ready(completed_task_ids):
                ready_tasks.append(task)

        return ready_tasks

    def save(self, config: Config) -> None:
        """Save plan to YAML file."""
        self._config = config

        # Ensure plan directory exists
        plan_dir = config.get_plan_dir(self.name)
        ensure_dir(str(plan_dir))

        # Ensure tasks directory exists
        tasks_dir = config.get_tasks_dir(self.name)
        ensure_dir(str(tasks_dir))

        # Save plan.yaml
        plan_file = config.get_plan_file(self.name)
        save_yaml(self.to_dict(), str(plan_file))

        logger.info(f"Plan {self.name} saved to {plan_file}")

    @classmethod
    def load(cls, plan_name: str, config: Config) -> 'Plan':
        """Load plan from YAML file."""
        plan_file = config.get_plan_file(plan_name)
        if not plan_file.exists():
            raise FileNotFoundError(f"Plan file not found: {plan_file}")

        data = load_yaml(str(plan_file))
        plan = cls.from_dict(data)
        plan.set_config(config)
        plan.load_tasks(config)

        logger.info(f"Plan {plan_name} loaded from {plan_file}")
        return plan

    @classmethod
    def list_all(cls, config: Config) -> List[str]:
        """List all plan names."""
        return config.list_plans()

    def __str__(self) -> str:
        """String representation of plan."""
        return f"Plan({self.name}: {self.brief} [{self.status}])"
