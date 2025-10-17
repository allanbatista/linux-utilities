"""
Project Manager - Professional CLI for managing projects with plans and tasks.

Version: 1.0.0
"""

__version__ = '1.0.0'
__author__ = 'Project Manager Team'

from .core.config import Config
from .core.plan import Plan, PlanStatus
from .core.task import Task, TaskStatus, TaskPriority
from .core.validator import Validator

__all__ = [
    'Config',
    'Plan',
    'PlanStatus',
    'Task',
    'TaskStatus',
    'TaskPriority',
    'Validator',
]
