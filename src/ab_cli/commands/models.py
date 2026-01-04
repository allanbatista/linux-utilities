#!/usr/bin/env python3
"""
ab models - List and explore available LLM models from OpenRouter.

Usage:
    ab models                              List all models (table format)
    ab models list                         Same as above
    ab models list --free                  Show only free models
    ab models list --search <term>         Search by name/description
    ab models list --context-min <n>       Filter by minimum context length
    ab models list --modality <type>       Filter by modality (text, image, audio, video)
    ab models info <model-id>              Show detailed info for a model
"""
import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

import requests

from ab_cli.core.config import get_config

# ANSI color codes
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
BOLD = '\033[1m'
DIM = '\033[2m'
NC = '\033[0m'  # No Color


def log_info(msg: str) -> None:
    print(f"{BLUE}[INFO]{NC} {msg}")


def log_error(msg: str) -> None:
    print(f"{RED}[ERROR]{NC} {msg}", file=sys.stderr)


def log_warn(msg: str) -> None:
    print(f"{YELLOW}[WARN]{NC} {msg}", file=sys.stderr)


def fetch_models(api_base: str, api_key: str) -> Optional[List[Dict[str, Any]]]:
    """Fetch available models from OpenRouter API."""
    url = f"{api_base.rstrip('/')}/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get('data', [])
    except requests.exceptions.RequestException as e:
        log_error(f"Failed to fetch models: {e}")
        return None
    except json.JSONDecodeError as e:
        log_error(f"Invalid JSON response: {e}")
        return None


def format_price(pricing: Optional[Dict[str, Any]]) -> str:
    """Format pricing info for display."""
    if not pricing:
        return "N/A"

    try:
        prompt = float(pricing.get('prompt', '0') or '0')
        completion = float(pricing.get('completion', '0') or '0')

        if prompt == 0 and completion == 0:
            return f"{GREEN}FREE{NC}"

        # Convert to price per 1M tokens
        prompt_1m = prompt * 1_000_000
        completion_1m = completion * 1_000_000

        return f"${prompt_1m:.2f} / ${completion_1m:.2f}"
    except (ValueError, TypeError):
        return "N/A"


def format_context(context_length: Optional[int]) -> str:
    """Format context length for display."""
    if not context_length:
        return "N/A"

    if context_length >= 1_000_000:
        return f"{context_length / 1_000_000:.1f}M"
    elif context_length >= 1_000:
        return f"{context_length / 1_000:.0f}k"
    return str(context_length)


def get_modalities(model: Dict[str, Any]) -> str:
    """Extract input modalities from model."""
    arch = model.get('architecture', {})
    modalities = arch.get('input_modalities', [])

    if not modalities:
        # Fallback to modality field
        modality = arch.get('modality', '')
        if modality:
            return modality
        return "text"

    return ', '.join(modalities)


def truncate(text: str, max_len: int) -> str:
    """Truncate text to max length with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + '...'


def filter_models(models: List[Dict[str, Any]], args) -> List[Dict[str, Any]]:
    """Apply filters to model list."""
    filtered = models

    # Filter by free
    if args.free:
        def is_free(m):
            pricing = m.get('pricing', {})
            try:
                prompt = float(pricing.get('prompt', '0') or '0')
                completion = float(pricing.get('completion', '0') or '0')
                return prompt == 0 and completion == 0
            except (ValueError, TypeError):
                return False
        filtered = [m for m in filtered if is_free(m)]

    # Filter by search term
    if args.search:
        term = args.search.lower()
        def matches(m):
            name = (m.get('name') or '').lower()
            model_id = (m.get('id') or '').lower()
            desc = (m.get('description') or '').lower()
            return term in name or term in model_id or term in desc
        filtered = [m for m in filtered if matches(m)]

    # Filter by minimum context
    if args.context_min:
        filtered = [m for m in filtered if (m.get('context_length') or 0) >= args.context_min]

    # Filter by modality
    if args.modality:
        mod = args.modality.lower()
        def has_modality(m):
            modalities = get_modalities(m).lower()
            return mod in modalities
        filtered = [m for m in filtered if has_modality(m)]

    return filtered


def sort_models(models: List[Dict[str, Any]], sort_by: str) -> List[Dict[str, Any]]:
    """Sort models by specified field."""
    if sort_by == 'name':
        return sorted(models, key=lambda m: (m.get('name') or m.get('id') or '').lower())
    elif sort_by == 'context':
        return sorted(models, key=lambda m: m.get('context_length') or 0, reverse=True)
    elif sort_by == 'price':
        def get_price(m):
            pricing = m.get('pricing', {})
            try:
                return float(pricing.get('prompt', '0') or '0')
            except (ValueError, TypeError):
                return float('inf')
        return sorted(models, key=get_price)
    else:
        return models


def print_table(models: List[Dict[str, Any]], limit: int) -> None:
    """Print models in table format."""
    # Apply limit
    if limit > 0:
        models = models[:limit]

    if not models:
        print("No models found matching the criteria.")
        return

    # Calculate column widths
    id_width = min(40, max(len(m.get('id', '')) for m in models))
    name_width = min(30, max(len(m.get('name', '')) for m in models))

    # Header
    header = (
        f"{BOLD}{'ID':<{id_width}}{NC} | "
        f"{BOLD}{'Name':<{name_width}}{NC} | "
        f"{BOLD}{'Context':>8}{NC} | "
        f"{BOLD}{'Price/1M (in/out)':<20}{NC} | "
        f"{BOLD}{'Modality'}{NC}"
    )
    separator = '-' * (id_width + name_width + 60)

    print(header)
    print(separator)

    # Rows
    for model in models:
        model_id = truncate(model.get('id', 'N/A'), id_width)
        name = truncate(model.get('name', 'N/A'), name_width)
        context = format_context(model.get('context_length'))
        price = format_price(model.get('pricing'))
        modality = get_modalities(model)

        # Clean price for width calculation (remove ANSI codes)
        price_clean = price.replace(GREEN, '').replace(NC, '')

        print(
            f"{model_id:<{id_width}} | "
            f"{name:<{name_width}} | "
            f"{context:>8} | "
            f"{price:<20} | "
            f"{modality}"
        )

    print(separator)
    print(f"{DIM}Showing {len(models)} model(s){NC}")


def print_model_info(model: Dict[str, Any]) -> None:
    """Print detailed info for a single model."""
    model_id = model.get('id', 'N/A')
    name = model.get('name', 'N/A')
    description = model.get('description', 'No description available.')
    context_length = model.get('context_length', 'N/A')
    pricing = model.get('pricing', {})
    architecture = model.get('architecture', {})
    top_provider = model.get('top_provider', {})
    supported_params = model.get('supported_parameters', [])

    print(f"\n{BOLD}Model: {model_id}{NC}")
    print("=" * (len(model_id) + 7))
    print(f"{CYAN}Name:{NC}           {name}")
    print(f"{CYAN}Description:{NC}    {description[:200]}{'...' if len(description) > 200 else ''}")
    print(f"{CYAN}Context Length:{NC} {context_length:,} tokens" if isinstance(context_length, int) else f"{CYAN}Context Length:{NC} {context_length}")

    max_completion = top_provider.get('max_completion_tokens')
    if max_completion:
        print(f"{CYAN}Max Output:{NC}     {max_completion:,} tokens")

    print(f"\n{BOLD}Pricing (per 1M tokens):{NC}")
    prompt_price = float(pricing.get('prompt', '0') or '0') * 1_000_000
    completion_price = float(pricing.get('completion', '0') or '0') * 1_000_000
    if prompt_price == 0 and completion_price == 0:
        print(f"  {GREEN}FREE{NC}")
    else:
        print(f"  Prompt:       ${prompt_price:.4f}")
        print(f"  Completion:   ${completion_price:.4f}")

    print(f"\n{BOLD}Modalities:{NC}")
    input_mod = architecture.get('input_modalities', ['text'])
    output_mod = architecture.get('output_modalities', ['text'])
    print(f"  Input:        {', '.join(input_mod) if input_mod else 'text'}")
    print(f"  Output:       {', '.join(output_mod) if output_mod else 'text'}")

    if supported_params:
        print(f"\n{BOLD}Supported Parameters:{NC}")
        params_str = ', '.join(supported_params[:10])
        if len(supported_params) > 10:
            params_str += f" (+{len(supported_params) - 10} more)"
        print(f"  {params_str}")

    print()


def cmd_list(args) -> None:
    """List available models."""
    config = get_config()
    api_base = config.get_with_default('global.api_base')
    api_key_env = config.get_with_default('global.api_key_env')
    api_key = os.getenv(api_key_env)

    if not api_key:
        log_error(f"Environment variable {api_key_env} is not set.")
        log_error("Set it with: export OPENROUTER_API_KEY='your-key'")
        sys.exit(1)

    models = fetch_models(api_base, api_key)
    if models is None:
        sys.exit(1)

    # Apply filters
    models = filter_models(models, args)

    # Sort
    models = sort_models(models, args.sort)

    # Output
    if args.json:
        output = models[:args.limit] if args.limit > 0 else models
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print_table(models, args.limit)


def cmd_info(args) -> None:
    """Show detailed info for a specific model."""
    config = get_config()
    api_base = config.get_with_default('global.api_base')
    api_key_env = config.get_with_default('global.api_key_env')
    api_key = os.getenv(api_key_env)

    if not api_key:
        log_error(f"Environment variable {api_key_env} is not set.")
        log_error("Set it with: export OPENROUTER_API_KEY='your-key'")
        sys.exit(1)

    models = fetch_models(api_base, api_key)
    if models is None:
        sys.exit(1)

    # Find model by ID
    model_id = args.model_id
    model = None
    for m in models:
        if m.get('id') == model_id:
            model = m
            break

    if not model:
        # Try partial match
        matches = [m for m in models if model_id.lower() in m.get('id', '').lower()]
        if len(matches) == 1:
            model = matches[0]
        elif len(matches) > 1:
            log_error(f"Multiple models match '{model_id}':")
            for m in matches[:10]:
                print(f"  - {m.get('id')}", file=sys.stderr)
            if len(matches) > 10:
                print(f"  ... and {len(matches) - 10} more", file=sys.stderr)
            sys.exit(1)
        else:
            log_error(f"Model not found: {model_id}")
            sys.exit(1)

    if args.json:
        print(json.dumps(model, indent=2, ensure_ascii=False))
    else:
        print_model_info(model)


def main():
    parser = argparse.ArgumentParser(
        description='List and explore available LLM models from OpenRouter',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  ab models                          List all models
  ab models list --free              Show only free models
  ab models list --search claude     Search for "claude" in name/description
  ab models list --context-min 128000  Models with 128k+ context
  ab models list --modality image    Models supporting image input
  ab models list --sort price        Sort by price (cheapest first)
  ab models info openai/gpt-4o       Show details for specific model
'''
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # list subcommand
    list_parser = subparsers.add_parser('list', help='List available models')
    list_parser.add_argument('--free', action='store_true',
                             help='Show only free models')
    list_parser.add_argument('--search', '-s', type=str,
                             help='Search by name/description')
    list_parser.add_argument('--context-min', type=int,
                             help='Minimum context length')
    list_parser.add_argument('--modality', '-m', type=str,
                             help='Filter by modality (text, image, audio, video)')
    list_parser.add_argument('--limit', '-l', type=int, default=50,
                             help='Limit number of results (default: 50, 0 for all)')
    list_parser.add_argument('--sort', choices=['name', 'context', 'price'],
                             default='name', help='Sort by field (default: name)')
    list_parser.add_argument('--json', action='store_true',
                             help='Output as JSON')

    # info subcommand
    info_parser = subparsers.add_parser('info', help='Show model details')
    info_parser.add_argument('model_id', help='Model ID (e.g., openai/gpt-4o)')
    info_parser.add_argument('--json', action='store_true',
                             help='Output as JSON')

    args = parser.parse_args()

    # Default to list if no subcommand
    if not args.command:
        # Create default args for list
        args.command = 'list'
        args.free = False
        args.search = None
        args.context_min = None
        args.modality = None
        args.limit = 50
        args.sort = 'name'
        args.json = False

    commands = {
        'list': cmd_list,
        'info': cmd_info,
    }

    commands[args.command](args)


if __name__ == '__main__':
    main()
