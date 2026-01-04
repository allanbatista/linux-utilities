#!/usr/bin/env python3
"""
CLI to concatenate file contents and send to OpenRouter.

Configuration via `~/.ab/config.json` (optional).

Example `~/.ab/config.json`:
{
  "global": {
    "language": "en",
    "api_base": "https://openrouter.ai/api/v1",
    "api_key_env": "OPENROUTER_API_KEY",
    "timeout_seconds": 300
  },
  "models": {
    "default": "nvidia/nemotron-3-nano-30b-a3b:free"
  }
}

Flag `--set-default-model <model>` to **persist** the default model.
"""
import argparse
import os
import pathlib
import json
import requests
import pyperclip
import datetime
import sys
import subprocess
from typing import Optional, Tuple, Dict, Any, List

from binaryornot.check import is_binary
import pathspec

from ab_cli.core.config import get_config

VERBOSE = True

def pp(*args, **kwargs):
    if VERBOSE:
        print(*args, **kwargs)

# =========================
# Utilities and Persistence
# =========================

def load_config() -> Dict[str, Any]:
    """Load config from ~/.ab/config.json using centralized config module."""
    try:
        config = get_config()
        # Return in legacy format for compatibility
        return {
            "model": config.get("models.default"),
            "api_base": config.get("global.api_base"),
            "api_key_env": config.get("global.api_key_env"),
            "request": {
                "timeout_seconds": config.get("global.timeout_seconds", 300)
            }
        }
    except Exception as e:
        pp(f"Warning: could not read config: {e}")
    return {}


def persist_default_model(new_model: str) -> bool:
    """
    Update default model in ~/.ab/config.json (models.default key),
    preserving other fields. Creates the file if it doesn't exist.
    """
    try:
        config = get_config()
        config.set("models.default", new_model)
        return True
    except Exception as e:
        pp(f"Error persisting default model: {e}")
        return False


# =========================
# Providers
# =========================

def build_specialist_prefix(specialist: Optional[str]) -> str:
    specialist_prompts = {
        'dev': 'Act as a senior programmer specialized in software development, with over 20 years of experience. Your responses should be clear, efficient, well-structured and follow industry best practices. Think step by step.',
        'rm': 'Act as a senior Retail Media analyst, specialized in digital advertising strategies for e-commerce and marketplaces. Your knowledge covers platforms like Amazon Ads, Mercado Ads and Criteo. Your responses should be analytical, strategic and data-driven.'
    }
    return specialist_prompts.get(specialist or "", "")


def send_to_openrouter(prompt: str, context: str, lang: str, specialist: Optional[str],
                        model_name: str, timeout_s: int, max_completion_tokens: int = 256,
                        api_key_env: str = "OPENROUTER_API_KEY",
                        api_base: str = "https://openrouter.ai/api/v1") -> Optional[Dict[str, Any]]:
    """
    Sends the prompt and context to the OpenRouter API (OpenAI compatible).
    """
    api_key = os.getenv(api_key_env)
    if not api_key:
        # Always print error to stderr, regardless of VERBOSE
        print(f"Error: The environment variable {api_key_env} is not defined.", file=sys.stderr)
        return None

    # Build full prompt
    parts = []
    specialist_prefix = build_specialist_prefix(specialist)
    if specialist_prefix:
        parts.append(specialist_prefix)

    parts.append(prompt)

    if context.strip():
        parts.append("\n--- FILE CONTEXT ---\n" + context)

    parts.append(f"--- OUTPUT INSTRUCTION ---\nRespond strictly in language: {lang}.")

    full_prompt = "\n\n".join(parts)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    url = f"{api_base.rstrip('/')}/chat/completions"

    messages = [{"role": "user", "content": full_prompt}]
    if specialist_prefix:
        messages.insert(0, {"role": "system", "content": specialist_prefix})

    payload = {
        "model": model_name,
        "messages": messages,
    }

    if max_completion_tokens > 0:
        payload["max_tokens"] = max_completion_tokens

    try:
        pp(f"Sending request to OpenRouter ({model_name})...")
        response = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
        response.raise_for_status()
        data = response.json()

        message = data['choices'][0]['message']
        text_response = message.get('content') or ''

        # Handle reasoning models (gpt-5, o1, o3, etc.) that put response in reasoning field
        if not text_response and 'reasoning' in message:
            # For simple tasks, try to extract the final answer from reasoning
            reasoning = message.get('reasoning', '')
            # If the model ran out of tokens, reasoning might contain a partial answer
            if reasoning:
                pp(f"Note: Using reasoning field (model: {model_name}, content was empty)")
                text_response = reasoning

        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", "N/A")
        response_tokens = usage.get("completion_tokens", "N/A")

        return {
            "provider": "openrouter",
            "model": model_name,
            "text": text_response,
            "prompt_tokens": prompt_tokens,
            "response_tokens": response_tokens,
            "full_prompt": full_prompt,
        }

    except requests.exceptions.RequestException as e:
        # Always print errors to stderr regardless of VERBOSE mode
        print(f"Network or HTTP error calling OpenRouter: {e}", file=sys.stderr)
        if getattr(e, 'response', None) is not None:
            try:
                print(f"Error details: {e.response.text}", file=sys.stderr)
            except Exception:
                pass
        return None
    except (KeyError, IndexError) as e:
        print(f"Error extracting content from response: {e}", file=sys.stderr)
        try:
            print(f"Response structure received: {response.json()}", file=sys.stderr)
        except Exception:
            pass
        return None
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return None


# =========================
# History and Persistence
# =========================

def save_to_history(full_prompt: str, response_text: str, result: Dict[str, Any],
                     files_info: Dict[str, Any], args: argparse.Namespace) -> None:
    """
    Save full interaction history with LLM to ~/.ab/history/

    Information saved:
    - Request timestamp
    - Provider and model used
    - Full prompt and response
    - Token metrics (prompt, response, total)
    - Processed files information
    - Configuration used (specialist, language, etc)
    - Prompt hash to avoid duplicates
    """
    try:
        import hashlib

        # History directory
        history_dir = pathlib.Path.home() / ".ab" / "history"
        history_dir.mkdir(parents=True, exist_ok=True)

        # Filename based on timestamp
        timestamp = datetime.datetime.now()
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")

        # Prompt hash for unique reference
        prompt_hash = hashlib.md5(full_prompt.encode('utf-8')).hexdigest()[:8]

        # Full data structure
        history_entry = {
            "metadata": {
                "timestamp": timestamp.isoformat(),
                "timestamp_formatted": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "prompt_hash": prompt_hash,
                "session_id": f"{timestamp_str}_{prompt_hash}"
            },
            "provider_info": {
                "provider": result.get('provider', 'unknown'),
                "model": result.get('model', 'unknown'),
                "api_version": result.get('api_version', 'N/A')
            },
            "tokens": {
                "prompt_tokens": result.get('prompt_tokens', 'N/A'),
                "response_tokens": result.get('response_tokens', 'N/A'),
                "total_tokens": (
                    result.get('prompt_tokens', 0) + result.get('response_tokens', 0)
                    if isinstance(result.get('prompt_tokens'), int) and isinstance(result.get('response_tokens'), int)
                    else 'N/A'
                ),
                "estimated_cost_usd": calculate_estimated_cost(
                    result.get('model', ''),
                    result.get('prompt_tokens', 0),
                    result.get('response_tokens', 0)
                )
            },
            "files_info": {
                "processed_count": files_info.get('processed', 0),
                "error_count": files_info.get('errors', 0),
                "skipped_count": files_info.get('skipped', 0),
                "total_words": files_info.get('words', 0),
                "total_estimated_tokens": files_info.get('tokens', 0),
                "file_list": files_info.get('file_list', [])
            },
            "configuration": {
                "specialist": args.specialist if hasattr(args, 'specialist') else None,
                "language": args.lang if hasattr(args, 'lang') else 'en',
                "max_tokens": args.max_tokens if hasattr(args, 'max_tokens') else None,
                "max_tokens_doc": args.max_tokens_doc if hasattr(args, 'max_tokens_doc') else None,
                "max_completion_tokens": 0 if getattr(args, 'unlimited', False) else (args.max_completion_tokens if hasattr(args, 'max_completion_tokens') else 16000),
                "path_format": (
                    'relative' if args.relative_paths else
                    'name_only' if args.filename_only else
                    'full'
                ) if hasattr(args, 'relative_paths') else 'full'
            },
            "content": {
                "prompt": {
                    "full": full_prompt,
                    "length_chars": len(full_prompt),
                    "length_words": len(full_prompt.split())
                },
                "response": {
                    "full": response_text,
                    "length_chars": len(response_text),
                    "length_words": len(response_text.split()),
                    "preview": response_text[:500] + "..." if len(response_text) > 500 else response_text
                }
            },
            "statistics": {
                "prompt_to_response_ratio": round(len(response_text) / len(full_prompt), 2) if full_prompt else 0,
                "avg_response_word_length": round(len(response_text) / max(len(response_text.split()), 1), 2),
                "response_lines": response_text.count('\n') + 1
            }
        }

        # Save individual file
        history_file = history_dir / f"history_{timestamp_str}_{prompt_hash}.json"
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history_entry, f, indent=2, ensure_ascii=False)

        # Update master index
        update_history_index(history_dir, history_entry)

        pp(f"History saved: {history_file}")

    except Exception as e:
        pp(f"Warning: Could not save history: {e}")


def calculate_estimated_cost(model: str, prompt_tokens: int, response_tokens: int) -> float:
    """
    Calculate estimated cost based on model and tokens used.
    Approximate values (may vary).
    """
    if not isinstance(prompt_tokens, int) or not isinstance(response_tokens, int):
        return 0.0

    # Approximate prices per 1M tokens (USD) - update as needed
    pricing = {
        # OpenAI
        'gpt-4o': {'prompt': 2.50, 'response': 10.00},
        'gpt-4o-mini': {'prompt': 0.15, 'response': 0.60},
        'gpt-4-turbo': {'prompt': 10.00, 'response': 30.00},
        'gpt-4': {'prompt': 30.00, 'response': 60.00},
        'gpt-3.5-turbo': {'prompt': 0.50, 'response': 1.50},

        # Google Gemini (estimates)
        'gemini-1.5-pro': {'prompt': 3.50, 'response': 10.50},
        'gemini-1.5-flash': {'prompt': 0.075, 'response': 0.30},
        'gemini-pro': {'prompt': 0.50, 'response': 1.50},
    }

    # Find model price
    model_lower = model.lower()
    price_info = None

    for model_key, prices in pricing.items():
        if model_key in model_lower:
            price_info = prices
            break

    if not price_info:
        return 0.0

    # Calculate cost
    prompt_cost = (prompt_tokens / 1_000_000) * price_info['prompt']
    response_cost = (response_tokens / 1_000_000) * price_info['response']

    return round(prompt_cost + response_cost, 6)


def update_history_index(history_dir: pathlib.Path, entry: Dict[str, Any]) -> None:
    """
    Update the master index file with interaction summary.
    """
    index_file = history_dir / "index.json"

    try:
        if index_file.exists():
            with open(index_file, 'r', encoding='utf-8') as f:
                index = json.load(f)
        else:
            index = {
                "created_at": datetime.datetime.now().isoformat(),
                "total_interactions": 0,
                "total_tokens_used": 0,
                "total_estimated_cost": 0.0,
                "interactions": []
            }

        # Add interaction summary
        summary = {
            "session_id": entry['metadata']['session_id'],
            "timestamp": entry['metadata']['timestamp'],
            "provider": entry['provider_info']['provider'],
            "model": entry['provider_info']['model'],
            "tokens": entry['tokens'].get('total_tokens', 'N/A'),
            "cost": entry['tokens'].get('estimated_cost_usd', 0.0),
            "files_processed": entry['files_info']['processed_count'],
            "response_preview": entry['content']['response']['preview']
        }

        index['interactions'].insert(0, summary)  # Most recent first
        index['total_interactions'] = len(index['interactions'])

        # Update totals
        if isinstance(entry['tokens'].get('total_tokens'), int):
            index['total_tokens_used'] += entry['tokens']['total_tokens']

        if isinstance(entry['tokens'].get('estimated_cost_usd'), (int, float)):
            index['total_estimated_cost'] += entry['tokens']['estimated_cost_usd']
            index['total_estimated_cost'] = round(index['total_estimated_cost'], 6)

        # Save index
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2, ensure_ascii=False)

    except Exception as e:
        pp(f"Warning: Could not update index: {e}")


def cleanup_old_history(history_dir: pathlib.Path, keep_last: int = 100) -> None:
    """
    Remove old history files, keeping only the last N.
    """
    try:
        history_files = sorted(
            history_dir.glob("history_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        if len(history_files) > keep_last:
            for old_file in history_files[keep_last:]:
                old_file.unlink()

    except Exception as e:
        # Non-critical, silent log
        pass


# =========================
# Binary Detection
# =========================

def is_binary_file(file_path: pathlib.Path) -> bool:
    """
    Detect if a file is binary using the binaryornot library.

    Args:
        file_path: Path of the file to check.

    Returns:
        True if the file is binary, False if it's text.
    """
    try:
        return is_binary(str(file_path))
    except Exception:
        return True  # If can't read, assume binary


# =========================
# .aiignore Support
# =========================

def find_git_root(start_path: pathlib.Path) -> Optional[pathlib.Path]:
    """
    Find the git repository root from the starting path.

    Args:
        start_path: Starting path for search.

    Returns:
        Git root path or None if not in a repository.
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True, text=True, cwd=str(start_path)
        )
        if result.returncode == 0:
            return pathlib.Path(result.stdout.strip())
    except Exception:
        pass
    return None


def find_aiignore_files(start_path: pathlib.Path) -> List[pathlib.Path]:
    """
    Search for .aiignore files from starting directory to git root.

    Args:
        start_path: Starting path for search.

    Returns:
        List of .aiignore file paths found (from most specific to most general).
    """
    aiignore_files = []
    current = start_path.resolve()
    git_root = find_git_root(current)

    while current != current.parent:
        aiignore_path = current / '.aiignore'
        if aiignore_path.exists() and aiignore_path.is_file():
            aiignore_files.append(aiignore_path)

        # Stop at git root if found
        if git_root and current == git_root:
            break

        current = current.parent

    return aiignore_files


def load_aiignore_spec(aiignore_files: List[pathlib.Path]) -> Optional[pathspec.GitIgnoreSpec]:
    """
    Load and combine patterns from multiple .aiignore files.

    Args:
        aiignore_files: List of .aiignore paths (from most specific to most general).

    Returns:
        Combined spec or None if no patterns.
    """
    all_patterns = []

    # Process from most general (root) to most specific
    for aiignore_path in reversed(aiignore_files):
        try:
            with open(aiignore_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            all_patterns.extend(lines)
        except Exception as e:
            pp(f"Warning: Error reading {aiignore_path}: {e}")

    if not all_patterns:
        return None

    return pathspec.GitIgnoreSpec.from_lines(all_patterns)


def should_ignore_path(
    file_path: pathlib.Path,
    spec: Optional[pathspec.GitIgnoreSpec],
    base_path: pathlib.Path
) -> bool:
    """
    Check if a file should be ignored based on .aiignore patterns.

    Args:
        file_path: Absolute path of the file.
        spec: Compiled GitIgnore spec (or None).
        base_path: Base path for relative path calculation.

    Returns:
        True if the file should be ignored.
    """
    if spec is None:
        return False

    try:
        rel_path = file_path.relative_to(base_path)
        return spec.match_file(str(rel_path))
    except ValueError:
        # file_path is not relative to base_path
        return spec.match_file(str(file_path))


# =========================
# File Processing
# =========================

def process_file(file_path: pathlib.Path, path_format: str, max_tokens_doc: int) -> Tuple[str, int, int]:
    """
    Read file content, format header and truncate if necessary based on tokens.

    Args:
        file_path: Path of the file to process.
        path_format: How the path should be formatted ('full', 'relative', 'name_only').
        max_tokens_doc: Maximum estimated tokens for this file.

    Returns:
        Tuple containing formatted content, word count and estimated tokens.
    """
    try:
        display_path = ""
        if path_format == 'name_only':
            display_path = file_path.name
        elif path_format == 'relative':
            display_path = os.path.relpath(file_path.resolve(), pathlib.Path.cwd())
        else: # 'full'
            display_path = str(file_path.resolve())

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        original_tokens = len(content) // 4
        warning_message = ""

        if original_tokens > max_tokens_doc:
            max_chars = max_tokens_doc * 4
            content = content[:max_chars]
            warning_message = (
                f"// warning_content_truncated=\"true\" "
                f"original_token_count=\"{original_tokens}\" "
                f"new_token_count=\"{max_tokens_doc}\"\n"
            )
            pp(f"  -> Warning: File '{display_path}' was truncated to ~{max_tokens_doc} tokens.")

        word_count = len(content.split())
        estimated_tokens = len(content) // 4
        formatted_content = f"// filename=\"{display_path}\"\n{warning_message}{content}\n"

        return formatted_content, word_count, estimated_tokens
    except Exception as e:
        error_message = f"// error_processing_file=\"{file_path.resolve()}\"\n// Error: {e}\n"
        return error_message, 0, 0


# =========================
# Effective Configuration
# =========================

def resolve_settings(args, config: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve model/timeout/api_base/api_key_env from args + config."""
    # Model precedence: CLI > config > default
    model = args.model or config.get("model") or "nvidia/nemotron-3-nano-30b-a3b:free"

    # API key env var name
    api_key_env = config.get("api_key_env") or "OPENROUTER_API_KEY"

    # API base
    api_base = config.get("api_base") or "https://openrouter.ai/api/v1"

    # Timeout
    timeout_s = int(config.get("request", {}).get("timeout_seconds", 300))

    return {
        "model": model,
        "api_key_env": api_key_env,
        "api_base": api_base,
        "timeout_s": timeout_s,
    }


# =========================
# Main
# =========================

def main():
    """Main function that orchestrates script execution."""
    parser = argparse.ArgumentParser(
        description=(
            "Concatenate text file contents (ignores binaries) and "
            "optionally send to OpenRouter API.\n"
            "Use .aiignore to exclude files (gitignore syntax)."
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "paths",
        metavar="PATH",
        type=pathlib.Path,
        nargs='*',
        help="A list of files and/or directories to process."
    )
    parser.add_argument(
        "-p", "--prompt",
        type=str,
        help="An optional prompt to send to the API. Use '-' to read from stdin."
    )
    parser.add_argument(
        '--lang',
        type=str,
        default='en',
        help='Output language. Default: en'
    )
    parser.add_argument(
        '-n', '--max-tokens',
        type=int,
        default=900_000,
        help='Maximum estimated tokens for total context. Default: 900000'
    )
    parser.add_argument(
        '-nn', '--max-tokens-doc',
        type=int,
        default=250_000,
        help='Maximum estimated tokens per individual file. Default: 250000'
    )
    parser.add_argument(
        '-s', '--specialist',
        type=str,
        choices=['dev', 'rm'],
        help=(
            "Define a specialist persona:\n"
            "'dev' for Senior Programmer\n"
            "'rm'  for Senior Retail Media Analyst."
        )
    )
    parser.add_argument(
        '--model',
        type=str,
        help='OpenRouter model name to use. Ex: nvidia/nemotron-3-nano-30b-a3b:free'
    )
    parser.add_argument(
        '-m', '--max-completion-tokens',
        type=int,
        default=16000,
        help='Maximum tokens for model response. Default: 16000'
    )
    parser.add_argument(
        '-u', '--unlimited',
        action='store_true',
        help='Remove response token limit (does not send max_tokens to API)'
    )
    parser.add_argument(
        '--set-default-model',
        type=str,
        help='Set and persist the default model (top-level "model") in ~/.ab/config.json and exit.'
    )
    parser.add_argument(
        '--only-output',
        action='store_true',
        help="Return only the model result"
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help="Format result as JSON"
    )

    path_options = parser.add_mutually_exclusive_group()
    path_options.add_argument(
        "--relative-paths",
        action="store_true",
        help="Display relative paths instead of absolute paths."
    )
    path_options.add_argument(
        "--filename-only",
        action="store_true",
        help="Display only the filename instead of full path."
    )


    # If no arguments passed, show help
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    # If prompt is '-', read from stdin
    if args.prompt == '-':
        args.prompt = sys.stdin.read()

    global VERBOSE
    VERBOSE = not args.only_output

    # Update default model if requested
    if args.set_default_model:
        if persist_default_model(args.set_default_model):
            pp(f"Default model updated to: {args.set_default_model} in ~/.ab/config.json")
        else:
            pp("Error updating default model.")
        # If only set default and no prompt or paths provided, exit.
        if not args.prompt and len(args.paths) == 0:
            return

    # Load configurations
    config = load_config()
    settings = resolve_settings(args, config)

    path_format_option = 'full'
    if args.relative_paths:
        path_format_option = 'relative'
    elif args.filename_only:
        path_format_option = 'name_only'

    # Load .aiignore patterns
    aiignore_files = find_aiignore_files(pathlib.Path.cwd())
    aiignore_spec = load_aiignore_spec(aiignore_files)
    if aiignore_files:
        pp(f"Loaded .aiignore from: {', '.join(str(f) for f in aiignore_files)}")

    all_files_content = []
    total_word_count = 0
    total_estimated_tokens = 0
    files_processed_count = 0
    files_error_count = 0
    files_skipped_count = 0

    for path_arg in args.paths:
        if not path_arg.exists():
            pp(f"Warning: Path '{path_arg}' does not exist. Skipping.")
            continue

        base_path = path_arg.resolve() if path_arg.is_dir() else path_arg.parent.resolve()

        if path_arg.is_file():
            # Check .aiignore
            if should_ignore_path(path_arg.resolve(), aiignore_spec, base_path):
                pp(f"Ignored by .aiignore: {path_arg}")
                files_skipped_count += 1
                continue
            # Check if binary
            if is_binary_file(path_arg):
                pp(f"Ignored (binary): {path_arg}")
                files_skipped_count += 1
                continue
            # Process text file
            content, word_count, estimated_tokens = process_file(path_arg, path_format_option, args.max_tokens_doc)
            pp(f"Processing file: {path_arg.resolve()} ({word_count} words, ~{estimated_tokens} tokens)")
            if content.startswith("// error_processing_file"):
                files_error_count += 1
            else:
                files_processed_count += 1
                total_word_count += word_count
                total_estimated_tokens += estimated_tokens
            all_files_content.append(content)

        elif path_arg.is_dir():
            pp(f"Processing directory: {path_arg.resolve()}")
            for child_path in path_arg.rglob('*'):
                if child_path.is_file():
                    # Check .aiignore
                    if should_ignore_path(child_path.resolve(), aiignore_spec, base_path):
                        files_skipped_count += 1
                        continue
                    # Check if binary
                    if is_binary_file(child_path):
                        files_skipped_count += 1
                        continue
                    # Process text file
                    content, word_count, estimated_tokens = process_file(child_path, path_format_option, args.max_tokens_doc)
                    pp(f"  -> Processing: {child_path.relative_to(path_arg)} ({word_count} words, ~{estimated_tokens} tokens)")
                    if content.startswith("// error_processing_file"):
                        files_error_count += 1
                    else:
                        files_processed_count += 1
                        total_word_count += word_count
                        total_estimated_tokens += estimated_tokens
                    all_files_content.append(content)
        else:
            pp(f"Warning: Path '{path_arg}' is not a file or directory. Skipping.")

    final_text = "".join(all_files_content)

    # If no files were processed
    if not final_text and not args.prompt:
        pp("\nNo valid files were found or processed.")
        if files_skipped_count > 0:
            pp(f"{files_skipped_count} file(s) were ignored (binary or .aiignore).")
        return

    original_total_tokens = len(final_text) // 4
    if args.max_tokens and original_total_tokens > args.max_tokens:
        pp(f"\nWarning: Final context with ~{original_total_tokens} tokens exceeded limit of {args.max_tokens}. Truncating...")
        max_chars = args.max_tokens * 4
        final_text = final_text[:max_chars]
        pp(f"New estimated token count in context: ~{len(final_text) // 4}")

    # Make OpenRouter call if prompt exists
    if args.prompt:
        model = settings["model"]
        timeout_s = settings["timeout_s"]
        api_key_env = settings["api_key_env"]
        api_base = settings["api_base"]

        max_tokens = 0 if args.unlimited else args.max_completion_tokens
        result = send_to_openrouter(
            args.prompt, final_text, args.lang, args.specialist,
            model, timeout_s, max_tokens,
            api_key_env=api_key_env, api_base=api_base
        )

        if result:
            response_text = result['text']

            if VERBOSE:
                pp("\n--- REQUEST INFORMATION ---")
                pp(f"Provider Used: {result['provider']}")
                pp(f"Model Used: {result['model']}")
                pp(f"Files Processed: {files_processed_count} ({total_word_count} words, ~{total_estimated_tokens} tokens) | Errors: {files_error_count} | Ignored: {files_skipped_count}")
                pp(f"Tokens Sent (API): {result['prompt_tokens']}")
                pp(f"Tokens Received (API): {result['response_tokens']}")
                pp("---------------------------------")

                pp("\n--- MODEL RESPONSE ---\n")
                pp(response_text)
                pp("\n--------------------------\n")
            else:
                text = response_text.strip()

                if args.json:
                    if text.startswith('```json'):
                        text = text.replace('```json', '').replace('```', '')

                    try:
                        text = json.dumps(json.loads(text), indent=4)
                    except:
                        pass

                print(text, flush=True)

            # Skip clipboard when not in verbose mode (subprocess calls)
            if VERBOSE:
                try:
                    pyperclip.copy(response_text)
                    pp("Response copied to clipboard!")
                except pyperclip.PyperclipException as e:
                    pp(f"Error: Could not copy to clipboard. {e}")

            # Prepare processed files information
            files_info = {
                'processed': files_processed_count,
                'errors': files_error_count,
                'skipped': files_skipped_count,
                'words': total_word_count,
                'tokens': total_estimated_tokens,
                'file_list': [str(p) for p in args.paths]
            }

            save_to_history(result['full_prompt'], response_text, result, files_info, args)
        else:
            # API call failed - exit with error code
            sys.exit(1)
        return

    # If no prompt but file content exists, copy to clipboard
    if final_text:
        try:
            pyperclip.copy(final_text)
            pp(f"\nProcessed {files_processed_count} file(s) successfully ({total_word_count} words, ~{total_estimated_tokens} tokens total).")
            if files_skipped_count > 0:
                 pp(f"{files_skipped_count} file(s) were ignored (binary or .aiignore).")
            if files_error_count > 0:
                pp(f"Found errors in {files_error_count} file(s).")
            pp("Combined content was copied to your clipboard!")
        except pyperclip.PyperclipException as e:
            pp(f"\nError: Could not copy to clipboard. {e}")
            pp("\nHere is the combined output:\n")
            pp("--------------------------------------------------")
            pp(final_text)
            pp("--------------------------------------------------")


if __name__ == "__main__":
    main()
