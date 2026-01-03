#!/usr/bin/env python3
"""
pr-description - Generate PR title and description using LLM.

Analyzes commits and diff relative to base branch.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

from ab_cli.core.config import get_config, estimate_tokens, get_language

# ANSI colors
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
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


def get_repo_root() -> str:
    """Get the root directory of the git repository."""
    result = run_git('rev-parse', '--show-toplevel')
    return result.stdout.strip()


def get_current_branch() -> str:
    """Get the current branch name."""
    result = run_git('rev-parse', '--abbrev-ref', 'HEAD')
    return result.stdout.strip()


def detect_base_branch() -> str:
    """Detect base branch (main/master/develop)."""
    # Priority: main > master > develop (local)
    for branch in ['main', 'master', 'develop']:
        try:
            run_git('show-ref', '--verify', '--quiet', f'refs/heads/{branch}')
            return branch
        except subprocess.CalledProcessError:
            pass

    # Fallback: try remote
    for branch in ['main', 'master', 'develop']:
        try:
            run_git('show-ref', '--verify', '--quiet', f'refs/remotes/origin/{branch}')
            return f'origin/{branch}'
        except subprocess.CalledProcessError:
            pass

    return ""


def get_commits_ahead(base_branch: str, current_branch: str) -> int:
    """Get number of commits ahead of base branch."""
    try:
        result = run_git('rev-list', '--count', f'{base_branch}..{current_branch}')
        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0


def get_commits_log(base_branch: str, current_branch: str) -> str:
    """Get commit log between branches."""
    try:
        result = run_git('log', '--oneline', f'{base_branch}..{current_branch}')
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def get_diff(base_branch: str, current_branch: str) -> str:
    """Get diff between branches."""
    try:
        result = run_git('diff', f'{base_branch}...{current_branch}')
        return result.stdout
    except subprocess.CalledProcessError:
        return ""


def get_files_changed(base_branch: str, current_branch: str) -> str:
    """Get list of changed files with status."""
    try:
        result = run_git('diff', '--name-status', f'{base_branch}...{current_branch}')
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def check_gh_installed() -> bool:
    """Check if gh CLI is installed."""
    return shutil.which('gh') is not None


def check_gh_authenticated() -> bool:
    """Check if gh CLI is authenticated."""
    try:
        subprocess.run(['gh', 'auth', 'status'], capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def create_pr(title: str, body: str, base_branch: str, draft: bool = False) -> str:
    """Create PR using gh CLI. Returns PR URL."""
    cmd = ['gh', 'pr', 'create', '--title', title, '--body', body, '--base', base_branch]
    if draft:
        cmd.append('--draft')

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)

    return result.stdout.strip()


def find_prompt_command() -> str:
    """Find the ab-prompt command."""
    import pathlib
    module_dir = pathlib.Path(__file__).parent.parent.parent.parent
    prompt_cmd = module_dir / 'bin' / 'ab-prompt'
    if prompt_cmd.exists():
        return str(prompt_cmd)

    if shutil.which('ab-prompt'):
        return 'ab-prompt'

    raise FileNotFoundError("Could not find ab-prompt command")


def generate_pr_content(commits: str, diff: str, files_changed: str,
                        current_branch: str, base_branch: str,
                        lang: str, prompt_cmd: str) -> tuple:
    """Generate PR title and description using LLM."""
    config = get_config()

    prompt_text = f"""Analyze the commits and changes below and generate title and description for a Pull Request.

RULES:
1. Respond EXACTLY in the format specified below
2. Title: maximum 72 characters, concise and descriptive
3. Write in language: {lang}
4. Use bullet points in Summary (2-4 main points)
5. List only the most relevant files in Changes
6. Suggest 2-4 tests in Testing

BRANCH: {current_branch}
BASE: {base_branch}

COMMITS:
{commits}

FILES CHANGED:
{files_changed}

DIFF:
{diff}

RESPONSE FORMAT (follow exactly):
TITLE: <concise title here>

DESCRIPTION:
## Summary
- point 1
- point 2

## Changes
- file: change description

## Testing
- [ ] test 1
- [ ] test 2
"""

    # Estimate tokens and select model
    estimated_tokens = estimate_tokens(prompt_text)
    selected_model = config.select_model(estimated_tokens)

    log_info(f"Estimated tokens: ~{estimated_tokens} | Model: {selected_model} | Lang: {lang}")
    print()

    # Write prompt to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(prompt_text)
        prompt_file = f.name

    try:
        result = subprocess.run(
            [prompt_cmd, '--model', selected_model, '--lang', lang,
             '--max-completion-tokens', '-1', '--only-output', '--prompt', '-'],
            stdin=open(prompt_file, 'r'),
            capture_output=True,
            text=True,
            check=True
        )
        response = result.stdout.strip()
    finally:
        os.unlink(prompt_file)

    if not response:
        return None, None

    # Parse response
    title_match = re.search(r'^TITLE:\s*(.+)$', response, re.MULTILINE)
    if title_match:
        pr_title = title_match.group(1).strip()
    else:
        # Fallback: use first line
        pr_title = response.split('\n')[0].strip()

    desc_match = re.search(r'^DESCRIPTION:\s*\n(.+)', response, re.MULTILINE | re.DOTALL)
    if desc_match:
        pr_body = desc_match.group(1).strip()
    else:
        # Fallback: use everything after first line
        lines = response.split('\n')
        pr_body = '\n'.join(lines[1:]).strip() if len(lines) > 1 else response

    return pr_title, pr_body


def main():
    parser = argparse.ArgumentParser(
        description='Automatically generates PR title and description using the prompt utility',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  pr-description                    # Generate title and description
  pr-description -c                 # Generate and create PR
  pr-description -c -d              # Create PR as draft
  pr-description -b develop -c -y   # Create PR to develop without confirmation
  pr-description -l pt-br           # Generate in Portuguese
'''
    )

    parser.add_argument('-b', '--base', type=str, default='',
                        help='Base branch (default: auto-detect main/master)')
    parser.add_argument('-c', '--create', action='store_true',
                        help='Create PR using gh CLI')
    parser.add_argument('-d', '--draft', action='store_true',
                        help='Create as draft (requires -c)')
    parser.add_argument('-l', '--lang', type=str,
                        default=get_language('pr-description'),
                        help=f'Output language (default: {get_language("pr-description")})')
    parser.add_argument('-y', '--yes', action='store_true',
                        help='Skip confirmation')

    args = parser.parse_args()

    # Check if inside git repo
    if not is_git_repo():
        log_error("Not inside a git repository")
        sys.exit(1)

    # Find prompt command
    try:
        prompt_cmd = find_prompt_command()
    except FileNotFoundError as e:
        log_error(str(e))
        sys.exit(1)

    # Check gh CLI if creating PR
    if args.create:
        if not check_gh_installed():
            log_error("gh CLI is not installed. Install with: sudo apt install gh")
            sys.exit(1)
        if not check_gh_authenticated():
            log_error("gh is not authenticated. Run: gh auth login")
            sys.exit(1)

    # Change to repo root
    os.chdir(get_repo_root())

    # Detect base branch
    base_branch = args.base or detect_base_branch()
    if not base_branch:
        log_error("Could not detect base branch. Use -b to specify.")
        sys.exit(1)

    # Get current branch
    current_branch = get_current_branch()

    log_info(f"Current branch: {current_branch}")
    log_info(f"Base branch: {base_branch}")

    # Check not on base branch
    if current_branch == base_branch:
        log_error(f"You are on the base branch ({base_branch}). Create a feature branch first.")
        sys.exit(1)

    # Check commits ahead
    commits_ahead = get_commits_ahead(base_branch, current_branch)
    if commits_ahead == 0:
        log_warning(f"No commits ahead of {base_branch}")
        sys.exit(0)

    log_info(f"Commits ahead: {commits_ahead}")
    print()

    # Analyze changes
    log_info("Analyzing changes...")

    commits = get_commits_log(base_branch, current_branch)
    diff = get_diff(base_branch, current_branch)
    files_changed = get_files_changed(base_branch, current_branch)

    if not diff:
        log_warning(f"No changes detected compared to {base_branch}")
        sys.exit(0)

    # Generate PR content
    log_info("Generating PR title and description...")

    try:
        pr_title, pr_body = generate_pr_content(
            commits, diff, files_changed,
            current_branch, base_branch,
            args.lang, prompt_cmd
        )
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to generate PR description: {e}")
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        sys.exit(1)

    if not pr_title:
        log_error("Failed to generate PR description")
        sys.exit(1)

    # Show result
    print(f"{GREEN}PR Title:{NC}")
    print("-" * 40)
    print(pr_title)
    print("-" * 40)
    print()
    print(f"{GREEN}PR Description:{NC}")
    print("-" * 40)
    print(pr_body)
    print("-" * 40)
    print()

    # Create PR if requested
    if args.create:
        if not args.yes:
            try:
                reply = input("Create PR with this content? (Y/n) ").strip().lower()
            except EOFError:
                reply = 'n'

            if reply == 'n':
                log_warning("PR creation cancelled")
                sys.exit(0)

        log_info("Creating PR...")

        try:
            pr_url = create_pr(pr_title, pr_body, base_branch, args.draft)
            print()
            log_success("PR created successfully!")
            log_info(f"URL: {pr_url}")
        except RuntimeError as e:
            log_error(f"Failed to create PR: {e}")
            sys.exit(1)
    else:
        log_info("Use -c to create the PR automatically")


if __name__ == '__main__':
    main()
