"""LLM helper utilities for ab-cli.

Provides simplified interface for LLM API calls with automatic
model selection based on token count.
"""
from typing import Optional

from ab_cli.core.config import get_config, estimate_tokens
from ab_cli.commands.prompt import send_to_openrouter


def call_llm(
    prompt: str,
    context: str = "",
    lang: str = "en",
    specialist: Optional[str] = None,
    max_completion_tokens: int = -1,
) -> Optional[dict]:
    """Call LLM with automatic model selection based on token count.

    This is a simplified wrapper around send_to_openrouter that handles
    config retrieval and model selection automatically.

    Args:
        prompt: The prompt text to send to the LLM
        context: Additional context to include (default: "")
        lang: Output language (default: "en")
        specialist: Optional specialist persona (default: None)
        max_completion_tokens: Max tokens for completion, -1 for no limit

    Returns:
        dict with 'text' key containing response, or None on failure
    """
    config = get_config()

    # Estimate tokens and select appropriate model
    estimated_tokens = estimate_tokens(prompt + context)
    selected_model = config.select_model(estimated_tokens)

    # Get API settings from config
    timeout_s = config.get_with_default('global.timeout_seconds')
    api_key_env = config.get_with_default('global.api_key_env')
    api_base = config.get_with_default('global.api_base')

    return send_to_openrouter(
        prompt=prompt,
        context=context,
        lang=lang,
        specialist=specialist,
        model_name=selected_model,
        timeout_s=timeout_s,
        max_completion_tokens=max_completion_tokens,
        api_key_env=api_key_env,
        api_base=api_base
    )


def call_llm_with_model_info(
    prompt: str,
    context: str = "",
    lang: str = "en",
    specialist: Optional[str] = None,
    max_completion_tokens: int = -1,
) -> tuple[Optional[dict], str, int]:
    """Call LLM and return response with model info.

    Same as call_llm but also returns the selected model name
    and estimated token count for logging purposes.

    Args:
        prompt: The prompt text to send to the LLM
        context: Additional context to include (default: "")
        lang: Output language (default: "en")
        specialist: Optional specialist persona (default: None)
        max_completion_tokens: Max tokens for completion, -1 for no limit

    Returns:
        Tuple of (response_dict, model_name, estimated_tokens)
    """
    config = get_config()

    # Estimate tokens and select appropriate model
    estimated_tokens = estimate_tokens(prompt + context)
    selected_model = config.select_model(estimated_tokens)

    # Get API settings from config
    timeout_s = config.get_with_default('global.timeout_seconds')
    api_key_env = config.get_with_default('global.api_key_env')
    api_base = config.get_with_default('global.api_base')

    result = send_to_openrouter(
        prompt=prompt,
        context=context,
        lang=lang,
        specialist=specialist,
        model_name=selected_model,
        timeout_s=timeout_s,
        max_completion_tokens=max_completion_tokens,
        api_key_env=api_key_env,
        api_base=api_base
    )

    return result, selected_model, estimated_tokens


def get_llm_text(
    prompt: str,
    context: str = "",
    lang: str = "en",
    specialist: Optional[str] = None,
) -> Optional[str]:
    """Call LLM and return just the text response.

    Convenience function when you only need the text output.

    Args:
        prompt: The prompt text to send to the LLM
        context: Additional context to include (default: "")
        lang: Output language (default: "en")
        specialist: Optional specialist persona (default: None)

    Returns:
        The text response string, or None on failure
    """
    result = call_llm(prompt, context, lang, specialist)

    if result:
        return result.get('text', '').strip()

    return None
