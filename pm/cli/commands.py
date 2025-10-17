"""CLI commands implementation using click."""

import sys
import click
from pathlib import Path

from ..core.config import Config
from ..core.plan import Plan, PlanStatus
from ..core.task import Task, TaskStatus, TaskPriority
from ..core.validator import Validator
from ..utils.logger import setup_logger
from .formatters import Formatter
from .interactive import InteractiveMode


# Global options
@click.group()
@click.version_option(version='1.0.0', prog_name='pm')
@click.option('-c', '--config', type=click.Path(), help='Path to config file')
@click.option('-v', '--verbose', is_flag=True, help='Verbose output')
@click.option('-q', '--quiet', is_flag=True, help='Quiet mode')
@click.option('--no-color', is_flag=True, help='Disable colored output')
@click.pass_context
def cli(ctx, config, verbose, quiet, no_color):
    """Project Manager - Professional CLI for managing projects with plans and tasks."""
    # Initialize context
    ctx.ensure_object(dict)

    # Create config
    cfg = Config(no_color=no_color, verbose=verbose, quiet=quiet)
    ctx.obj['config'] = cfg

    # Create formatter
    formatter = Formatter(no_color=no_color)
    ctx.obj['formatter'] = formatter

    # Setup logger
    if verbose:
        log_level = 10  # DEBUG
    elif quiet:
        log_level = 40  # ERROR
    else:
        log_level = 20  # INFO

    logger = setup_logger(log_to_console=not quiet, level=log_level)
    ctx.obj['logger'] = logger


# =====================
# init command
# =====================
@cli.command()
@click.pass_context
def init(ctx):
    """Initialize workspace for project manager."""
    config: Config = ctx.obj['config']
    formatter: Formatter = ctx.obj['formatter']

    if config.workspace_exists():
        formatter.print_warning("Workspace already initialized")
        return

    try:
        config.init_workspace()
        formatter.print_success(f"Workspace initialized at {config.workspace_path}")
        formatter.print_info(f"Plans directory: {config.plans_path}")
        formatter.print_info(f"Logs directory: {config.logs_path}")
        formatter.print_info(f"Config file: {config.config_path}")
    except Exception as e:
        formatter.print_error(f"Failed to initialize workspace: {e}")
        sys.exit(1)


# =====================
# plan commands
# =====================
@cli.group()
@click.pass_context
def plan(ctx):
    """Manage plans."""
    pass


@plan.command('list')
@click.option('-s', '--status', type=str, help='Filter by status')
@click.option('-t', '--tag', type=str, help='Filter by tag')
@click.pass_context
def plan_list(ctx, status, tag):
    """List all plans."""
    config: Config = ctx.obj['config']
    formatter: Formatter = ctx.obj['formatter']

    if not config.workspace_exists():
        formatter.print_error("Workspace not initialized. Run 'pm init' first.")
        sys.exit(1)

    try:
        plan_names = config.list_plans()

        if not plan_names:
            formatter.print_info("No plans found")
            return

        plans = []
        for plan_name in plan_names:
            p = Plan.load(plan_name, config)

            # Apply filters
            if status and str(p.status) != status:
                continue

            if tag and tag not in p.tags:
                continue

            plans.append(p)

        formatter.print_plan_list(plans)

    except Exception as e:
        formatter.print_error(f"Failed to list plans: {e}")
        sys.exit(1)


@plan.command('create')
@click.option('--interactive/--no-interactive', default=True, help='Interactive mode')
@click.option('--name', type=str, help='Plan name')
@click.option('--brief', type=str, help='Brief description')
@click.pass_context
def plan_create(ctx, interactive, name, brief):
    """Create a new plan."""
    config: Config = ctx.obj['config']
    formatter: Formatter = ctx.obj['formatter']

    if not config.workspace_exists():
        formatter.print_error("Workspace not initialized. Run 'pm init' first.")
        sys.exit(1)

    try:
        if interactive:
            # Interactive wizard
            wizard = InteractiveMode(config, formatter)
            new_plan = wizard.create_plan_wizard()

            if new_plan is None:
                formatter.print_warning("Plan creation cancelled")
                return

        else:
            # Non-interactive mode
            if not name:
                formatter.print_error("Plan name is required in non-interactive mode")
                sys.exit(1)

            new_plan = Plan(
                name=name,
                brief=brief or "",
                status=PlanStatus.DRAFT
            )

        # Save plan
        new_plan.save(config)
        formatter.print_success(f"Plan '{new_plan.name}' created successfully")

    except Exception as e:
        formatter.print_error(f"Failed to create plan: {e}")
        sys.exit(1)


@plan.command('show')
@click.argument('plan_name')
@click.option('--tasks', is_flag=True, help='Show tasks')
@click.pass_context
def plan_show(ctx, plan_name, tasks):
    """Show plan details."""
    config: Config = ctx.obj['config']
    formatter: Formatter = ctx.obj['formatter']

    if not config.workspace_exists():
        formatter.print_error("Workspace not initialized. Run 'pm init' first.")
        sys.exit(1)

    try:
        p = Plan.load(plan_name, config)
        formatter.print_plan_details(p)

        if tasks:
            formatter.print_header("Tasks")
            task_list = p.get_tasks()
            formatter.print_task_list(task_list)

    except FileNotFoundError:
        formatter.print_error(f"Plan '{plan_name}' not found")
        sys.exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to show plan: {e}")
        sys.exit(1)


@plan.command('edit')
@click.argument('plan_name')
@click.pass_context
def plan_edit(ctx, plan_name):
    """Edit plan (interactive)."""
    config: Config = ctx.obj['config']
    formatter: Formatter = ctx.obj['formatter']

    if not config.workspace_exists():
        formatter.print_error("Workspace not initialized. Run 'pm init' first.")
        sys.exit(1)

    try:
        p = Plan.load(plan_name, config)

        wizard = InteractiveMode(config, formatter)
        if wizard.edit_plan_wizard(p):
            p.save(config)
            formatter.print_success(f"Plan '{plan_name}' updated successfully")
        else:
            formatter.print_info("No changes made")

    except FileNotFoundError:
        formatter.print_error(f"Plan '{plan_name}' not found")
        sys.exit(1)
    except Exception as e:
        formatter.print_error(f"Failed to edit plan: {e}")
        sys.exit(1)


@plan.command('approve')
@click.argument('plan_name')
@click.option('--by', 'approved_by', required=True, help='Approver name')
@click.pass_context
def plan_approve(ctx, plan_name, approved_by):
    """Approve plan for execution."""
    config: Config = ctx.obj['config']
    formatter: Formatter = ctx.obj['formatter']

    try:
        p = Plan.load(plan_name, config)
        p.approve(approved_by)
        p.save(config)
        formatter.print_success(f"Plan '{plan_name}' approved by {approved_by}")

    except Exception as e:
        formatter.print_error(f"Failed to approve plan: {e}")
        sys.exit(1)


@plan.command('delete')
@click.argument('plan_name')
@click.option('--yes', is_flag=True, help='Skip confirmation')
@click.pass_context
def plan_delete(ctx, plan_name, yes):
    """Delete a plan."""
    config: Config = ctx.obj['config']
    formatter: Formatter = ctx.obj['formatter']

    if not yes:
        confirm = input(f"Are you sure you want to delete plan '{plan_name}'? [y/N]: ")
        if confirm.lower() not in ['y', 'yes']:
            formatter.print_info("Deletion cancelled")
            return

    try:
        plan_dir = config.get_plan_dir(plan_name)
        if plan_dir.exists():
            import shutil
            shutil.rmtree(plan_dir)
            formatter.print_success(f"Plan '{plan_name}' deleted")
        else:
            formatter.print_error(f"Plan '{plan_name}' not found")

    except Exception as e:
        formatter.print_error(f"Failed to delete plan: {e}")
        sys.exit(1)


# =====================
# task commands
# =====================
@cli.group()
@click.pass_context
def task(ctx):
    """Manage tasks."""
    pass


@task.command('list')
@click.argument('plan_name')
@click.option('-s', '--status', type=str, help='Filter by status')
@click.option('--unassigned', is_flag=True, help='Show only unassigned tasks')
@click.pass_context
def task_list(ctx, plan_name, status, unassigned):
    """List tasks in a plan."""
    config: Config = ctx.obj['config']
    formatter: Formatter = ctx.obj['formatter']

    try:
        p = Plan.load(plan_name, config)
        tasks = p.get_tasks()

        # Apply filters
        if status:
            tasks = [t for t in tasks if str(t.status) == status]

        if unassigned:
            tasks = [t for t in tasks if not t.assigned_to]

        formatter.print_task_list(tasks)

    except Exception as e:
        formatter.print_error(f"Failed to list tasks: {e}")
        sys.exit(1)


@task.command('create')
@click.argument('plan_name')
@click.option('--interactive/--no-interactive', default=True, help='Interactive mode')
@click.option('--title', type=str, help='Task title')
@click.option('--priority', type=click.Choice(['critical', 'high', 'medium', 'low']), help='Task priority')
@click.pass_context
def task_create(ctx, plan_name, interactive, title, priority):
    """Create a new task in a plan."""
    config: Config = ctx.obj['config']
    formatter: Formatter = ctx.obj['formatter']

    try:
        p = Plan.load(plan_name, config)

        if interactive:
            wizard = InteractiveMode(config, formatter)
            new_task = wizard.create_task_wizard(p)

            if new_task is None:
                formatter.print_warning("Task creation cancelled")
                return
        else:
            if not title:
                formatter.print_error("Task title is required in non-interactive mode")
                sys.exit(1)

            import uuid
            new_task = Task(
                id=str(uuid.uuid4()),
                title=title,
                priority=TaskPriority(priority) if priority else TaskPriority.MEDIUM
            )

        # Add task to plan
        p.add_task(new_task)
        p.save(config)

        formatter.print_success(f"Task '{new_task.title}' created successfully")

    except Exception as e:
        formatter.print_error(f"Failed to create task: {e}")
        sys.exit(1)


@task.command('show')
@click.argument('plan_name')
@click.argument('task_id')
@click.pass_context
def task_show(ctx, plan_name, task_id):
    """Show task details."""
    config: Config = ctx.obj['config']
    formatter: Formatter = ctx.obj['formatter']

    try:
        p = Plan.load(plan_name, config)
        t = p.get_task(task_id)

        if not t:
            formatter.print_error(f"Task '{task_id}' not found")
            sys.exit(1)

        formatter.print_task_details(t)

    except Exception as e:
        formatter.print_error(f"Failed to show task: {e}")
        sys.exit(1)


@task.command('start')
@click.argument('plan_name')
@click.argument('task_id')
@click.pass_context
def task_start(ctx, plan_name, task_id):
    """Start task execution."""
    config: Config = ctx.obj['config']
    formatter: Formatter = ctx.obj['formatter']

    try:
        p = Plan.load(plan_name, config)
        t = p.get_task(task_id)

        if not t:
            formatter.print_error(f"Task '{task_id}' not found")
            sys.exit(1)

        # Check if ready
        is_ready, reason = Validator.check_task_ready_to_execute(t, p.get_tasks())
        if not is_ready:
            formatter.print_error(f"Task not ready: {reason}")
            sys.exit(1)

        t.update_status(TaskStatus.EXECUTING)
        t.save(str(config.get_task_file(plan_name, task_id)))

        formatter.print_success(f"Task '{t.title}' started")

    except Exception as e:
        formatter.print_error(f"Failed to start task: {e}")
        sys.exit(1)


@task.command('complete')
@click.argument('plan_name')
@click.argument('task_id')
@click.pass_context
def task_complete(ctx, plan_name, task_id):
    """Mark task as completed."""
    config: Config = ctx.obj['config']
    formatter: Formatter = ctx.obj['formatter']

    try:
        p = Plan.load(plan_name, config)
        t = p.get_task(task_id)

        if not t:
            formatter.print_error(f"Task '{task_id}' not found")
            sys.exit(1)

        t.update_status(TaskStatus.COMPLETED)
        t.save(str(config.get_task_file(plan_name, task_id)))

        # Update plan progress
        p.update_progress()
        p.save(config)

        formatter.print_success(f"Task '{t.title}' completed")

    except Exception as e:
        formatter.print_error(f"Failed to complete task: {e}")
        sys.exit(1)


# =====================
# status command
# =====================
@cli.command()
@click.option('--plan', type=str, help='Show status for specific plan')
@click.pass_context
def status(ctx, plan):
    """Show overall status."""
    config: Config = ctx.obj['config']
    formatter: Formatter = ctx.obj['formatter']

    if not config.workspace_exists():
        formatter.print_error("Workspace not initialized. Run 'pm init' first.")
        sys.exit(1)

    try:
        if plan:
            # Show specific plan status
            p = Plan.load(plan, config)
            formatter.print_plan_details(p)
            formatter.print_header("Tasks")
            formatter.print_task_list(p.get_tasks())
        else:
            # Show all plans status
            plan_names = config.list_plans()

            if not plan_names:
                formatter.print_info("No plans found")
                return

            plans = [Plan.load(name, config) for name in plan_names]
            formatter.print_plan_list(plans)

    except Exception as e:
        formatter.print_error(f"Failed to show status: {e}")
        sys.exit(1)


# =====================
# validate command
# =====================
@cli.command()
@click.argument('plan_name')
@click.pass_context
def validate(ctx, plan_name):
    """Validate plan and tasks."""
    config: Config = ctx.obj['config']
    formatter: Formatter = ctx.obj['formatter']

    try:
        p = Plan.load(plan_name, config)

        formatter.print_header(f"Validating plan: {plan_name}")

        # Validate plan
        result = Validator.validate_plan(p)
        formatter.print_validation_result(result)

        # Show suggested next tasks
        next_tasks = Validator.suggest_next_tasks(p)
        if next_tasks:
            formatter.print_header("Suggested next tasks")
            formatter.print_task_list(next_tasks[:5])

    except Exception as e:
        formatter.print_error(f"Failed to validate plan: {e}")
        sys.exit(1)


if __name__ == '__main__':
    cli()
