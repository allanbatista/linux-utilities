#!/usr/bin/env python3
"""
branch-name - Generate branch names from task descriptions using LLM.

Analyzes task description and generates appropriate branch names following
conventional naming patterns (feature/, fix/, chore/, etc.).
"""
import argparse
import re
import subprocess
import sys
from typing import Optional

from ab_cli.core.config import get_language
from ab_cli.utils import (
    call_llm,
    log_info,
    log_success,
    log_warning,
    log_error,
    GREEN,
    YELLOW,
    NC,
    is_git_repo,
    branch_exists,
    create_branch,
)


def extract_ticket_number(description: str) -> Optional[str]:
    """Extract ticket number from description (JIRA-123, #123, etc.)."""
    # Match patterns like JIRA-123, ABC-456, #123
    patterns = [
        r'([A-Z]+-\d+)',  # JIRA-style: ABC-123
        r'#(\d+)',         # GitHub-style: #123
    ]

    for pattern in patterns:
        match = re.search(pattern, description)
        if match:
            return match.group(1)

    return None


def generate_branch_name(description: str, lang: str, prefix: Optional[str] = None) -> str:
    """Generate branch name using LLM."""
    # Extract ticket number if present
    ticket = extract_ticket_number(description)
    ticket_context = f"\nTicket number found: {ticket}" if ticket else ""

    prompt_text = f"""Generate a git branch name from this task description.

RULES:
1. Return ONLY the branch name, nothing else
2. Use lowercase kebab-case (words-separated-by-dashes)
3. Max 50 characters total
4. Choose appropriate prefix based on task type:
   - feature/ for new features
   - fix/ for bug fixes
   - chore/ for maintenance tasks
   - refactor/ for code refactoring
   - docs/ for documentation
   - test/ for test-related changes
5. If a ticket number is present, include it after the prefix
6. Be concise but descriptive
{f'7. Force prefix: {prefix}/' if prefix else ''}

TASK DESCRIPTION:
{description}
{ticket_context}

Example outputs:
- "add user login" -> feature/add-user-login
- "JIRA-123: fix button alignment" -> fix/JIRA-123-button-alignment
- "update readme" -> docs/update-readme
- "#456 refactor auth module" -> refactor/456-auth-module

Return ONLY the branch name:"""

    try:
        result = call_llm(prompt_text, lang=lang)

        if not result:
            log_error("API call failed for branch name generation")
            return ""

        branch_name = result.get('text', '').strip()

        if not branch_name:
            log_warning("Empty response from LLM")
            return ""

        # Clean up the response (remove quotes, extra whitespace, etc.)
        branch_name = branch_name.strip('"\'`')
        # Take only the first line if multiple lines
        branch_name = branch_name.split('\n')[0].strip()
        branch_name = re.sub(r'\s+', '-', branch_name)
        branch_name = re.sub(r'[^a-zA-Z0-9/_-]', '', branch_name)

        # Ensure max length
        if len(branch_name) > 50:
            branch_name = branch_name[:50].rstrip('-')

        return branch_name
    except Exception as e:
        log_error(f"Failed to generate branch name: {e}")
        return ""


def main():
    parser = argparse.ArgumentParser(
        description='Generate branch names from task descriptions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  branch-name "add user authentication"
  branch-name "fix login button on mobile"
  branch-name "JIRA-123: implement payment gateway"
  branch-name --prefix feature "new dashboard"
  branch-name -c "add user validation"  # Create and checkout
'''
    )
    parser.add_argument(
        'description',
        nargs='?',
        help='Task description to generate branch name from'
    )
    parser.add_argument(
        '-c', '--create',
        action='store_true',
        help='Create and checkout the branch'
    )
    parser.add_argument(
        '-p', '--prefix',
        help='Force a specific prefix (feature, fix, chore, etc.)'
    )
    parser.add_argument(
        '-l', '--lang',
        default=None,
        help='Output language (default: en)'
    )
    parser.add_argument(
        '-y', '--yes',
        action='store_true',
        help='Skip confirmation when creating branch'
    )

    args = parser.parse_args()

    # Get language from config if not specified
    lang = args.lang or get_language('branch-name')

    # Check if description provided
    if not args.description:
        parser.print_help()
        sys.exit(0)

    # Check if in git repo when creating branch
    if args.create and not is_git_repo():
        log_error("Not a git repository")
        sys.exit(1)

    try:
        log_info("Generating branch name...")

        branch_name = generate_branch_name(args.description, lang, args.prefix)

        if not branch_name:
            log_error("Failed to generate branch name")
            sys.exit(1)

        print()
        print(f"{GREEN}Suggested branch name:{NC}")
        print(f"  {YELLOW}{branch_name}{NC}")
        print()

        if args.create:
            # Check if branch exists
            if branch_exists(branch_name):
                log_error(f"Branch '{branch_name}' already exists")
                sys.exit(1)

            # Confirm creation
            if not args.yes:
                response = input(f"Create and checkout '{branch_name}'? [Y/n] ").strip().lower()
                if response in ('n', 'no'):
                    log_warning("Cancelled")
                    sys.exit(0)

            # Create branch
            if create_branch(branch_name):
                log_success(f"Created and switched to '{branch_name}'")
            else:
                sys.exit(1)

    except subprocess.CalledProcessError as e:
        log_error(f"Command failed: {e}")
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        log_warning("Cancelled")
        sys.exit(130)


if __name__ == '__main__':
    main()
