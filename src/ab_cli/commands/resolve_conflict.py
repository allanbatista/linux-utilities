#!/usr/bin/env python3
"""
resolve-conflict - Analyze merge conflicts and suggest resolutions using LLM.

Detects conflict markers, extracts versions, and suggests merged content.
"""
import argparse
import os
import subprocess
import sys
from typing import Optional

from ab_cli.core.config import get_config, estimate_tokens, get_language
from ab_cli.commands.prompt import send_to_openrouter

# ANSI colors
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
NC = '\033[0m'  # No Color


def log_info(msg: str) -> None:
    print(f"{BLUE}[INFO]{NC} {msg}")


def log_success(msg: str) -> None:
    print(f"{GREEN}[SUCCESS]{NC} {msg}")


def log_warning(msg: str) -> None:
    print(f"{YELLOW}[WARNING]{NC} {msg}")


def log_error(msg: str) -> None:
    print(f"{RED}[ERROR]{NC} {msg}", file=sys.stderr)


def run_git(*args, capture: bool = True, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command."""
    cmd = ['git'] + list(args)
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=check
    )


def is_git_repo() -> bool:
    """Check if current directory is inside a git repository."""
    try:
        run_git('rev-parse', '--is-inside-work-tree')
        return True
    except subprocess.CalledProcessError:
        return False


def get_conflicted_files() -> list[str]:
    """Get list of files with merge conflicts."""
    try:
        result = run_git('diff', '--name-only', '--diff-filter=U')
        if result.stdout.strip():
            return result.stdout.strip().split('\n')
    except subprocess.CalledProcessError:
        pass
    return []


def has_conflict_markers(content: str) -> bool:
    """Check if content has conflict markers."""
    return '<<<<<<<' in content and '=======' in content and '>>>>>>>' in content


def parse_conflicts(content: str) -> list[dict]:
    """Parse conflict sections from file content."""
    conflicts = []
    lines = content.split('\n')

    i = 0
    while i < len(lines):
        if lines[i].startswith('<<<<<<<'):
            conflict = {
                'start_line': i + 1,
                'ours_marker': lines[i],
                'ours': [],
                'theirs': [],
                'theirs_marker': '',
                'end_line': 0,
            }

            i += 1
            # Collect "ours" version
            while i < len(lines) and not lines[i].startswith('======='):
                conflict['ours'].append(lines[i])
                i += 1

            if i < len(lines):
                i += 1  # Skip =======

            # Collect "theirs" version
            while i < len(lines) and not lines[i].startswith('>>>>>>>'):
                conflict['theirs'].append(lines[i])
                i += 1

            if i < len(lines):
                conflict['theirs_marker'] = lines[i]
                conflict['end_line'] = i + 1
                i += 1

            conflicts.append(conflict)
        else:
            i += 1

    return conflicts


def get_file_context(filepath: str, conflict: dict, context_lines: int = 10) -> tuple[str, str]:
    """Get context before and after the conflict."""
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
    except Exception:
        return "", ""

    start = max(0, conflict['start_line'] - context_lines - 1)
    end = min(len(lines), conflict['end_line'] + context_lines)

    before = ''.join(lines[start:conflict['start_line'] - 1])
    after = ''.join(lines[conflict['end_line']:end])

    return before, after


def resolve_conflict_with_llm(filepath: str, conflict: dict,
                              lang: str, dry_run: bool = False) -> Optional[str]:
    """Resolve a single conflict using LLM."""
    config = get_config()

    before_context, after_context = get_file_context(filepath, conflict)

    ours_code = '\n'.join(conflict['ours'])
    theirs_code = '\n'.join(conflict['theirs'])

    # Extract branch names from markers
    ours_branch = conflict['ours_marker'].replace('<<<<<<<', '').strip() or 'HEAD'
    theirs_branch = conflict['theirs_marker'].replace('>>>>>>>', '').strip() or 'incoming'

    prompt_text = f"""You are a code merging assistant. Resolve this merge conflict by producing the correct merged code.

FILE: {filepath}
CONFLICT LOCATION: lines {conflict['start_line']}-{conflict['end_line']}

CONTEXT BEFORE CONFLICT:
{before_context}

=== OUR VERSION ({ours_branch}) ===
{ours_code}

=== THEIR VERSION ({theirs_branch}) ===
{theirs_code}

CONTEXT AFTER CONFLICT:
{after_context}

INSTRUCTIONS:
1. Analyze both versions and understand what each is trying to accomplish
2. Merge the changes intelligently - include both changes if they don't conflict logically
3. If they truly conflict (same code modified differently), choose the better implementation
4. Return ONLY the resolved code, no explanations, no conflict markers
5. The result should be valid, working code

RESOLVED CODE:"""

    estimated_tokens = estimate_tokens(prompt_text)
    selected_model = config.select_model(estimated_tokens)
    timeout_s = config.get_with_default('global.timeout_seconds')
    api_key_env = config.get_with_default('global.api_key_env')
    api_base = config.get_with_default('global.api_base')

    try:
        result = send_to_openrouter(
            prompt=prompt_text,
            context="",
            lang=lang,
            specialist=None,
            model_name=selected_model,
            timeout_s=timeout_s,
            max_completion_tokens=-1,  # No limit
            api_key_env=api_key_env,
            api_base=api_base
        )

        if not result:
            log_error("API call failed for conflict resolution")
            return None

        resolved = result.get('text', '').strip()

        # Clean up markdown code fences if present
        if resolved.startswith('```'):
            lines = resolved.split('\n')
            lines = lines[1:]  # Remove first line
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            resolved = '\n'.join(lines)

        return resolved
    except Exception as e:
        log_error(f"Failed to resolve conflict: {e}")
        return None


def apply_resolution(filepath: str, conflict: dict, resolved_code: str) -> bool:
    """Apply the resolved code to the file."""
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()

        # Replace conflict section with resolved code
        new_lines = (
            lines[:conflict['start_line'] - 1] +
            [resolved_code + '\n'] +
            lines[conflict['end_line']:]
        )

        with open(filepath, 'w') as f:
            f.writelines(new_lines)

        return True
    except Exception as e:
        log_error(f"Failed to apply resolution: {e}")
        return False


def display_resolution(filepath: str, conflict: dict, resolved: str) -> None:
    """Display the proposed resolution."""
    print(f"\n{CYAN}=== CONFLICT IN {filepath} (lines {conflict['start_line']}-{conflict['end_line']}) ==={NC}")

    print(f"\n{RED}--- OUR VERSION ---{NC}")
    print('\n'.join(conflict['ours']))

    print(f"\n{YELLOW}--- THEIR VERSION ---{NC}")
    print('\n'.join(conflict['theirs']))

    print(f"\n{GREEN}--- PROPOSED RESOLUTION ---{NC}")
    print(resolved)
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Resolve merge conflicts using LLM',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  resolve-conflict              # Interactive mode for all conflicts
  resolve-conflict file.py      # Resolve specific file
  resolve-conflict -y           # Auto-apply suggestions
  resolve-conflict --dry-run    # Preview suggestions only
'''
    )
    parser.add_argument(
        'file',
        nargs='?',
        help='Specific file to resolve (default: all conflicted files)'
    )
    parser.add_argument(
        '-y', '--yes',
        action='store_true',
        help='Auto-apply resolutions without confirmation'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview resolutions without applying'
    )
    parser.add_argument(
        '-l', '--lang',
        default=None,
        help='Output language (default: en)'
    )

    args = parser.parse_args()

    # Check if in git repo
    if not is_git_repo():
        log_error("Not inside a git repository")
        sys.exit(1)

    # Get language from config if not specified
    lang = args.lang or get_language('resolve-conflict')

    # Get files to process
    if args.file:
        if not os.path.exists(args.file):
            log_error(f"File not found: {args.file}")
            sys.exit(1)
        files = [args.file]
    else:
        files = get_conflicted_files()

    if not files:
        log_warning("No conflicted files found")
        sys.exit(0)

    log_info(f"Found {len(files)} file(s) with conflicts")

    resolved_count = 0
    skipped_count = 0

    for filepath in files:
        try:
            with open(filepath, 'r') as f:
                content = f.read()
        except Exception as e:
            log_error(f"Cannot read {filepath}: {e}")
            continue

        if not has_conflict_markers(content):
            log_info(f"No conflicts in {filepath}")
            continue

        conflicts = parse_conflicts(content)
        log_info(f"Processing {filepath}: {len(conflicts)} conflict(s)")

        for i, conflict in enumerate(conflicts, 1):
            log_info(f"Resolving conflict {i}/{len(conflicts)} in {filepath}...")

            resolved = resolve_conflict_with_llm(filepath, conflict, lang, args.dry_run)

            if not resolved:
                log_warning(f"Could not resolve conflict {i} in {filepath}")
                skipped_count += 1
                continue

            display_resolution(filepath, conflict, resolved)

            if args.dry_run:
                log_info("Dry run - not applying changes")
                continue

            if args.yes:
                if apply_resolution(filepath, conflict, resolved):
                    log_success(f"Applied resolution to {filepath}")
                    resolved_count += 1
                    # Re-read file for next conflict (line numbers changed)
                    with open(filepath, 'r') as f:
                        content = f.read()
                    conflicts = parse_conflicts(content)
                else:
                    skipped_count += 1
            else:
                try:
                    choice = input(f"Apply this resolution? [{GREEN}y{NC}/n/e(dit)] ").strip().lower()
                except EOFError:
                    choice = 'n'

                if choice == 'y' or choice == '':
                    if apply_resolution(filepath, conflict, resolved):
                        log_success(f"Applied resolution to {filepath}")
                        resolved_count += 1
                        # Re-read file for next conflict
                        with open(filepath, 'r') as f:
                            content = f.read()
                        conflicts = parse_conflicts(content)
                    else:
                        skipped_count += 1
                elif choice == 'e':
                    log_info("Opening file in editor...")
                    editor = os.environ.get('EDITOR', 'vim')
                    subprocess.run([editor, filepath])
                    skipped_count += 1
                else:
                    log_info("Skipped")
                    skipped_count += 1

    print()
    log_info(f"Summary: {resolved_count} resolved, {skipped_count} skipped")

    if resolved_count > 0:
        log_info("Run 'git add' on resolved files, then 'git commit' to complete the merge")


if __name__ == '__main__':
    main()
