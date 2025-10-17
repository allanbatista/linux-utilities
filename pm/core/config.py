"""Configuration management for project manager."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..utils.helpers import load_yaml, save_yaml, ensure_dir


@dataclass
class Config:
    """
    Global configuration for project manager.

    Manages workspace paths and configuration settings.
    """

    workspace_dir: str = '.project-manager'
    plans_dir: str = 'plans'
    logs_dir: str = 'logs'
    config_file: str = 'config.yaml'

    # Runtime settings
    verbose: bool = False
    quiet: bool = False
    no_color: bool = False

    def __post_init__(self):
        """Ensure all directories exist."""
        self._workspace_path = Path(self.workspace_dir)
        self._plans_path = self._workspace_path / self.plans_dir
        self._logs_path = self._workspace_path / self.logs_dir
        self._config_path = self._workspace_path / self.config_file

    @property
    def workspace_path(self) -> Path:
        """Get workspace path."""
        return self._workspace_path

    @property
    def plans_path(self) -> Path:
        """Get plans directory path."""
        return self._plans_path

    @property
    def logs_path(self) -> Path:
        """Get logs directory path."""
        return self._logs_path

    @property
    def config_path(self) -> Path:
        """Get config file path."""
        return self._config_path

    def get_plan_dir(self, plan_name: str) -> Path:
        """Get directory for a specific plan."""
        return self._plans_path / plan_name

    def get_plan_file(self, plan_name: str) -> Path:
        """Get plan.yaml file path."""
        return self.get_plan_dir(plan_name) / 'plan.yaml'

    def get_prd_file(self, plan_name: str) -> Path:
        """Get PRD markdown file path."""
        return self.get_plan_dir(plan_name) / 'prd.md'

    def get_tasks_dir(self, plan_name: str) -> Path:
        """Get tasks directory for a plan."""
        return self.get_plan_dir(plan_name) / 'tasks'

    def get_task_file(self, plan_name: str, task_id: str) -> Path:
        """Get task YAML file path."""
        return self.get_tasks_dir(plan_name) / f'task-{task_id}.yaml'

    def get_plan_log_dir(self, plan_name: str) -> Path:
        """Get log directory for a plan."""
        return self._logs_path / plan_name

    def get_execution_log(self, plan_name: str) -> Path:
        """Get execution log file path."""
        return self.get_plan_log_dir(plan_name) / 'execution.log'

    def init_workspace(self) -> None:
        """Initialize workspace structure."""
        ensure_dir(str(self._workspace_path))
        ensure_dir(str(self._plans_path))
        ensure_dir(str(self._logs_path))

        # Create default config if it doesn't exist
        if not self._config_path.exists():
            default_config = {
                'version': '1.0.0',
                'workspace_dir': self.workspace_dir,
                'plans_dir': self.plans_dir,
                'logs_dir': self.logs_dir,
                'settings': {
                    'default_priority': 'medium',
                    'auto_approve': False,
                    'require_prd': True
                }
            }
            save_yaml(default_config, str(self._config_path))

        # Create .gitignore if it doesn't exist
        gitignore_path = self._workspace_path / '.gitignore'
        if not gitignore_path.exists():
            gitignore_content = """# Project Manager - Ignore logs
logs/
*.log
"""
            gitignore_path.write_text(gitignore_content, encoding='utf-8')

    def workspace_exists(self) -> bool:
        """Check if workspace is initialized."""
        return self._workspace_path.exists() and self._config_path.exists()

    def plan_exists(self, plan_name: str) -> bool:
        """Check if a plan exists."""
        return self.get_plan_file(plan_name).exists()

    def list_plans(self) -> list[str]:
        """List all plan names in workspace."""
        if not self._plans_path.exists():
            return []

        plans = []
        for item in self._plans_path.iterdir():
            if item.is_dir():
                plan_file = item / 'plan.yaml'
                if plan_file.exists():
                    plans.append(item.name)

        return sorted(plans)

    def load_config_file(self) -> dict:
        """Load configuration from file."""
        if self._config_path.exists():
            return load_yaml(str(self._config_path))
        return {}

    def save_config_file(self, config_data: dict) -> None:
        """Save configuration to file."""
        save_yaml(config_data, str(self._config_path))

    @classmethod
    def from_args(cls, **kwargs) -> 'Config':
        """Create config from command-line arguments."""
        return cls(**{k: v for k, v in kwargs.items() if v is not None})
