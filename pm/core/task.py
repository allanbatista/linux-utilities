"""Task management for project manager."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from pathlib import Path

from ..utils.helpers import load_yaml, save_yaml, get_timestamp
from ..utils.logger import get_logger

logger = get_logger(__name__)


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = 'pending'
    READY = 'ready'
    EXECUTING = 'executing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    BLOCKED = 'blocked'

    def __str__(self):
        return self.value


class TaskPriority(str, Enum):
    """Task priority enumeration."""
    CRITICAL = 'critical'
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'

    def __str__(self):
        return self.value


@dataclass
class Task:
    """
    Task representation following the new YAML schema.

    Schema:
        metadata:
          id: string
          order: number
          created_at: ISO-8601
          updated_at: ISO-8601

        summary:
          title: string (128 chars)
          description: markdown
          priority: critical|high|medium|low
          estimated_hours: number

        status:
          current: pending|ready|executing|completed|failed|blocked
          started_at: ISO-8601
          completed_at: ISO-8601
          progress: 0-100

        dependencies:
          requires: [task_id]
          blocks: [task_id]

        execution:
          assigned_to: string
          notes: markdown
          artifacts: [path]
    """

    # Metadata
    id: str
    order: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # Summary
    title: str = ""
    description: str = ""
    priority: TaskPriority = TaskPriority.MEDIUM
    estimated_hours: float = 0.0

    # Status
    status: TaskStatus = TaskStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: int = 0

    # Dependencies
    requires: List[str] = field(default_factory=list)
    blocks: List[str] = field(default_factory=list)

    # Execution
    assigned_to: Optional[str] = None
    notes: str = ""
    artifacts: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Initialize timestamps if not set."""
        if self.created_at is None:
            self.created_at = get_timestamp()
        if self.updated_at is None:
            self.updated_at = get_timestamp()

        # Ensure priority is TaskPriority enum
        if isinstance(self.priority, str):
            self.priority = TaskPriority(self.priority)

        # Ensure status is TaskStatus enum
        if isinstance(self.status, str):
            self.status = TaskStatus(self.status)

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary following schema."""
        return {
            'metadata': {
                'id': self.id,
                'order': self.order,
                'created_at': self.created_at,
                'updated_at': self.updated_at
            },
            'summary': {
                'title': self.title,
                'description': self.description,
                'priority': str(self.priority),
                'estimated_hours': self.estimated_hours
            },
            'status': {
                'current': str(self.status),
                'started_at': self.started_at,
                'completed_at': self.completed_at,
                'progress': self.progress
            },
            'dependencies': {
                'requires': self.requires,
                'blocks': self.blocks
            },
            'execution': {
                'assigned_to': self.assigned_to,
                'notes': self.notes,
                'artifacts': self.artifacts
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """Create task from dictionary."""
        metadata = data.get('metadata', {})
        summary = data.get('summary', {})
        status_data = data.get('status', {})
        dependencies = data.get('dependencies', {})
        execution = data.get('execution', {})

        return cls(
            # Metadata
            id=metadata.get('id', ''),
            order=metadata.get('order', 0),
            created_at=metadata.get('created_at'),
            updated_at=metadata.get('updated_at'),
            # Summary
            title=summary.get('title', ''),
            description=summary.get('description', ''),
            priority=TaskPriority(summary.get('priority', 'medium')),
            estimated_hours=summary.get('estimated_hours', 0.0),
            # Status
            status=TaskStatus(status_data.get('current', 'pending')),
            started_at=status_data.get('started_at'),
            completed_at=status_data.get('completed_at'),
            progress=status_data.get('progress', 0),
            # Dependencies
            requires=dependencies.get('requires', []),
            blocks=dependencies.get('blocks', []),
            # Execution
            assigned_to=execution.get('assigned_to'),
            notes=execution.get('notes', ''),
            artifacts=execution.get('artifacts', [])
        )

    def update_status(self, new_status: TaskStatus) -> None:
        """Update task status with timestamps."""
        self.status = new_status
        self.updated_at = get_timestamp()

        if new_status == TaskStatus.EXECUTING and self.started_at is None:
            self.started_at = get_timestamp()

        if new_status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            self.completed_at = get_timestamp()
            if new_status == TaskStatus.COMPLETED:
                self.progress = 100

        logger.info(f"Task {self.id} status updated to {new_status}")

    def update_progress(self, progress: int) -> None:
        """Update task progress (0-100)."""
        self.progress = max(0, min(100, progress))
        self.updated_at = get_timestamp()

        if self.progress == 100 and self.status != TaskStatus.COMPLETED:
            self.update_status(TaskStatus.COMPLETED)

        logger.info(f"Task {self.id} progress updated to {self.progress}%")

    def add_dependency(self, task_id: str) -> None:
        """Add a task dependency (this task requires another)."""
        if task_id not in self.requires:
            self.requires.append(task_id)
            self.updated_at = get_timestamp()
            logger.info(f"Task {self.id} now requires {task_id}")

    def add_blocker(self, task_id: str) -> None:
        """Add a task that this task blocks."""
        if task_id not in self.blocks:
            self.blocks.append(task_id)
            self.updated_at = get_timestamp()
            logger.info(f"Task {self.id} now blocks {task_id}")

    def remove_dependency(self, task_id: str) -> None:
        """Remove a task dependency."""
        if task_id in self.requires:
            self.requires.remove(task_id)
            self.updated_at = get_timestamp()
            logger.info(f"Removed dependency {task_id} from task {self.id}")

    def is_ready(self, completed_tasks: List[str]) -> bool:
        """Check if task is ready to execute based on dependencies."""
        if not self.requires:
            return True
        return all(dep in completed_tasks for dep in self.requires)

    def assign(self, assignee: str) -> None:
        """Assign task to someone."""
        self.assigned_to = assignee
        self.updated_at = get_timestamp()
        logger.info(f"Task {self.id} assigned to {assignee}")

    def add_artifact(self, artifact_path: str) -> None:
        """Add an artifact (file path) to task."""
        if artifact_path not in self.artifacts:
            self.artifacts.append(artifact_path)
            self.updated_at = get_timestamp()

    def add_notes(self, note: str) -> None:
        """Add notes to task."""
        if self.notes:
            self.notes += f"\n\n{note}"
        else:
            self.notes = note
        self.updated_at = get_timestamp()

    def save(self, file_path: str) -> None:
        """Save task to YAML file."""
        save_yaml(self.to_dict(), file_path)
        logger.info(f"Task {self.id} saved to {file_path}")

    @classmethod
    def load(cls, file_path: str) -> 'Task':
        """Load task from YAML file."""
        data = load_yaml(file_path)
        task = cls.from_dict(data)
        logger.info(f"Task {task.id} loaded from {file_path}")
        return task

    def __str__(self) -> str:
        """String representation of task."""
        return f"Task({self.id}: {self.title} [{self.status}])"
