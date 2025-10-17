"""Output formatters for CLI with rich formatting."""

from typing import List, Optional
from datetime import datetime

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
    from rich.panel import Panel
    from rich.text import Text
    from rich.tree import Tree
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from ..core.plan import Plan, PlanStatus
from ..core.task import Task, TaskStatus, TaskPriority
from ..core.validator import ValidationResult
from ..utils.helpers import truncate_text


class Formatter:
    """Output formatter for CLI."""

    def __init__(self, no_color: bool = False):
        """Initialize formatter."""
        self.no_color = no_color
        if RICH_AVAILABLE and not no_color:
            self.console = Console()
        else:
            self.console = None

    def print(self, text: str, style: Optional[str] = None) -> None:
        """Print text with optional style."""
        if self.console:
            self.console.print(text, style=style)
        else:
            print(text)

    def print_success(self, message: str) -> None:
        """Print success message."""
        if self.console:
            self.console.print(f"✓ {message}", style="bold green")
        else:
            print(f"✓ {message}")

    def print_error(self, message: str) -> None:
        """Print error message."""
        if self.console:
            self.console.print(f"✗ {message}", style="bold red")
        else:
            print(f"✗ {message}")

    def print_warning(self, message: str) -> None:
        """Print warning message."""
        if self.console:
            self.console.print(f"⚠ {message}", style="bold yellow")
        else:
            print(f"⚠ {message}")

    def print_info(self, message: str) -> None:
        """Print info message."""
        if self.console:
            self.console.print(f"ℹ {message}", style="blue")
        else:
            print(f"ℹ {message}")

    def print_header(self, title: str) -> None:
        """Print section header."""
        if self.console:
            self.console.print(f"\n[bold cyan]{title}[/bold cyan]")
            self.console.print("─" * len(title))
        else:
            print(f"\n{title}")
            print("─" * len(title))

    def format_status(self, status: str) -> str:
        """Format status with color."""
        status_colors = {
            'draft': 'white',
            'pending': 'yellow',
            'ready': 'cyan',
            'approved': 'blue',
            'executing': 'magenta',
            'completed': 'green',
            'failed': 'red',
            'blocked': 'red',
            'cancelled': 'dim'
        }

        status_icons = {
            'draft': '📝',
            'pending': '⏳',
            'ready': '🔵',
            'approved': '✅',
            'executing': '🔄',
            'completed': '✅',
            'failed': '❌',
            'blocked': '🚫',
            'cancelled': '⛔'
        }

        color = status_colors.get(status, 'white')
        icon = status_icons.get(status, '❓')

        if self.console:
            return f"[{color}]{icon} {status.upper()}[/{color}]"
        else:
            return f"{icon} {status.upper()}"

    def format_priority(self, priority: str) -> str:
        """Format priority with color."""
        priority_colors = {
            'critical': 'bold red',
            'high': 'red',
            'medium': 'yellow',
            'low': 'green'
        }

        priority_icons = {
            'critical': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🟢'
        }

        color = priority_colors.get(priority, 'white')
        icon = priority_icons.get(priority, '⚪')

        if self.console:
            return f"[{color}]{icon} {priority.upper()}[/{color}]"
        else:
            return f"{icon} {priority.upper()}"

    def print_plan_list(self, plans: List[Plan]) -> None:
        """Print list of plans in table format."""
        if not plans:
            self.print_info("No plans found")
            return

        if self.console:
            table = Table(title="Plans", box=box.ROUNDED, show_lines=False)
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Status", justify="center")
            table.add_column("Progress", justify="center")
            table.add_column("Tasks", justify="center")
            table.add_column("Brief", style="dim")

            for plan in plans:
                tasks_summary = plan._calculate_tasks_summary()
                total = tasks_summary['total']
                completed = tasks_summary['completed']

                table.add_row(
                    plan.name,
                    self.format_status(str(plan.status)),
                    f"{plan.progress}%",
                    f"{completed}/{total}",
                    truncate_text(plan.brief, 50)
                )

            self.console.print(table)
        else:
            # Fallback to simple text
            print("\nPlans:")
            print("-" * 80)
            for plan in plans:
                print(f"  {plan.name} [{plan.status}] - {plan.brief}")

    def print_plan_details(self, plan: Plan) -> None:
        """Print detailed plan information."""
        if self.console:
            # Plan header
            self.console.print(Panel(
                f"[bold cyan]{plan.name}[/bold cyan]\n"
                f"[dim]{plan.brief}[/dim]",
                title="Plan Details",
                border_style="cyan"
            ))

            # Metadata
            table = Table(box=box.SIMPLE, show_header=False)
            table.add_column("Field", style="bold")
            table.add_column("Value")

            table.add_row("Status", self.format_status(str(plan.status)))
            table.add_row("Progress", f"{plan.progress}%")
            table.add_row("Version", plan.version)
            if plan.author:
                table.add_row("Author", plan.author)
            if plan.tags:
                table.add_row("Tags", ", ".join(plan.tags))
            table.add_row("Created", plan.created_at or "N/A")
            if plan.is_approved:
                table.add_row("Approved by", plan.approved_by or "N/A")
                table.add_row("Approved at", plan.approved_at or "N/A")

            self.console.print(table)

            # Objectives
            if plan.objectives:
                self.print_header("Objectives")
                for i, obj in enumerate(plan.objectives, 1):
                    self.console.print(f"  {i}. {obj}")

            # Deliverables
            if plan.deliverables:
                self.print_header("Deliverables")
                for i, deliv in enumerate(plan.deliverables, 1):
                    self.console.print(f"  {i}. {deliv}")

        else:
            # Fallback
            print(f"\nPlan: {plan.name}")
            print(f"Brief: {plan.brief}")
            print(f"Status: {plan.status}")
            print(f"Progress: {plan.progress}%")

    def print_task_list(self, tasks: List[Task]) -> None:
        """Print list of tasks in table format."""
        if not tasks:
            self.print_info("No tasks found")
            return

        if self.console:
            table = Table(title="Tasks", box=box.ROUNDED, show_lines=False)
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Title", style="white")
            table.add_column("Status", justify="center")
            table.add_column("Priority", justify="center")
            table.add_column("Progress", justify="center")
            table.add_column("Assigned", style="dim")

            for task in tasks:
                table.add_row(
                    task.id[:8],
                    truncate_text(task.title, 40),
                    self.format_status(str(task.status)),
                    self.format_priority(str(task.priority)),
                    f"{task.progress}%",
                    task.assigned_to or "-"
                )

            self.console.print(table)
        else:
            # Fallback
            print("\nTasks:")
            print("-" * 80)
            for task in tasks:
                print(f"  [{task.id[:8]}] {task.title} - {task.status}")

    def print_task_details(self, task: Task) -> None:
        """Print detailed task information."""
        if self.console:
            # Task header
            self.console.print(Panel(
                f"[bold cyan]{task.title}[/bold cyan]\n"
                f"[dim]ID: {task.id}[/dim]",
                title="Task Details",
                border_style="cyan"
            ))

            # Metadata
            table = Table(box=box.SIMPLE, show_header=False)
            table.add_column("Field", style="bold")
            table.add_column("Value")

            table.add_row("Status", self.format_status(str(task.status)))
            table.add_row("Priority", self.format_priority(str(task.priority)))
            table.add_row("Progress", f"{task.progress}%")
            table.add_row("Estimated Hours", str(task.estimated_hours))
            if task.assigned_to:
                table.add_row("Assigned to", task.assigned_to)
            table.add_row("Created", task.created_at or "N/A")

            self.console.print(table)

            # Description
            if task.description:
                self.print_header("Description")
                self.console.print(task.description)

            # Dependencies
            if task.requires:
                self.print_header("Dependencies")
                for dep in task.requires:
                    self.console.print(f"  • {dep}")

            # Notes
            if task.notes:
                self.print_header("Notes")
                self.console.print(task.notes)

        else:
            # Fallback
            print(f"\nTask: {task.title}")
            print(f"ID: {task.id}")
            print(f"Status: {task.status}")
            print(f"Priority: {task.priority}")
            print(f"Progress: {task.progress}%")

    def print_validation_result(self, result: ValidationResult) -> None:
        """Print validation result."""
        if result.is_valid:
            self.print_success("Validation passed!")
        else:
            self.print_error(f"Validation failed with {len(result.errors)} error(s)")

        # Print errors
        for error in result.errors:
            self.print_error(error.message)

        # Print warnings
        for warning in result.warnings:
            self.print_warning(warning.message)

    def print_progress_bar(self, current: int, total: int, description: str = "") -> None:
        """Print progress bar."""
        if total == 0:
            return

        percentage = (current / total) * 100

        if self.console:
            bar_length = 30
            filled = int(bar_length * current / total)
            bar = "█" * filled + "░" * (bar_length - filled)
            self.console.print(
                f"{description} [{bar}] {current}/{total} ({percentage:.1f}%)",
                style="cyan"
            )
        else:
            print(f"{description} {current}/{total} ({percentage:.1f}%)")
