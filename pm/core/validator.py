"""Validation system for plans and tasks."""

from typing import List, Set, Dict, Tuple, Optional
from dataclasses import dataclass

from .plan import Plan
from .task import Task, TaskStatus
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationError:
    """Validation error information."""
    severity: str  # 'error', 'warning', 'info'
    message: str
    context: Optional[Dict] = None


@dataclass
class ValidationResult:
    """Result of validation."""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]

    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0

    def get_all_issues(self) -> List[ValidationError]:
        """Get all issues (errors and warnings)."""
        return self.errors + self.warnings


class Validator:
    """Validator for plans and tasks."""

    @staticmethod
    def detect_circular_dependencies(tasks: List[Task]) -> List[List[str]]:
        """
        Detect circular dependencies in tasks.

        Returns:
            List of cycles, where each cycle is a list of task IDs
        """
        # Build dependency graph
        graph: Dict[str, List[str]] = {task.id: task.requires for task in tasks}

        cycles = []
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        path: List[str] = []

        def dfs(node: str) -> bool:
            """DFS to detect cycles."""
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            # Visit all dependencies
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)
                    return True

            path.pop()
            rec_stack.remove(node)
            return False

        # Check all nodes
        for task_id in graph:
            if task_id not in visited:
                dfs(task_id)

        return cycles

    @staticmethod
    def validate_task_dependencies(task: Task, all_tasks: List[Task]) -> ValidationResult:
        """
        Validate task dependencies.

        Checks:
        - All required tasks exist
        - No circular dependencies
        - Blocked tasks exist
        """
        errors = []
        warnings = []

        task_ids = {t.id for t in all_tasks}

        # Check if required tasks exist
        for req_id in task.requires:
            if req_id not in task_ids:
                errors.append(ValidationError(
                    severity='error',
                    message=f"Task {task.id} requires non-existent task {req_id}",
                    context={'task_id': task.id, 'missing_dependency': req_id}
                ))

        # Check if blocked tasks exist
        for blocked_id in task.blocks:
            if blocked_id not in task_ids:
                errors.append(ValidationError(
                    severity='error',
                    message=f"Task {task.id} blocks non-existent task {blocked_id}",
                    context={'task_id': task.id, 'missing_blocked': blocked_id}
                ))

        # Check for circular dependencies
        cycles = Validator.detect_circular_dependencies(all_tasks)
        for cycle in cycles:
            if task.id in cycle:
                errors.append(ValidationError(
                    severity='error',
                    message=f"Circular dependency detected: {' -> '.join(cycle)}",
                    context={'task_id': task.id, 'cycle': cycle}
                ))

        # Check if task has too many dependencies
        if len(task.requires) > 10:
            warnings.append(ValidationError(
                severity='warning',
                message=f"Task {task.id} has {len(task.requires)} dependencies (consider breaking it down)",
                context={'task_id': task.id, 'dependency_count': len(task.requires)}
            ))

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    @staticmethod
    def validate_plan(plan: Plan) -> ValidationResult:
        """
        Validate entire plan.

        Checks:
        - Plan has tasks
        - All task dependencies are valid
        - Plan status is consistent with task statuses
        - Required fields are present
        """
        errors = []
        warnings = []

        # Check if plan has name
        if not plan.name or not plan.name.strip():
            errors.append(ValidationError(
                severity='error',
                message="Plan must have a name",
                context={'plan_id': plan.id}
            ))

        # Check if plan has tasks
        tasks = plan.get_tasks()
        if len(tasks) == 0:
            warnings.append(ValidationError(
                severity='warning',
                message=f"Plan {plan.name} has no tasks",
                context={'plan_name': plan.name}
            ))
        else:
            # Validate all task dependencies
            for task in tasks:
                task_result = Validator.validate_task_dependencies(task, tasks)
                errors.extend(task_result.errors)
                warnings.extend(task_result.warnings)

            # Check plan status consistency
            all_completed = all(t.status == TaskStatus.COMPLETED for t in tasks)
            any_failed = any(t.status == TaskStatus.FAILED for t in tasks)

            if all_completed and plan.status not in ['completed', 'cancelled']:
                warnings.append(ValidationError(
                    severity='warning',
                    message=f"Plan {plan.name}: All tasks completed but plan status is {plan.status}",
                    context={'plan_name': plan.name, 'plan_status': str(plan.status)}
                ))

            if any_failed and plan.status not in ['failed', 'cancelled']:
                warnings.append(ValidationError(
                    severity='warning',
                    message=f"Plan {plan.name}: Some tasks failed but plan status is {plan.status}",
                    context={'plan_name': plan.name, 'plan_status': str(plan.status)}
                ))

        # Check if objectives are defined
        if not plan.objectives:
            warnings.append(ValidationError(
                severity='warning',
                message=f"Plan {plan.name} has no objectives defined",
                context={'plan_name': plan.name}
            ))

        # Check if deliverables are defined
        if not plan.deliverables:
            warnings.append(ValidationError(
                severity='warning',
                message=f"Plan {plan.name} has no deliverables defined",
                context={'plan_name': plan.name}
            ))

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    @staticmethod
    def check_task_ready_to_execute(task: Task, all_tasks: List[Task]) -> Tuple[bool, Optional[str]]:
        """
        Check if a task is ready to execute.

        Returns:
            (is_ready, reason) - reason is None if ready, otherwise explains why not
        """
        if task.status == TaskStatus.COMPLETED:
            return False, "Task already completed"

        if task.status == TaskStatus.FAILED:
            return False, "Task has failed"

        if task.status == TaskStatus.BLOCKED:
            return False, "Task is blocked"

        # Check dependencies
        completed_task_ids = [t.id for t in all_tasks if t.status == TaskStatus.COMPLETED]

        for req_id in task.requires:
            if req_id not in completed_task_ids:
                # Find the required task
                req_task = next((t for t in all_tasks if t.id == req_id), None)
                if req_task:
                    return False, f"Waiting for task {req_id} ({req_task.title})"
                else:
                    return False, f"Dependency {req_id} not found"

        return True, None

    @staticmethod
    def find_blocked_tasks(tasks: List[Task]) -> List[Tuple[Task, str]]:
        """
        Find tasks that are blocked and the reason.

        Returns:
            List of (task, reason) tuples
        """
        blocked = []

        for task in tasks:
            if task.status == TaskStatus.BLOCKED:
                blocked.append((task, "Manually marked as blocked"))
                continue

            is_ready, reason = Validator.check_task_ready_to_execute(task, tasks)
            if not is_ready and reason and "Waiting for" in reason:
                blocked.append((task, reason))

        return blocked

    @staticmethod
    def suggest_next_tasks(plan: Plan) -> List[Task]:
        """
        Suggest which tasks should be executed next.

        Returns tasks that are:
        - Not completed/failed/blocked
        - Have all dependencies satisfied
        - Ordered by priority
        """
        tasks = plan.get_tasks()
        ready_tasks = []

        for task in tasks:
            is_ready, _ = Validator.check_task_ready_to_execute(task, tasks)
            if is_ready:
                ready_tasks.append(task)

        # Sort by priority (critical first) and order
        priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        ready_tasks.sort(key=lambda t: (priority_order.get(str(t.priority), 2), t.order))

        return ready_tasks
