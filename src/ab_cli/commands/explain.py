#!/usr/bin/env python3
"""
explain - Quickly explain code, errors, or technical concepts using LLM.

Automatically gathers context from bash history, files, and environment.
"""
import argparse
import os
import re
import subprocess
import sys
from typing import Optional

from ab_cli.core.config import get_language
from ab_cli.utils import (
    call_llm_with_model_info,
    log_info,
    log_warning,
    GREEN,
    NC,
)


def get_bash_history(lines: int = 20) -> str:
    """Get last N lines from bash history."""
    histfile = os.environ.get('HISTFILE', os.path.expanduser('~/.bash_history'))

    if not os.path.exists(histfile):
        return ""

    try:
        with open(histfile, 'r', errors='ignore') as f:
            history_lines = f.readlines()
        # Get last N lines
        recent = history_lines[-lines:] if len(history_lines) >= lines else history_lines
        return ''.join(recent).strip()
    except Exception:
        return ""


def get_directory_listing(path: str = '.') -> str:
    """Get ls -la output for a directory."""
    try:
        result = subprocess.run(
            ['ls', '-la', path],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return ""


def extract_file_references(text: str) -> list[str]:
    """Extract potential file references from error messages."""
    patterns = [
        r"'([^']+\.[a-z]{1,4})'",  # 'file.py'
        r'"([^"]+\.[a-z]{1,4})"',  # "file.py"
        r'File "([^"]+)"',          # Python traceback
        r'in ([^\s]+\.[a-z]{1,4})',  # in file.py
        r'from ([^\s]+\.[a-z]{1,4})',  # from file.py
        r'([^\s]+\.[a-z]{1,4}):\d+',  # file.py:123
    ]

    files = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        files.extend(matches)

    # Filter to existing files
    existing = []
    for f in files:
        if os.path.isfile(f):
            existing.append(f)
    return list(set(existing))


def read_file_with_context(filepath: str, line: Optional[int] = None,
                           end_line: Optional[int] = None, context_lines: int = 10) -> str:
    """Read a file, optionally focusing on specific lines with context."""
    if not os.path.exists(filepath):
        return f"Error: File '{filepath}' not found"

    try:
        with open(filepath, 'r', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        return f"Error reading file: {e}"

    total_lines = len(lines)

    if line is not None:
        # Single line or range
        start = max(0, line - context_lines - 1)
        end = min(total_lines, (end_line or line) + context_lines)

        result_lines = []
        for i in range(start, end):
            line_num = i + 1
            marker = ">>>" if (line <= line_num <= (end_line or line)) else "   "
            result_lines.append(f"{marker} {line_num:4d}: {lines[i].rstrip()}")

        return '\n'.join(result_lines)
    else:
        # Entire file (limit to first 200 lines for context)
        if total_lines > 200:
            content = ''.join(lines[:200])
            content += f"\n\n... (truncated, {total_lines - 200} more lines)"
            return content
        return ''.join(lines)


def detect_input_type(input_text: str) -> str:
    """Detect what kind of input we're dealing with."""
    # Check if it's a file reference with line number
    if re.match(r'^[^\s:]+\.[a-z]{1,4}:\d+(-\d+)?$', input_text):
        return 'file_line'

    # Check if it looks like a file path
    if os.path.isfile(input_text):
        return 'file'

    # Check if it looks like an error message
    error_indicators = [
        'error', 'Error', 'ERROR',
        'exception', 'Exception', 'EXCEPTION',
        'failed', 'Failed', 'FAILED',
        'Traceback', 'traceback',
        'undefined', 'not found', 'not defined',
        'permission denied', 'Permission denied',
        'No such file', 'no such file',
    ]
    if any(indicator in input_text for indicator in error_indicators):
        return 'error'

    # Default to treating it as a concept/question
    return 'concept'


def parse_file_reference(ref: str) -> tuple[str, Optional[int], Optional[int]]:
    """Parse file:line or file:start-end reference."""
    if ':' not in ref:
        return ref, None, None

    parts = ref.rsplit(':', 1)
    filepath = parts[0]
    line_spec = parts[1]

    if '-' in line_spec:
        start, end = line_spec.split('-', 1)
        return filepath, int(start), int(end)
    else:
        return filepath, int(line_spec), None


def build_context(args, input_text: str, input_type: str) -> str:
    """Build context string based on input type and options."""
    context_parts = []

    # Add bash history context
    if args.history > 0:
        history = get_bash_history(args.history)
        if history:
            context_parts.append(f"=== RECENT BASH COMMANDS (last {args.history}) ===\n{history}")

    # Add directory listing
    if args.with_files:
        context_dir = args.context_dir or '.'
        listing = get_directory_listing(context_dir)
        if listing:
            context_parts.append(f"=== DIRECTORY LISTING ({context_dir}) ===\n{listing}")

    # For error messages, auto-detect and read referenced files
    if input_type == 'error' and args.with_files:
        referenced_files = extract_file_references(input_text)
        for filepath in referenced_files[:3]:  # Limit to 3 files
            content = read_file_with_context(filepath)
            context_parts.append(f"=== FILE: {filepath} ===\n{content}")

    # Add relevant environment variables for debugging
    if args.with_files and input_type == 'error':
        env_vars = ['PATH', 'PYTHONPATH', 'NODE_PATH', 'HOME', 'PWD']
        env_context = []
        for var in env_vars:
            val = os.environ.get(var)
            if val:
                env_context.append(f"{var}={val}")
        if env_context:
            context_parts.append("=== ENVIRONMENT ===\n" + '\n'.join(env_context))

    return '\n\n'.join(context_parts)


def generate_explanation(prompt_text: str, lang: str) -> str:
    """Generate explanation using LLM."""
    try:
        result, selected_model, _ = call_llm_with_model_info(prompt_text, lang=lang)

        log_info(f"Using model: {selected_model}")

        if not result:
            log_warning("API call failed for explanation")
            return ""

        return result.get('text', '').strip()
    except Exception as e:
        log_warning(f"Failed to generate explanation: {e}")
        return ""


def main():
    parser = argparse.ArgumentParser(
        description='Explain code, errors, or technical concepts using LLM',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  explain file.py                  # Explain entire file
  explain file.py:42               # Explain specific line
  explain file.py:10-50            # Explain line range
  explain "error: ECONNREFUSED"    # Explain error message
  explain --concept "dependency injection"  # Explain concept
  echo "stack trace" | explain -   # Explain from stdin
  explain --history 20 "command failed"  # Include bash history
  explain --with-files "No such file"    # Include dir listing
'''
    )
    parser.add_argument(
        'input',
        nargs='?',
        help='File path, file:line, error message, or concept to explain'
    )
    parser.add_argument(
        '-c', '--concept',
        type=str,
        help='Explain a technical concept'
    )
    parser.add_argument(
        '--history',
        type=int,
        default=0,
        help='Include last N lines from bash history as context'
    )
    parser.add_argument(
        '--with-files',
        action='store_true',
        help='Include directory listing and auto-read referenced files'
    )
    parser.add_argument(
        '--context-dir',
        type=str,
        help='Directory to use for context gathering (default: current)'
    )
    parser.add_argument(
        '-l', '--lang',
        default=None,
        help='Output language (default: en)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Provide detailed explanation'
    )

    args = parser.parse_args()

    # Get language from config if not specified
    lang = args.lang or get_language('explain')

    # Determine input source
    if args.concept:
        input_text = args.concept
        input_type = 'concept'
    elif args.input == '-':
        input_text = sys.stdin.read().strip()
        input_type = detect_input_type(input_text)
    elif args.input:
        input_text = args.input
        input_type = detect_input_type(input_text)
    else:
        parser.print_help()
        sys.exit(0)

    # Build prompt based on input type
    main_content = ""

    if input_type == 'file':
        content = read_file_with_context(input_text)
        main_content = f"=== FILE: {input_text} ===\n{content}"
        question = f"Explain what this code in '{input_text}' does."

    elif input_type == 'file_line':
        filepath, start_line, end_line = parse_file_reference(input_text)
        content = read_file_with_context(filepath, start_line, end_line)
        main_content = f"=== FILE: {filepath} ===\n{content}"
        if end_line:
            question = f"Explain lines {start_line}-{end_line} in '{filepath}'. Focus on the marked lines (>>>)."
        else:
            question = f"Explain line {start_line} in '{filepath}'. Focus on the marked line (>>>)."

    elif input_type == 'error':
        main_content = f"=== ERROR MESSAGE ===\n{input_text}"
        question = "Explain this error and suggest how to fix it."
        # Auto-enable history for errors
        if args.history == 0:
            args.history = 10

    elif input_type == 'concept':
        main_content = f"=== CONCEPT ===\n{input_text}"
        question = f"Explain the concept: {input_text}"

    # Build additional context
    context = build_context(args, input_text, input_type)

    # Build final prompt
    detail_level = "detailed and comprehensive" if args.verbose else "concise but clear"
    prompt_text = f"""You are a helpful technical assistant. Provide a {detail_level} explanation.

{main_content}

{context}

QUESTION: {question}

Respond in language: {lang}
"""

    log_info("Generating explanation...")

    explanation = generate_explanation(prompt_text, lang)

    if explanation:
        print()
        print(f"{GREEN}=== EXPLANATION ==={NC}")
        print(explanation)
        print()
    else:
        log_warning("No explanation generated")


if __name__ == '__main__':
    main()
