"""Custom tools for Claude Agent SDK plan generation."""

import re
from typing import List, Optional, Dict, Any
from claude_agent_sdk import tool, create_sdk_mcp_server

from ..utils.logger import get_logger

logger = get_logger(__name__)


def validate_plan_name(name: str) -> tuple[bool, Optional[str]]:
    """
    Validate plan name format.

    Args:
        name: Plan name to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name:
        return False, "Plan name cannot be empty"

    if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name):
        return False, "Plan name must be lowercase with hyphens (e.g., my-api-project)"

    if len(name) < 3:
        return False, "Plan name must be at least 3 characters"

    if len(name) > 50:
        return False, "Plan name must not exceed 50 characters"

    return True, None


def validate_brief(brief: str) -> tuple[bool, Optional[str]]:
    """
    Validate brief description.

    Args:
        brief: Brief description to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not brief:
        return False, "Brief cannot be empty"

    if len(brief) > 128:
        return False, f"Brief must not exceed 128 characters (currently {len(brief)})"

    if len(brief) < 10:
        return False, "Brief must be at least 10 characters"

    return True, None


def validate_list(items: List[str], field_name: str, min_items: int = 2) -> tuple[bool, Optional[str]]:
    """
    Validate a list of items.

    Args:
        items: List to validate
        field_name: Name of the field (for error messages)
        min_items: Minimum number of items required

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not items:
        return False, f"{field_name} cannot be empty"

    if len(items) < min_items:
        return False, f"{field_name} must have at least {min_items} items"

    # Check for empty strings
    if any(not item.strip() for item in items):
        return False, f"{field_name} cannot contain empty items"

    return True, None


@tool(
    name="finalize_plan",
    description="Finalize and structure the plan data when all required information has been collected and user confirms",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Project name in lowercase-with-hyphens format"
            },
            "brief": {
                "type": "string",
                "description": "Brief description (max 128 characters)"
            },
            "objectives": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of project objectives"
            },
            "deliverables": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of project deliverables"
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional tags for categorization"
            },
            "author": {
                "type": "string",
                "description": "Optional author name"
            }
        },
        "required": ["name", "brief", "objectives", "deliverables"]
    }
)
async def finalize_plan_tool(
    name: str,
    brief: str,
    objectives: List[str],
    deliverables: List[str],
    tags: Optional[List[str]] = None,
    author: Optional[str] = None
) -> Dict[str, Any]:
    """
    Custom tool that Claude calls when plan data is ready to be finalized.

    This tool validates all input data and returns a structured dictionary
    that will be used to create the Plan object.

    Args:
        name: Project name
        brief: Brief description
        objectives: List of objectives
        deliverables: List of deliverables
        tags: Optional list of tags
        author: Optional author name

    Returns:
        Dictionary with validation result and plan data
    """
    logger.info(f"finalize_plan_tool called with name='{name}'")

    errors = []

    # Validate name
    is_valid, error = validate_plan_name(name)
    if not is_valid:
        errors.append(f"Name: {error}")

    # Validate brief
    is_valid, error = validate_brief(brief)
    if not is_valid:
        errors.append(f"Brief: {error}")

    # Validate objectives
    is_valid, error = validate_list(objectives, "Objectives", min_items=2)
    if not is_valid:
        errors.append(error)

    # Validate deliverables
    is_valid, error = validate_list(deliverables, "Deliverables", min_items=2)
    if not is_valid:
        errors.append(error)

    # If there are validation errors, return them
    if errors:
        logger.warning(f"Plan validation failed: {errors}")
        return {
            "success": False,
            "errors": errors,
            "message": "Plan validation failed. Please fix the following issues:\n" + "\n".join(f"- {e}" for e in errors)
        }

    # All validations passed
    plan_data = {
        "success": True,
        "data": {
            "name": name,
            "brief": brief,
            "objectives": objectives,
            "deliverables": deliverables,
            "tags": tags or [],
            "author": author or "",
        },
        "message": f"Plan '{name}' successfully created!"
    }

    logger.info(f"Plan data validated successfully: {name}")
    return plan_data


def create_plan_tools_server():
    """
    Create an MCP server with plan generation tools.

    Returns:
        MCP server instance with registered tools
    """
    return create_sdk_mcp_server([finalize_plan_tool])
