"""Interactive mode for CLI with wizards."""

import uuid
from typing import Optional, List

from ..core.config import Config
from ..core.plan import Plan, PlanStatus
from ..core.task import Task, TaskStatus, TaskPriority
from .formatters import Formatter


class InteractiveMode:
    """Interactive mode for creating plans and tasks."""

    def __init__(self, config: Config, formatter: Formatter):
        """Initialize interactive mode."""
        self.config = config
        self.formatter = formatter

    def _input(self, prompt: str, default: Optional[str] = None) -> str:
        """Get user input with optional default."""
        if default:
            prompt = f"{prompt} [{default}]"

        value = input(f"{prompt}: ").strip()

        if not value and default:
            return default

        return value

    def _input_list(self, prompt: str, item_name: str = "item") -> List[str]:
        """Get list of items from user."""
        print(f"\n{prompt}")
        print(f"Enter {item_name}s (one per line, empty line to finish):")

        items = []
        while True:
            value = input(f"  {len(items) + 1}. ").strip()
            if not value:
                break
            items.append(value)

        return items

    def _confirm(self, prompt: str, default: bool = False) -> bool:
        """Get confirmation from user."""
        default_str = "Y/n" if default else "y/N"
        response = input(f"{prompt} [{default_str}]: ").strip().lower()

        if not response:
            return default

        return response in ['y', 'yes']

    def _select(self, prompt: str, options: List[str], default: Optional[str] = None) -> str:
        """Select from list of options."""
        print(f"\n{prompt}")
        for i, option in enumerate(options, 1):
            default_marker = " (default)" if option == default else ""
            print(f"  {i}. {option}{default_marker}")

        while True:
            choice = input("Select (number or name): ").strip()

            if not choice and default:
                return default

            # Try by number
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            except ValueError:
                pass

            # Try by name
            if choice in options:
                return choice

            print("Invalid choice. Try again.")

    def create_plan_wizard(self) -> Optional[Plan]:
        """Interactive wizard to create a new plan."""
        self.formatter.print_header("Create New Plan")
        print("\nThis wizard will guide you through creating a new plan.\n")

        # Basic info
        name = self._input("Plan name (lowercase, hyphen-separated)")
        if not name:
            self.formatter.print_error("Plan name is required")
            return None

        # Check if plan already exists
        if self.config.plan_exists(name):
            self.formatter.print_error(f"Plan '{name}' already exists")
            return None

        brief = self._input("Brief description (128 chars max)")
        author = self._input("Author name", default="")

        # Version
        version = self._input("Version", default="1.0.0")

        # Tags
        if self._confirm("Add tags?", default=False):
            tags = []
            while True:
                tag = self._input("Tag (empty to finish)").strip()
                if not tag:
                    break
                tags.append(tag)
        else:
            tags = []

        # Objectives
        if self._confirm("Add objectives?", default=True):
            objectives = self._input_list("Objectives", "objective")
        else:
            objectives = []

        # Deliverables
        if self._confirm("Add deliverables?", default=True):
            deliverables = self._input_list("Deliverables", "deliverable")
        else:
            deliverables = []

        # Create plan
        plan = Plan(
            name=name,
            brief=brief,
            author=author,
            version=version,
            tags=tags,
            objectives=objectives,
            deliverables=deliverables,
            status=PlanStatus.DRAFT
        )

        # Create PRD?
        if self._confirm("Create PRD file?", default=True):
            prd_content = f"""# {name.replace('-', ' ').title()}

## Overview
{brief}

## Objectives
"""
            for obj in objectives:
                prd_content += f"- {obj}\n"

            prd_content += "\n## Deliverables\n"
            for deliv in deliverables:
                prd_content += f"- {deliv}\n"

            prd_content += """
## Requirements

### Functional Requirements
(To be defined)

### Non-Functional Requirements
(To be defined)

## Technical Design
(To be defined)

## Implementation Plan
(To be defined)
"""

            # Save PRD
            prd_file = self.config.get_prd_file(name)
            prd_file.parent.mkdir(parents=True, exist_ok=True)
            prd_file.write_text(prd_content, encoding='utf-8')
            self.formatter.print_success(f"PRD created at {prd_file}")

        return plan

    def create_task_wizard(self, plan: Plan) -> Optional[Task]:
        """Interactive wizard to create a new task."""
        self.formatter.print_header(f"Create New Task for Plan: {plan.name}")
        print("\nThis wizard will guide you through creating a new task.\n")

        # Basic info
        title = self._input("Task title")
        if not title:
            self.formatter.print_error("Task title is required")
            return None

        description = self._input("Task description (optional)")

        # Priority
        priority_str = self._select(
            "Select priority",
            ['critical', 'high', 'medium', 'low'],
            default='medium'
        )
        priority = TaskPriority(priority_str)

        # Estimated hours
        estimated_hours_str = self._input("Estimated hours", default="0")
        try:
            estimated_hours = float(estimated_hours_str)
        except ValueError:
            estimated_hours = 0.0

        # Order
        existing_tasks = plan.get_tasks()
        default_order = len(existing_tasks) + 1
        order_str = self._input(f"Task order", default=str(default_order))
        try:
            order = int(order_str)
        except ValueError:
            order = default_order

        # Dependencies
        requires = []
        if existing_tasks and self._confirm("Add dependencies?", default=False):
            print("\nAvailable tasks:")
            for task in existing_tasks:
                print(f"  - {task.id[:8]}: {task.title}")

            requires = self._input_list("Dependencies (task IDs)", "dependency")

        # Assigned to
        assigned_to = self._input("Assign to (optional)", default="")

        # Create task
        task = Task(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            priority=priority,
            estimated_hours=estimated_hours,
            order=order,
            requires=requires,
            assigned_to=assigned_to if assigned_to else None,
            status=TaskStatus.PENDING
        )

        return task

    def edit_plan_wizard(self, plan: Plan) -> bool:
        """Interactive wizard to edit a plan."""
        self.formatter.print_header(f"Edit Plan: {plan.name}")
        self.formatter.print_plan_details(plan)

        print("\nWhat would you like to edit?")
        print("  1. Brief description")
        print("  2. Author")
        print("  3. Tags")
        print("  4. Objectives")
        print("  5. Deliverables")
        print("  6. Status")
        print("  0. Cancel")

        choice = input("\nSelect: ").strip()

        if choice == "1":
            new_brief = self._input("New brief description", default=plan.brief)
            plan.brief = new_brief
            return True

        elif choice == "2":
            new_author = self._input("New author", default=plan.author or "")
            plan.author = new_author
            return True

        elif choice == "3":
            if self._confirm("Replace all tags?"):
                tags = self._input_list("Tags", "tag")
                plan.tags = tags
            else:
                if self._confirm("Add new tags?"):
                    new_tags = self._input_list("New tags", "tag")
                    plan.tags.extend(new_tags)
            return True

        elif choice == "4":
            if self._confirm("Replace all objectives?"):
                objectives = self._input_list("Objectives", "objective")
                plan.objectives = objectives
            else:
                if self._confirm("Add new objectives?"):
                    new_objs = self._input_list("New objectives", "objective")
                    plan.objectives.extend(new_objs)
            return True

        elif choice == "5":
            if self._confirm("Replace all deliverables?"):
                deliverables = self._input_list("Deliverables", "deliverable")
                plan.deliverables = deliverables
            else:
                if self._confirm("Add new deliverables?"):
                    new_delivs = self._input_list("New deliverables", "deliverable")
                    plan.deliverables.extend(new_delivs)
            return True

        elif choice == "6":
            status_options = ['draft', 'pending', 'approved', 'executing', 'completed', 'failed', 'cancelled']
            new_status_str = self._select("Select new status", status_options, default=str(plan.status))
            plan.status = PlanStatus(new_status_str)
            return True

        return False
