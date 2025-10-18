"""Custom tools for Claude Agent SDK plan generation."""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from claude_agent_sdk import tool, create_sdk_mcp_server

from ..utils.logger import get_logger
from .prompts import CONFIRMATION_TEMPLATE

logger = get_logger(__name__)


@dataclass
class PlanDraft:
    """In-memory draft representation shared across tool calls."""
    name: str = ""
    brief: str = ""
    objectives: List[str] = field(default_factory=list)
    deliverables: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    author: str = ""
    has_preview: bool = False

    def to_data(self) -> Dict[str, Any]:
        """Return dict representation suitable for tool responses."""
        return {
            "name": self.name,
            "brief": self.brief,
            "objectives": list(self.objectives),
            "deliverables": list(self.deliverables),
            "tags": list(self.tags),
            "author": self.author,
        }


_current_draft: PlanDraft = PlanDraft()


def _reset_plan_draft() -> None:
    """Reset the global draft state for a new planning session."""
    global _current_draft
    _current_draft = PlanDraft()
    logger.debug("Plan draft state reset")


def _format_preview_message(data: Dict[str, Any]) -> str:
    """Render preview text using the confirmation template."""
    objectives_md = "\n".join(f"- {item}" for item in data.get("objectives", []))
    deliverables_md = "\n".join(f"- {item}" for item in data.get("deliverables", []))
    tags = data.get("tags") or []
    author = data.get("author") or ""

    tags_section = "🏷️ **Tags**: " + ", ".join(tags) if tags else ""
    author_section = f"👤 **Autor**: {author}" if author else ""

    return CONFIRMATION_TEMPLATE.format(
        name=data.get("name", ""),
        brief=data.get("brief", ""),
        objectives=objectives_md or "- (adicionar objetivos)",
        deliverables=deliverables_md or "- (adicionar entregáveis)",
        tags_section=tags_section,
        author_section=author_section
    )


def _update_draft(data: Dict[str, Any], mark_preview: bool = False) -> None:
    """Persist provided data into the draft."""
    global _current_draft
    _current_draft.name = data.get("name", _current_draft.name)
    _current_draft.brief = data.get("brief", _current_draft.brief)
    _current_draft.objectives = list(data.get("objectives", _current_draft.objectives))
    _current_draft.deliverables = list(data.get("deliverables", _current_draft.deliverables))
    _current_draft.tags = list(data.get("tags", _current_draft.tags))
    _current_draft.author = data.get("author", _current_draft.author)
    _current_draft.has_preview = mark_preview
    logger.debug("Plan draft updated: %s", _current_draft)


def _require_preview_alignment(data: Dict[str, Any]) -> Optional[str]:
    """Ensure finalize input matches the latest previewed draft."""
    missing_preview = not _current_draft.has_preview
    mismatched_fields = []

    for field in ("name", "brief", "objectives", "deliverables", "tags", "author"):
        if getattr(_current_draft, field) != data.get(field, getattr(_current_draft, field)):
            mismatched_fields.append(field)

    if missing_preview:
        return "É necessário chamar a ferramenta preview_plan antes de finalizar."

    if mismatched_fields:
        return (
            "Alguns campos mudaram após o último preview "
            f"({', '.join(mismatched_fields)}). Gere um novo preview antes de finalizar."
        )

    return None


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


def _sanitize_list(value: Any) -> List[str]:
    """Normalize list inputs removing whitespaces and vazios."""
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = [item.strip() for item in value.split(",")]
    else:
        return []

    return [item.strip() for item in items if item and item.strip()]


@tool(
    name="preview_plan",
    description="Gera um preview formatado do plano atual e registra o estado para confirmação posterior.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "brief": {"type": "string"},
            "objectives": {
                "type": "array",
                "items": {"type": "string"}
            },
            "deliverables": {
                "type": "array",
                "items": {"type": "string"}
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"}
            },
            "author": {"type": "string"}
        },
        "required": ["name", "brief", "objectives", "deliverables"]
    }
)
async def preview_plan_tool(
    name: str,
    brief: str,
    objectives: List[str],
    deliverables: List[str],
    tags: Optional[List[str]] = None,
    author: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validate and persist a plan draft, returning a formatted preview.
    """
    logger.info("preview_plan_tool called for '%s'", name)

    errors = []

    is_valid, error = validate_plan_name(name)
    if not is_valid:
        errors.append(f"Name: {error}")

    is_valid, error = validate_brief(brief)
    if not is_valid:
        errors.append(f"Brief: {error}")

    is_valid, error = validate_list(objectives, "Objectives", min_items=2)
    if not is_valid:
        errors.append(error)

    is_valid, error = validate_list(deliverables, "Deliverables", min_items=2)
    if not is_valid:
        errors.append(error)

    if errors:
        logger.warning("Preview validation failed: %s", errors)
        return {
            "success": False,
            "errors": errors,
            "message": "Não foi possível gerar o preview. Ajuste os campos e tente novamente."
        }

    draft_data = {
        "name": name,
        "brief": brief,
        "objectives": objectives,
        "deliverables": deliverables,
        "tags": tags or [],
        "author": author or "",
    }
    _update_draft(draft_data, mark_preview=True)

    preview_text = _format_preview_message(draft_data)
    return {
        "success": True,
        "message": "Preview gerado. Confirme com o usuário ou solicite ajustes.",
        "data": draft_data,
        "preview": preview_text
    }


@tool(
    name="update_plan_field",
    description="Atualiza um campo individual do plano em andamento (ex.: objetivos, deliverables, brief).",
    input_schema={
        "type": "object",
        "properties": {
            "field": {
                "type": "string",
                "enum": ["name", "brief", "objectives", "deliverables", "tags", "author"]
            },
            "value": {}
        },
        "required": ["field", "value"]
    }
)
async def update_plan_field_tool(field: str, value: Any) -> Dict[str, Any]:
    """
    Update a single field in the stored draft and mark preview as stale.
    """
    logger.info("update_plan_field_tool called for '%s'", field)

    updated_data = _current_draft.to_data()

    if field in {"objectives", "deliverables", "tags"}:
        sanitized = _sanitize_list(value)
        if not sanitized:
            return {
                "success": False,
                "message": f"Não foi possível atualizar '{field}'. Forneça uma lista com valores não vazios."
            }
        updated_data[field] = sanitized
    elif field in {"name", "brief", "author"}:
        if not isinstance(value, str) or not value.strip():
            return {
                "success": False,
                "message": f"Valor inválido para '{field}'. Forneça uma string não vazia."
            }
        updated_data[field] = value.strip()
    else:
        return {
            "success": False,
            "message": f"O campo '{field}' não é suportado."
        }

    _update_draft(updated_data, mark_preview=False)

    return {
        "success": True,
        "message": f"Campo '{field}' atualizado. Gere um novo preview antes de finalizar.",
        "data": _current_draft.to_data()
    }


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

    preview_alignment_error = _require_preview_alignment({
        "name": name,
        "brief": brief,
        "objectives": objectives,
        "deliverables": deliverables,
        "tags": tags or [],
        "author": author or ""
    })
    if preview_alignment_error:
        errors.append(preview_alignment_error)

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
    _reset_plan_draft()
    return create_sdk_mcp_server([
        preview_plan_tool,
        update_plan_field_tool,
        finalize_plan_tool
    ])
