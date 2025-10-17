"""Claude Agent SDK client for interactive plan generation."""

import os
from typing import Optional, Dict, Any, AsyncIterator
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock

os.environ["ANTHROPIC_API_KEY"] = ''

from .prompts import PLAN_SYSTEM_PROMPT
from ..utils.logger import get_logger

logger = get_logger(__name__)


class GenericAgentClient:
    """
    Client for interacting with Claude Agent SDK to generate plans.

    This class manages the lifecycle of an agent session and handles
    communication with Claude for interactive plan creation.
    """

    def __init__(self, custom_tools: Optional[list] = None, system_prompt: Optional[str] = None):
        """
        Initialize the Plan Agent Client.

        Args:
            custom_tools: List of custom tools to make available to the agent
        """
        self.custom_tools = custom_tools or []
        self.client: Optional[ClaudeSDKClient] = None
        self._conversation_history = []
        self.system_prompt = system_prompt

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
            logger.info("Thinking...")

            if not self.client:
                raise RuntimeError("Agent session not started. Use async with context manager.")

            logger.debug(f"Sending message: {message[:100]}...")
            self._conversation_history.append({"role": "user", "content": message})
            await self.client.query(message)
        except Exception as e:
            logger.error(f"Error sending message: {message}: {e}")
            raise

    async def receive_response(self) -> AsyncIterator[AssistantMessage]:
        """
        Receive streaming response from the agent.

        Yields:
            AssistantMessage objects from Claude
        """
        if not self.client:
            raise RuntimeError("Agent session not started. Use async with context manager.")

        async for message in self.client.receive_response():
            if isinstance(message, AssistantMessage):
                # Store in conversation history
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
