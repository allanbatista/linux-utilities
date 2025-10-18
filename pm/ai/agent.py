"""Claude Agent SDK client for interactive plan generation."""

import difflib
import os
import re
from typing import Optional, Dict, Any, AsyncIterator

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    ToolResultBlock,
)

from rich.markdown import Markdown

from .printer import TerminalPrinter
from .json_dumps import dumps

os.environ["ANTHROPIC_API_KEY"] = ''

from .prompts import PLAN_SYSTEM_PROMPT
from ..utils.logger import get_logger

logger = get_logger(__name__)

pp = TerminalPrinter()

SYSTEM_REMINDER_PATTERN = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)

MAX_DIFF_PREVIEW_LINES = 160
DIFF_TRUNCATION_NOTICE = "... (diff truncado)"
KNOWN_EDIT_KEYS = {"file_path", "old_string", "new_string"}

BLOCK_DISPLAY_NAMES = {
    "text": "💬 Resposta",
    "thinking": "🤔 Pensando",
    "tool_use": "🔧 Uso de ferramenta",
    "tool_result": "📦 Resultado da ferramenta",
    "tool_result_error": "⚠️ Resultado da ferramenta (erro)",
    "json": "📄 Dados",
    "error": "❌ Erro",
}

PRINTER_MESSAGE_TYPES = {
    "text": "response",
    "thinking": "thinking",
    "tool_use": "tool",
    "tool_result": "tool_result",
    "tool_result_error": "tool_result_error",
    "json": "response",
    "error": "error",
}

TODO_STATUS_SYMBOLS = {
    "pending": "⏳",
    "todo": "⏳",
    "in_progress": "🔄",
    "doing": "🔄",
    "active": "🔄",
    "completed": "✅",
    "complete": "✅",
    "done": "✅",
    "blocked": "⛔",
    "cancelled": "✖️",
}


def strip_system_reminders(text: Any | None) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return SYSTEM_REMINDER_PATTERN.sub("", text)


def build_diff_preview(old_text: str, new_text: str) -> str:
    diff_lines = list(
        difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile="antes",
            tofile="depois",
            lineterm="",
        )
    )

    if not diff_lines:
        return ""

    if len(diff_lines) > MAX_DIFF_PREVIEW_LINES:
        diff_lines = diff_lines[:MAX_DIFF_PREVIEW_LINES]
        diff_lines.append(DIFF_TRUNCATION_NOTICE)

    return "\n".join(diff_lines)


def writer_formatter(input_data: Dict[str, Any]) -> str:
    file_path = input_data.get("file_path")
    new_content = strip_system_reminders(input_data.get("content", ""))

    sections = []
    if file_path:
        sections.append(f"**Arquivo:** `{file_path}`")

    diff_text = ""
    if new_content:
        existing_content = ""
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as file_handle:
                    existing_content = file_handle.read()
            except (OSError, UnicodeDecodeError):
                existing_content = ""

        diff_text = build_diff_preview(
            strip_system_reminders(existing_content),
            new_content,
        )

    if diff_text:
        sections.append(f"```diff\n{diff_text}\n```")
    elif new_content:
        sections.append(f"```text\n{new_content}\n```")

    extra_fields = {
        key: value
        for key, value in input_data.items()
        if key not in {"file_path", "content"}
    }
    if extra_fields:
        sections.append(f"```json\n{dumps(extra_fields, indent=2)}\n```")

    return "\n\n".join(sections) if sections else ""


def edit_formatter(input_data: Dict[str, Any]) -> str:
    file_path = input_data.get("file_path")
    old_text = strip_system_reminders(input_data.get("old_string", ""))
    new_text = strip_system_reminders(input_data.get("new_string", ""))

    sections = []
    if file_path:
        sections.append(f"**Arquivo:** `{file_path}`")

    diff_text = build_diff_preview(old_text, new_text)
    if diff_text:
        sections.append(f"```diff\n{diff_text}\n```")
    else:
        sections.append("Nenhuma diferença detectada.")

    extra_fields = {
        key: value
        for key, value in input_data.items()
        if key not in KNOWN_EDIT_KEYS
    }
    if extra_fields:
        sections.append(f"```json\n{dumps(extra_fields, indent=2)}\n```")

    return "\n\n".join(sections)


def todo_formatter(input_data: Dict[str, Any]) -> str:
    todos_raw = input_data.get("todos")
    if not isinstance(todos_raw, list) or not todos_raw:
        return f"```json\n{dumps(input_data, indent=2)}\n```"

    lines: list[str] = []
    total_items = len(todos_raw)

    for index, todo in enumerate(todos_raw, start=1):
        if not isinstance(todo, dict):
            continue

        content = strip_system_reminders(todo.get("content")).strip()
        content = content or "Sem descrição"

        status_raw = strip_system_reminders(todo.get("status")).lower()
        symbol = TODO_STATUS_SYMBOLS.get(status_raw, "•")

        line_prefix = f"{index}." if total_items > 1 else "-"
        lines.append(f"{line_prefix} {symbol} {content}")

        active_form = strip_system_reminders(todo.get("activeForm")).strip()
        if active_form:
            lines.append(f"   ↪ {active_form}")

        extra_fields = {
            key: value
            for key, value in todo.items()
            if key not in {"content", "status", "activeForm"} and value not in (None, "")
        }
        if extra_fields:
            lines.append(f"   ```json\n{dumps(extra_fields, indent=2)}\n```")

    if not lines:
        return f"```json\n{dumps(input_data, indent=2)}\n```"

    sections = ["**To-dos atualizados:**", "\n".join(lines)]

    extra_top_level = {
        key: value
        for key, value in input_data.items()
        if key != "todos"
    }
    if extra_top_level:
        sections.append(f"```json\n{dumps(extra_top_level, indent=2)}\n```")

    return "\n\n".join(sections)


TOOL_FORMATTER = {
    "write": writer_formatter,
    "edit": edit_formatter,
    "todowrite": todo_formatter,
}

class GenericAgentClient:
    """
    Client for interacting with Claude Agent SDK to generate plans.

    This class manages the lifecycle of an agent session and handles
    communication with Claude for interactive plan creation.
    """

    def __init__(self, custom_tools: Optional[list] = None, system_prompt: Optional[str] = None, console=None):
        """
        Initialize the Plan Agent Client.

        Args:
            custom_tools: List of custom tools to make available to the agent
        """
        self.custom_tools = custom_tools or []
        self.client: Optional[ClaudeSDKClient] = None
        self._conversation_history = []
        self.system_prompt = system_prompt
        self.console = console
        self._suppressed_tool_ids: set[str] = set()

        # # Verify API key is set
        # if not os.getenv('ANTHROPIC_API_KEY'):
        #     raise ValueError(
        #         "ANTHROPIC_API_KEY environment variable not set. "
        #         "Please set it with your Claude API key from https://console.anthropic.com/"
        #     )

    def _create_options(self) -> ClaudeAgentOptions:
        """Create Claude Agent options with appropriate configuration."""
        return ClaudeAgentOptions(
            system_prompt=self.system_prompt,
            # system_prompt={
            #     "type": "preset",
            #     "preset": "claude_code",
            #     "append": self.system_prompt
            # },
            setting_sources=["project"],
            allowed_tools=["Read", "Write", "Edit"],
            permission_mode='bypassPermissions'
        )

    async def __aenter__(self):
        """Async context manager entry - starts the agent session."""
        options = self._create_options()
        self.client = ClaudeSDKClient(options=options)
        await self.client.__aenter__()
        logger.info("Claude Agent session started")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleans up the agent session."""
        if self.client:
            await self.client.__aexit__(exc_type, exc_val, exc_tb)
            logger.info("Claude Agent session ended")
        return False

    async def send_message(self, message: str) -> None:
        """
        Send a message to the agent.

        Args:
            message: User message to send
        """
        try:
            print("\nThinking...\n")

            if not self.client:
                raise RuntimeError("Agent session not started. Use async with context manager.")

            logger.debug(f"Sending message: {message[:100]}...")
            self._conversation_history.append({"role": "user", "content": message})
            await self.client.query(message)
        except Exception as e:
            logger.error(f"Error sending message: {message}: {e}")
            raise

    def _strip_system_blocks(self, text: str) -> str:
        return strip_system_reminders(text)

    def _sanitize_output(self, text: str, *, strip: bool = True) -> str:
        if not text:
            return ""
        cleaned = self._strip_system_blocks(text)
        return cleaned.strip() if strip else cleaned

    def pp(self, text: str, message_type: str, support_text=True) -> None:
        """Renderiza saída formatada conforme o tipo de mensagem."""
        text = self._sanitize_output(text, strip=False)
        if not text.strip():
            return

        display_name = BLOCK_DISPLAY_NAMES.get(message_type, message_type)
        printer_type = PRINTER_MESSAGE_TYPES.get(message_type, message_type)

        if self.console:
            if support_text and not text.strip().startswith("```"):
                text = f"```text\n{text}\n```"

            md = Markdown(f"\n\n---\n\n**{display_name}**\n\n{text}")
            self.console.print(md)
        else:
            pp.print_claude_message(text, printer_type)

    @staticmethod
    def _format_json_block(data: Any, indent: int = 2) -> str:
        """Retorna dados estruturados como bloco JSON formatado."""
        return f"```json\n{dumps(data, indent=indent)}\n```"

    def _handle_text_block(self, block: TextBlock) -> Optional[str]:
        text = self._sanitize_output(block.text or "")
        if text:
            self.pp(text, "text", support_text=False)
            return text
        return None

    def _handle_thinking_block(self, block: ThinkingBlock) -> None:
        thinking = self._sanitize_output(block.thinking or "")
        if not thinking:
            return

        signature = getattr(block, "signature", "")
        if signature:
            self.pp(f"`signature: {signature}`\n\n{thinking}", "thinking")
        else:
            self.pp(thinking, "thinking")

    def _handle_tool_use_block(self, block: ToolUseBlock) -> None:
        tool_name_raw = getattr(block, "name", "desconhecido")
        tool_name_normalized = (tool_name_raw or "").lower()
        tool_name = tool_name_raw or "desconhecido"
        tool_id = getattr(block, "id", "")
        tool_input = getattr(block, "input", None)

        if tool_name_normalized == "read":
            if tool_id:
                self._suppressed_tool_ids.add(tool_id)
            return

        header_parts = []
        if tool_name:
            header_parts.append(f"**Ferramenta:** `{tool_name}`")
        if tool_id:
            header_parts.append(f"**ID:** `{tool_id}`")

        if tool_input:
            tool_formatter = TOOL_FORMATTER.get(tool_name_normalized)
            if tool_formatter:
                formatted_section = tool_formatter(tool_input)
                if formatted_section:
                    header_parts.append(formatted_section)
            else:
                header_parts.append(self._format_json_block(tool_input))

        message = "\n\n".join(header_parts) if header_parts else "Uso de ferramenta"
        self.pp(message, "tool_use", support_text=False)

    def _handle_tool_result_block(self, block: ToolResultBlock) -> None:
        has_error = getattr(block, "is_error", False)
        result_type = "tool_result_error" if has_error else "tool_result"
        tool_use_id = getattr(block, "tool_use_id", "")

        if tool_use_id and tool_use_id in self._suppressed_tool_ids:
            self._suppressed_tool_ids.discard(tool_use_id)
            return

        parts = []
        if tool_use_id:
            parts.append(f"**Tool use ID:** `{tool_use_id}`")

        content = getattr(block, "content", None)
        if isinstance(content, str):
            content_text = self._sanitize_output(content)
            if content_text:
                parts.append(content_text)
        elif content:
            parts.append(self._format_json_block(content))

        if not parts:
            parts.append("Sem conteúdo retornado pela ferramenta.")

        self.pp("\n\n".join(parts), result_type, support_text=False)

    def print_message(self, message: Any) -> Optional[str]:
        """Processa e exibe uma mensagem recebida do Claude"""
        response_text = ""

        try:
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        block_text = self._handle_text_block(block)
                        if block_text:
                            response_text = block_text
                    elif isinstance(block, ThinkingBlock):
                        self._handle_thinking_block(block)
                    elif isinstance(block, ToolUseBlock):
                        self._handle_tool_use_block(block)
                    elif isinstance(block, ToolResultBlock):
                        self._handle_tool_result_block(block)
                    else:
                        self.pp(self._format_json_block(block), "json")

            elif hasattr(message, "content"):
                content = getattr(message, "content", None)
                if isinstance(content, str):
                    sanitized = self._sanitize_output(content)
                    if sanitized:
                        self.pp(sanitized, "text")
                elif content:
                    # print("---------------> ", message.__class__.__name__)
                    # print(message)
                    for block in content:
                        if isinstance(block, ToolResultBlock):
                            continue
                        block_content = getattr(block, "content", None)
                        sanitized = self._sanitize_output(block_content)
                        if sanitized:
                            self.pp(sanitized, "text")

            elif hasattr(message, "result"):
                response_text = self._sanitize_output(message.result)
                if response_text:
                    self.pp(response_text, "text", support_text=False)

            # elif hasattr(message, "__dict__"):
            #     self.pp(self._format_json_block(message, indent=4), "json")

        except Exception as e:
            self.pp(f"Erro ao processar mensagem: {e}", "error")

        return response_text if response_text else None

    async def receive_response(self) -> AsyncIterator[AssistantMessage]:
        """
        Receive streaming response from the agent.

        Yields:
            AssistantMessage objects from Claude
        """
        if not self.client:
            raise RuntimeError("Agent session not started. Use async with context manager.")

        async for message in self.client.receive_response():
            self.print_message(message)

            if isinstance(message, AssistantMessage):
                self._conversation_history.append({
                    "role": "assistant",
                    "content": self._extract_text_from_message(message)
                })

                yield message

    def _extract_text_from_message(self, message: AssistantMessage) -> str:
        """Extract text content from an assistant message."""
        text_parts = []
        for block in message.content:
            if isinstance(block, TextBlock):
                text_parts.append(block.text)
        return "\n".join(text_parts)

    def get_conversation_history(self) -> list:
        """Get the full conversation history."""
        return self._conversation_history.copy()

    def has_tool_use(self, message: AssistantMessage, tool_name: str) -> bool:
        """
        Check if a message contains a specific tool use.

        Args:
            message: AssistantMessage to check
            tool_name: Name of the tool to look for

        Returns:
            True if the message contains a tool use with the given name
        """
        for block in message.content:
            if hasattr(block, 'name') and block.name == tool_name:
                return True
        return False

    def extract_tool_input(self, message: AssistantMessage, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Extract input parameters from a tool use in a message.

        Args:
            message: AssistantMessage containing tool use
            tool_name: Name of the tool

        Returns:
            Dictionary of tool input parameters, or None if not found
        """
        for block in message.content:
            if hasattr(block, 'name') and block.name == tool_name:
                if hasattr(block, 'input'):
                    return block.input
        return None
