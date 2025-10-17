"""AI-powered plan generator using Claude Agent SDK."""

from typing import Optional, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from claude_agent_sdk import AssistantMessage, TextBlock

from .agent import GenericAgentClient
from .tools import create_plan_tools_server
from .prompts import INITIAL_PROMPT, PLAN_SYSTEM_PROMPT
from ..core.plan import Plan, PlanStatus
from ..core.config import Config
from ..utils.logger import get_logger
from ..utils.helpers import get_timestamp

logger = get_logger(__name__)
console = Console()


class AIPlanGenerator:
    """
    AI-powered plan generator that orchestrates interactive conversations
    with Claude to create structured project plans.
    """

    def __init__(self, config: Config):
        """
        Initialize the AI Plan Generator.

        Args:
            config: Project manager configuration
        """
        self.config = config
        self.plan_data: Optional[Dict[str, Any]] = None
        self._finalized = False

    async def interactive_planning(self) -> Optional[Plan]:
        """
        Execute the interactive planning flow with Claude.

        Returns:
            Created Plan object, or None if cancelled
        """
        console.print(Panel(
            "[bold cyan]AI-Powered Plan Creation[/bold cyan]\n\n"
            "Converse com Claude para criar seu plano de projeto.\n"
            "Digite 'cancelar' ou 'sair' a qualquer momento para cancelar.",
            border_style="cyan"
        ))
        console.print()

        # Create custom tools server
        tools_server = create_plan_tools_server()

        try:
            async with GenericAgentClient(custom_tools=[tools_server], system_prompt=PLAN_SYSTEM_PROMPT) as agent:
                # Start conversation
                console.print(f"[bold cyan]{INITIAL_PROMPT}[/bold cyan]")
                user_input = input("> ").strip()

                if self._is_cancel_command(user_input):
                    console.print("[yellow]Operação cancelada.[/yellow]")
                    return None

                # Send initial message
                await agent.send_message(user_input)

                # Main conversation loop
                while not self._finalized:
                    # Receive and display agent responses
                    async for message in agent.receive_response():
                        if isinstance(message, AssistantMessage):
                            # Display message
                            self._display_message(message)

                            # Check if plan was finalized
                            if agent.has_tool_use(message, "finalize_plan"):
                                tool_result = agent.extract_tool_input(message, "finalize_plan")
                                if tool_result:
                                    success = self._handle_finalization(tool_result)
                                    if success:
                                        # Create and return the plan
                                        return self._create_plan()
                                    else:
                                        # Validation failed, continue conversation
                                        console.print("[yellow]Por favor, corrija os problemas e tente novamente.[/yellow]")

                    # If finalized, break out of loop
                    if self._finalized:
                        break

                    # Get next user input
                    console.print()
                    user_input = input("> ").strip()

                    if self._is_cancel_command(user_input):
                        console.print("[yellow]Operação cancelada.[/yellow]")
                        return None

                    # Send user message
                    await agent.send_message(user_input)

        except KeyboardInterrupt:
            console.print("\n[yellow]Operação cancelada.[/yellow]")
            return None
        except Exception as e:
            logger.error(f"Error during interactive planning: {e}", exc_info=True)
            console.print(f"[red]Erro durante o planejamento: {e}[/red]")
            return None

        return None

    def _display_message(self, message: AssistantMessage) -> None:
        """
        Display an assistant message to the user.

        Args:
            message: AssistantMessage from Claude
        """
        for block in message.content:
            if isinstance(block, TextBlock):
                # Display text with markdown support
                try:
                    md = Markdown(block.text)
                    console.print(md)
                except Exception:
                    # Fallback to plain text if markdown fails
                    console.print(block.text)

    def _is_cancel_command(self, text: str) -> bool:
        """
        Check if user input is a cancel command.

        Args:
            text: User input text

        Returns:
            True if it's a cancel command
        """
        cancel_commands = ['cancelar', 'sair', 'exit', 'quit', 'cancel']
        return text.lower() in cancel_commands

    def _handle_finalization(self, tool_result: Dict[str, Any]) -> bool:
        """
        Handle the finalization tool result.

        Args:
            tool_result: Result from finalize_plan tool

        Returns:
            True if successful, False if validation failed
        """
        if not tool_result.get('success', False):
            # Validation failed
            errors = tool_result.get('errors', [])
            console.print(Panel(
                "[bold red]Validação Falhou[/bold red]\n\n" +
                "\n".join(f"- {e}" for e in errors),
                border_style="red"
            ))
            return False

        # Extract plan data
        self.plan_data = tool_result.get('data', {})
        self._finalized = True

        # Display success message
        console.print()
        console.print(Panel(
            f"[bold green]✓ {tool_result.get('message', 'Plano criado com sucesso!')}[/bold green]",
            border_style="green"
        ))

        return True

    def _create_plan(self) -> Optional[Plan]:
        """
        Create a Plan object from the collected data.

        Returns:
            Plan object, or None if data is invalid
        """
        if not self.plan_data:
            logger.error("No plan data available to create plan")
            return None

        try:
            # Create Plan object
            plan = Plan(
                name=self.plan_data['name'],
                brief=self.plan_data['brief'],
                objectives=self.plan_data['objectives'],
                deliverables=self.plan_data['deliverables'],
                tags=self.plan_data.get('tags', []),
                author=self.plan_data.get('author', ''),
                status=PlanStatus.DRAFT,
                created_at=get_timestamp(),
                updated_at=get_timestamp(),
            )

            logger.info(f"Plan object created: {plan.name}")
            return plan

        except Exception as e:
            logger.error(f"Error creating plan: {e}", exc_info=True)
            console.print(f"[red]Erro ao criar plano: {e}[/red]")
            return None
