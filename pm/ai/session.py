"""Utilities for managing interactive planning sessions."""

from __future__ import annotations

from enum import Enum
from typing import Optional, Dict, Iterable, Tuple, Any
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from claude_agent_sdk import AssistantMessage, TextBlock

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ConversationStage(str, Enum):
    """Stages of the guided planning conversation."""
    DISCOVERY = "discovery"
    SYNTHESIS = "synthesis"
    CONFIRMATION = "confirmation"
    FINALIZED = "finalized"

    def label(self) -> str:
        labels = {
            "discovery": "🧭 Descoberta",
            "synthesis": "🛠️ Síntese",
            "confirmation": "✅ Confirmação",
            "finalized": "🏁 Finalizado",
        }
        return labels[self.value]


class PlanningSessionUI:
    """Handles CLI interaction, stage tracking, and feedback during planning."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self._stage: ConversationStage = ConversationStage.DISCOVERY
        self._received_agent_message = False
        self._last_preview: Optional[Dict[str, Any]] = None
        self._last_preview_text: Optional[str] = None
        self._cancelled = False

    def start_session(self) -> None:
        """Render the initial session banner, help, and stage indicator."""
        self.console.print(Panel(
            "[bold cyan]AI-Powered Plan Creation[/bold cyan]\n\n"
            "Converse com Claude para criar seu plano de projeto.\n"
            "Digite 'cancelar' ou 'sair' a qualquer momento para cancelar.",
            border_style="cyan"
        ))
        self.console.print()
        self._show_help(short=True)
        self._print_stage()

    def request_initial_input(self, question: str) -> Optional[str]:
        """Display the onboarding question and capture the first response."""
        self.console.print(f"[bold cyan]{question}[/bold cyan]")
        return self.prompt_user_input()

    def prepare_user_prompt(self) -> None:
        """Insert spacing before asking the user for input."""
        self.console.print()

    def prompt_user_input(self) -> Optional[str]:
        """Collect user input, offering local command handling."""
        while True:
            raw = input("> ").strip()

            if self._is_cancel_command(raw):
                self.console.print("[yellow]Operação cancelada.[/yellow]")
                self._cancelled = True
                return None

            if raw.startswith("/"):
                handled, cancel = self._handle_user_command(raw)
                if cancel:
                    self.console.print("[yellow]Operação cancelada.[/yellow]")
                    self._cancelled = True
                    return None
                if handled:
                    continue
                self.console.print("[yellow]Comando não reconhecido. Digite /ajuda para ver opções.[/yellow]")
                continue

            if not raw:
                self.console.print("[yellow]Entrada vazia. Descreva o que deseja ou use /ajuda.[/yellow]")
                continue

            return raw

    def handle_assistant_message(self, message: AssistantMessage) -> None:
        """Display assistant output and process tool-related feedback."""
        for block in message.content:
            if isinstance(block, TextBlock):
                try:
                    md = Markdown(block.text)
                    self.console.print(md)
                except Exception:
                    self.console.print(block.text)

        self._ensure_stage_after_agent_message()
        self._process_tool_blocks(message)

    def handle_finalization_result(self, tool_result: Dict[str, Any]) -> bool:
        """
        Present validation feedback for finalization attempts.

        Returns:
            True when validation succeeds, False otherwise.
        """
        if not tool_result.get('success', False):
            errors = tool_result.get('errors', [])
            self.console.print(Panel(
                "[bold red]Validação Falhou[/bold red]\n\n" +
                "\n".join(f"- {e}" for e in errors),
                border_style="red"
            ))
            return False

        self._set_stage(ConversationStage.FINALIZED)

        self.console.print()
        self.console.print(Panel(
            f"[bold green]✓ {tool_result.get('message', 'Plano criado com sucesso!')}[/bold green]",
            border_style="green"
        ))

        return True

    def is_cancelled(self) -> bool:
        """Whether the user terminated the session."""
        return self._cancelled

    def _process_tool_blocks(self, message: AssistantMessage) -> None:
        """React to tool invocations embedded in assistant messages."""
        for block in getattr(message, "content", []):
            name = getattr(block, "name", None)
            payload = getattr(block, "input", None)

            if not name or payload is None:
                continue

            if name == "preview_plan":
                self._handle_preview(payload)
            elif name == "update_plan_field":
                self._handle_plan_update(payload)

    def _handle_preview(self, payload: Dict[str, Any]) -> None:
        """Render previews and update confirmation stage."""
        if not payload.get("success"):
            errors = payload.get("errors") or ["Falha ao gerar preview."]
            self.console.print(Panel(
                "[bold red]Preview não gerado[/bold red]\n\n" +
                "\n".join(f"- {e}" for e in errors),
                border_style="red"
            ))
            return

        self._last_preview = payload.get("data")
        self._last_preview_text = payload.get("preview")
        self._set_stage(ConversationStage.CONFIRMATION)

        if self._last_preview_text:
            self.console.print(Panel(self._last_preview_text, border_style="cyan"))
        else:
            self.console.print("[cyan]Preview atualizado. Use /resumo para revisar quando quiser.[/cyan]")

    def _handle_plan_update(self, payload: Dict[str, Any]) -> None:
        """Display feedback for incremental plan updates."""
        if not payload.get("success"):
            self.console.print(Panel(
                f"[bold red]Atualização não aplicada[/bold red]\n{payload.get('message', '')}",
                border_style="red"
            ))
            return

        self._last_preview = payload.get("data")
        self._last_preview_text = None
        self._set_stage(ConversationStage.SYNTHESIS)

        message = payload.get("message", "Campo atualizado.")
        self.console.print(Panel(
            f"[green]{message}[/green]\nUse /resumo após gerar novo preview.",
            border_style="green"
        ))

    def _ensure_stage_after_agent_message(self) -> None:
        """Advance the stage after the first assistant reply."""
        if not self._received_agent_message:
            self._received_agent_message = True
            self._set_stage(ConversationStage.SYNTHESIS)

    def _handle_user_command(self, command: str) -> Tuple[bool, bool]:
        """Interpret slash commands; return (handled, cancel_requested)."""
        normalized = command.lower()

        if normalized in {"/ajuda", "/help"}:
            self._show_help()
            return True, False

        if normalized in {"/resumo", "/preview"}:
            if self._last_preview_text:
                self.console.print(Panel(self._last_preview_text, border_style="cyan"))
            else:
                self.console.print("[yellow]Nenhum preview disponível ainda. Peça ao agente para gerar primeiro.[/yellow]")
            return True, False

        if normalized in {"/etapa", "/stage"}:
            self._print_stage()
            return True, False

        if normalized in {"/cancelar", "/sair"}:
            return True, True

        return False, False

    def _show_help(self, short: bool = False) -> None:
        """Display helper commands."""
        lines: Iterable[str]
        if short:
            lines = [
                "Comandos rápidos:",
                "/ajuda  – ver instruções completas",
                "/resumo – mostrar último preview",
                "/etapa  – exibir etapa atual",
                "cancelar – encerrar a sessão",
            ]
        else:
            lines = [
                "Comandos disponíveis:",
                "/ajuda  – exibe esta lista",
                "/resumo – mostra o último preview gerado",
                "/etapa  – indica em qual etapa do fluxo estamos",
                "cancelar – encerra a criação do plano",
                "Dica: peça ao agente para gerar um preview antes de confirmar."
            ]

        self.console.print(Panel("\n".join(lines), border_style="magenta"))

    def _print_stage(self) -> None:
        """Render the stage indicator."""
        self.console.print(Panel(
            f"[bold]{self._stage.label()}[/bold]\n"
            "Use /ajuda para ver comandos disponíveis.",
            border_style="blue"
        ))

    def _set_stage(self, stage: ConversationStage) -> None:
        """Update the internal stage and re-render indicator when changed."""
        if stage == self._stage:
            return
        self._stage = stage
        self._print_stage()

    @staticmethod
    def _is_cancel_command(text: str) -> bool:
        """Check if raw user input matches a cancel keyword."""
        cancel_commands = {'cancelar', 'sair', 'exit', 'quit', 'cancel'}
        return text.lower() in cancel_commands
