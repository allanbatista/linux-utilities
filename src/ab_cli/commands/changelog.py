#!/usr/bin/env python3
"""
changelog - Generate changelog/release notes from commits.

Analyzes commits between tags/refs and generates structured changelog using LLM.
"""
import argparse
import subprocess
import sys

from ab_cli.core.config import get_config, estimate_tokens, get_language
from ab_cli.commands.prompt import send_to_openrouter
from ab_cli.utils import (
    log_info,
    log_success,
    log_warning,
    log_error,
    run_git,
    is_git_repo,
    get_latest_tag,
)


def get_commits(range_spec: str, oneline: bool = True) -> str:
    """Get commits in the specified range."""
    try:
        if oneline:
            result = run_git('log', '--oneline', range_spec)
        else:
            result = run_git('log', '--format=%H|%s|%b|%an|%aI', range_spec)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def get_commit_count(range_spec: str) -> int:
    """Get number of commits in range."""
    try:
        result = run_git('rev-list', '--count', range_spec)
        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0


def parse_commits(commits_str: str) -> list[dict]:
    """Parse commits into structured format."""
    commits = []
    for line in commits_str.split('\n'):
        if '|' in line:
            parts = line.split('|', 4)
            if len(parts) >= 4:
                commits.append({
                    'hash': parts[0],
                    'subject': parts[1],
                    'body': parts[2] if len(parts) > 2 else '',
                    'author': parts[3] if len(parts) > 3 else '',
                    'date': parts[4] if len(parts) > 4 else '',
                })
    return commits


def categorize_commits(commits: list[dict]) -> dict[str, list[dict]]:
    """Categorize commits by type (feat, fix, etc.)."""
    categories = {
        'features': [],
        'fixes': [],
        'refactor': [],
        'docs': [],
        'chore': [],
        'test': [],
        'other': [],
    }

    prefixes = {
        'feat': 'features',
        'feature': 'features',
        'fix': 'fixes',
        'bug': 'fixes',
        'refactor': 'refactor',
        'docs': 'docs',
        'doc': 'docs',
        'chore': 'chore',
        'test': 'test',
        'tests': 'test',
    }

    for commit in commits:
        subject = commit.get('subject', '').lower()
        categorized = False

        for prefix, category in prefixes.items():
            if subject.startswith(f'{prefix}:') or subject.startswith(f'{prefix}('):
                categories[category].append(commit)
                categorized = True
                break

        if not categorized:
            categories['other'].append(commit)

    return categories


def generate_changelog(commits: str, range_spec: str, format_type: str,
                       categorize: bool, lang: str) -> str:
    """Generate changelog using LLM."""
    config = get_config()

    category_instruction = ""
    if categorize:
        category_instruction = """
Group commits by type:
- Features: New functionality
- Bug Fixes: Bug fixes
- Refactoring: Code improvements without changing functionality
- Documentation: Documentation changes
- Other: Everything else
"""

    format_instructions = {
        'markdown': 'Use markdown format with headers (## Features, ## Bug Fixes, etc.) and bullet points.',
        'plain': 'Use plain text format with clear sections.',
        'json': 'Return a valid JSON object with categories as keys and arrays of changes as values.',
    }

    prompt_text = f"""Generate a changelog/release notes from these git commits.

COMMIT RANGE: {range_spec}

COMMITS:
{commits}

{category_instruction}

FORMAT: {format_instructions.get(format_type, format_instructions['markdown'])}

RULES:
1. Summarize related commits together when possible
2. Use clear, user-facing language (not technical git messages)
3. Highlight breaking changes if any
4. Be concise but informative
5. Respond in language: {lang}

Generate the changelog:"""

    estimated_tokens = estimate_tokens(prompt_text)
    selected_model = config.select_model(estimated_tokens)
    timeout_s = config.get_with_default('global.timeout_seconds')
    api_key_env = config.get_with_default('global.api_key_env')
    api_base = config.get_with_default('global.api_base')

    log_info(f"Using model: {selected_model}")

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
            log_error("API call failed for changelog generation")
            return ""

        return result.get('text', '').strip()
    except Exception as e:
        log_error(f"Failed to generate changelog: {e}")
        return ""


def main():
    parser = argparse.ArgumentParser(
        description='Generate changelog from git commits',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  changelog                        # Since last tag to HEAD
  changelog v1.0.0..v2.0.0         # Between two tags
  changelog HEAD~10..HEAD          # Last 10 commits
  changelog --format markdown      # Markdown output
  changelog --output CHANGELOG.md  # Write to file
  changelog --categories           # Group by type
'''
    )
    parser.add_argument(
        'range',
        nargs='?',
        help='Commit range (e.g., v1.0.0..v2.0.0). Default: last tag to HEAD'
    )
    parser.add_argument(
        '-f', '--format',
        default='markdown',
        choices=['markdown', 'plain', 'json'],
        help='Output format (default: markdown)'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Write output to file'
    )
    parser.add_argument(
        '-c', '--categories',
        action='store_true',
        help='Group commits by type (feat/fix/chore/etc.)'
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
    lang = args.lang or get_language('changelog')

    # Determine commit range
    if args.range:
        range_spec = args.range
    else:
        # Default: from last tag to HEAD
        latest_tag = get_latest_tag()
        if latest_tag:
            range_spec = f"{latest_tag}..HEAD"
            log_info(f"Using range: {range_spec}")
        else:
            # No tags, use all commits (limit to last 50)
            range_spec = "HEAD~50..HEAD"
            log_warning("No tags found, using last 50 commits")

    # Get commits
    commits = get_commits(range_spec)
    commit_count = get_commit_count(range_spec)

    if not commits:
        log_warning("No commits found in specified range")
        sys.exit(0)

    log_info(f"Found {commit_count} commits")

    log_info("Generating changelog...")

    changelog = generate_changelog(
        commits, range_spec, args.format,
        args.categories, lang
    )

    if not changelog:
        log_error("Failed to generate changelog")
        sys.exit(1)

    print()
    print(changelog)
    print()

    # Write to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            f.write(changelog + '\n')
        log_success(f"Changelog written to: {args.output}")


if __name__ == '__main__':
    main()
