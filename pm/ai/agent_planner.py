"""AI-powered plan generator using Claude Agent SDK."""

from typing import Optional, Dict, Any
from rich.console import Console
from claude_agent_sdk import AssistantMessage

from .agent import GenericAgentClient
from .tools import create_plan_tools_server
from .prompts import INITIAL_PROMPT, PLAN_SYSTEM_PROMPT
from .session import PlanningSessionUI
from ..core.plan import Plan, PlanStatus
from ..core.config import Config
from ..utils.logger import get_logger
from ..utils.helpers import get_timestamp

logger = get_logger(__name__)
console = Console()

PROMPT_AGENT = """
Você é um Product Manager sênior especializado na criação de documentação de requisitos de produto (PRD).
Sua expertise está em **descoberta, análise e documentação** - nunca em implementação técnica.
Mantenha toda a sua atenção na construção do PRD!
""".strip()

class AgentPlanner:
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
        self._ui = PlanningSessionUI(console=console)

    async def interactive_planning(self) -> Optional[Plan]:
        """
        Execute the interactive planning flow with Claude.

        Returns:
            Created Plan object, or None if cancelled
        """
        self._ui.start_session()

        # Create custom tools server
        tools_server = create_plan_tools_server()

        try:
            async with GenericAgentClient(custom_tools=[tools_server], system_prompt=PLAN_SYSTEM_PROMPT, console=console) as agent:
                # Start conversation
                user_input = self._ui.request_initial_input(INITIAL_PROMPT)
                if user_input is None:
                    return None

                # Send initial message
                await agent.send_message(f"""# System Rules\n\n{PROMPT_AGENT}\n\n# User Input:\n\n{user_input}""")

                # Main conversation loop
                while not self._finalized:
                    # Receive and display agent responses
                    async for message in agent.receive_response():
                        if isinstance(message, AssistantMessage):
                            # Display message
                            # self._ui.handle_assistant_message(message)

                            # Check if plan was finalized
                            if agent.has_tool_use(message, "finalize_plan"):
                                tool_result = agent.extract_tool_input(message, "finalize_plan")
                                if tool_result:
                                    success = self._ui.handle_finalization_result(tool_result)
                                    if success:
                                        self._finalized = True
                                        self.plan_data = tool_result.get('data', {})
                                        # Create and return the plan
                                        return self._create_plan()

                    # If finalized, break out of loop
                    if self._finalized:
                        break

                    # Get next user input
                    self._ui.prepare_user_prompt()
                    user_input = self._ui.prompt_user_input()
                    if user_input is None:
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
