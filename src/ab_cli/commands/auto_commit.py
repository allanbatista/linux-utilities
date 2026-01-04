#!/usr/bin/env python3
"""
auto-commit - Automatically generate commit messages using LLM.

Captures uncommitted changes and generates appropriate commit messages.
"""
import argparse
import os
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


def is_protected_branch(branch: str) -> bool:
    """Check if the branch is a protected branch (master/main)."""
    protected = ['master', 'main', 'develop', 'development']
    return branch.lower() in protected


def create_branch(branch_name: str) -> bool:
    """Create and checkout a new branch."""
    try:
        run_git('checkout', '-b', branch_name)
        return True
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to create branch: {e}")
        return False


def suggest_branch_name(diff: str, name_status: str, prompt_cmd: str, lang: str) -> str:
    """Generate a suggested branch name based on changes."""
    config = get_config()

    prompt_text = f"""Analyze these git changes and suggest a branch name.

RULES:
1. Return ONLY the branch name, nothing else
2. Use lowercase kebab-case (words-separated-by-dashes)
3. Max 50 characters total
4. Choose appropriate prefix based on change type:
   - feature/ for new features
   - fix/ for bug fixes
   - chore/ for maintenance tasks
   - refactor/ for code refactoring
   - docs/ for documentation
   - test/ for test-related changes
5. Be concise but descriptive

FILES CHANGED:
{name_status}

DIFF PREVIEW (first 1000 chars):
{diff[:1000]}

Return ONLY the branch name:"""

    estimated_tokens = estimate_tokens(prompt_text)
    selected_model = config.select_model(estimated_tokens)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(prompt_text)
        prompt_file = f.name

    try:
        result = subprocess.run(
            [prompt_cmd, '--model', selected_model, '--lang', lang,
             '--max-completion-tokens', '100', '--only-output', '--prompt', '-'],
            stdin=open(prompt_file, 'r'),
            capture_output=True,
            text=True,
            check=False
        )
        branch_name = result.stdout.strip()
        # Clean up
        import re
        branch_name = branch_name.strip('"\'`')
        branch_name = branch_name.split('\n')[0].strip()
        branch_name = re.sub(r'\s+', '-', branch_name)
        branch_name = re.sub(r'[^a-zA-Z0-9/_-]', '', branch_name)
        if len(branch_name) > 50:
            branch_name = branch_name[:50].rstrip('-')
        return branch_name
    finally:
        os.unlink(prompt_file)


def get_staged_files() -> str:
    """Get list of staged files."""
    result = run_git('diff', '--cached', '--name-only')
    return result.stdout.strip()


def get_unstaged_files() -> str:
    """Get list of unstaged modified files."""
    result = run_git('diff', '--name-only')
    return result.stdout.strip()


def get_untracked_files() -> str:
    """Get list of untracked files."""
    result = run_git('ls-files', '--others', '--exclude-standard')
    return result.stdout.strip()


def get_staged_diff() -> str:
    """Get the staged diff."""
    result = run_git('diff', '--cached')
    return result.stdout


def get_staged_name_status() -> str:
    """Get staged files with status (A, M, D, etc.)."""
    result = run_git('diff', '--cached', '--name-status')
    return result.stdout.strip()


def get_recent_commits(count: int = 5) -> str:
    """Get recent commit messages for style reference."""
    try:
        result = run_git('log', '--oneline', f'-{count}', check=False)
        return result.stdout.strip()
    except Exception:
        return ""


def stage_all_files() -> None:
    """Stage all files."""
    run_git('add', '-A')


def create_commit(message: str) -> None:
    """Create a git commit with the given message."""
    run_git('commit', '-m', message, capture=False)


def get_latest_commit() -> str:
    """Get the latest commit in oneline format."""
    result = run_git('log', '-1', '--oneline')
    return result.stdout.strip()


def find_prompt_command() -> str:
    """Find the ab-prompt command."""
    # Try to find it in the bin directory relative to this module
    import pathlib
    module_dir = pathlib.Path(__file__).parent.parent.parent.parent
    prompt_cmd = module_dir / 'bin' / 'ab-prompt'
    if prompt_cmd.exists():
        return str(prompt_cmd)

    # Fallback to PATH
    import shutil
    if shutil.which('ab-prompt'):
        return 'ab-prompt'

    raise FileNotFoundError("Could not find ab-prompt command")


def generate_commit_message(diff: str, name_status: str, recent_commits: str,
                           lang: str, prompt_cmd: str) -> str:
    """Generate commit message using the prompt utility."""
    config = get_config()

    # Build the prompt
    prompt_text = f"""Analyze the git changes below and generate ONLY the commit message, without additional explanations.

RULES:
1. Respond ONLY with the commit message, nothing else
2. Write in language: {lang}
3. Be concise and descriptive
4. First line: summary up to 100 characters (if possible)
5. If needed, add details after a blank line
6. Use bullet points for content after the first line
7. Do NOT add any footer, attribution, or "Generated by" text

RECENT COMMITS (style reference):
{recent_commits}

FILES CHANGED:
{name_status}

DIFF:
{diff}

Respond ONLY with the commit message:
"""

    # Estimate tokens and select model
    estimated_tokens = estimate_tokens(prompt_text)
    selected_model = config.select_model(estimated_tokens)

    log_info(f"Estimated tokens: ~{estimated_tokens} | Model: {selected_model} | Lang: {lang}")
    print()

    # Write prompt to temp file and use stdin
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
        return result.stdout.strip()
    finally:
        os.unlink(prompt_file)


def main():
    parser = argparse.ArgumentParser(
        description='Automatically generates commit messages using the prompt utility',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  auto-commit                    # Generate message and confirm
  auto-commit -y -a              # Stage all and commit without confirmation
  auto-commit -l pt-br           # Generate message in Portuguese
'''
    )

    parser.add_argument('-y', '--yes', action='store_true',
                        help='Skip commit confirmation')
    parser.add_argument('-a', '--add', action='store_true',
                        help='Automatically stage all files')
    parser.add_argument('-l', '--lang', type=str,
                        default=get_language('auto-commit'),
                        help=f'Output language (default: {get_language("auto-commit")})')

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

    # Change to repo root
    os.chdir(get_repo_root())

    log_info("Checking for uncommitted changes...")

    # Check for changes
    staged = get_staged_files()
    unstaged = get_unstaged_files()
    untracked = get_untracked_files()

    if not staged and not unstaged and not untracked:
        log_warning("No changes to commit")
        sys.exit(0)

    # Show summary
    print()
    log_info("Changes summary:")

    if staged:
        print(f"{GREEN}Staged:{NC}")
        for f in staged.split('\n'):
            print(f"  {f}")

    if unstaged:
        print(f"{YELLOW}Modified:{NC}")
        for f in unstaged.split('\n'):
            print(f"  {f}")

    if untracked:
        print(f"{RED}Untracked:{NC}")
        for f in untracked.split('\n'):
            print(f"  {f}")

    print()

    # Handle staging
    if unstaged or untracked:
        if args.add:
            log_info("Staging all files (--add)...")
            stage_all_files()
        else:
            try:
                reply = input("Stage all files? (y/N) ").strip().lower()
            except EOFError:
                reply = 'n'

            if reply == 'y':
                log_info("Staging files...")
                stage_all_files()
            elif not staged:
                log_warning("No files staged. Aborting.")
                sys.exit(0)

    # Get the diff
    log_info("Generating diff for analysis...")
    diff = get_staged_diff()

    if not diff:
        log_warning("No staged changes to commit")
        sys.exit(0)

    # Get context
    recent_commits = get_recent_commits(5)
    name_status = get_staged_name_status()

    # Check if on protected branch
    current_branch = get_current_branch()
    if is_protected_branch(current_branch):
        log_warning(f"You are on '{current_branch}' branch.")
        print()

        # Suggest a branch name
        log_info("Suggesting branch name...")
        suggested_branch = suggest_branch_name(diff, name_status, prompt_cmd, args.lang)

        if suggested_branch:
            print(f"\n{GREEN}Suggested branch name:{NC} {YELLOW}{suggested_branch}{NC}\n")

            print("Options:")
            print(f"  {GREEN}[1]{NC} Create branch and commit there (Recommended)")
            print(f"  {YELLOW}[2]{NC} Continue on {current_branch} anyway")
            print(f"  {RED}[3]{NC} Cancel")
            print()

            try:
                choice = input("Choice [1/2/3]: ").strip()
            except EOFError:
                choice = '3'

            if choice == '1':
                if create_branch(suggested_branch):
                    log_success(f"Created and switched to '{suggested_branch}'")
                else:
                    log_error("Failed to create branch")
                    sys.exit(1)
            elif choice == '2':
                log_warning(f"Continuing on {current_branch}...")
            else:
                log_warning("Cancelled")
                sys.exit(0)
        else:
            log_warning("Could not suggest branch name")
            print()
            print("Options:")
            print(f"  {GREEN}[1]{NC} Enter branch name manually")
            print(f"  {YELLOW}[2]{NC} Continue on {current_branch} anyway")
            print(f"  {RED}[3]{NC} Cancel")
            print()

            try:
                choice = input("Choice [1/2/3]: ").strip()
            except EOFError:
                choice = '3'

            if choice == '1':
                try:
                    manual_branch = input("Enter branch name: ").strip()
                except EOFError:
                    manual_branch = ''

                if manual_branch:
                    if create_branch(manual_branch):
                        log_success(f"Created and switched to '{manual_branch}'")
                    else:
                        log_error("Failed to create branch")
                        sys.exit(1)
                else:
                    log_warning("No branch name provided. Cancelled.")
                    sys.exit(0)
            elif choice == '2':
                log_warning(f"Continuing on {current_branch}...")
            else:
                log_warning("Cancelled")
                sys.exit(0)

    # Generate commit message
    log_info("Generating commit message...")

    try:
        commit_msg = generate_commit_message(
            diff, name_status, recent_commits, args.lang, prompt_cmd
        )
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to generate commit message: {e}")
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        sys.exit(1)

    if not commit_msg:
        log_error("Failed to generate commit message")
        sys.exit(1)

    # Show generated message
    print(f"{GREEN}Generated commit message:{NC}")
    print("-" * 40)
    print(commit_msg)
    print("-" * 40)
    print()

    # Confirm commit
    if not args.yes:
        try:
            reply = input("Confirm commit with this message? (Y/n) ").strip().lower()
        except EOFError:
            reply = 'n'

        if reply == 'n':
            log_warning("Commit cancelled")
            sys.exit(0)

    # Create commit
    log_info("Committing...")
    create_commit(commit_msg)

    print()
    log_success("Commit successful!")
    log_info(f"Latest commit: {get_latest_commit()}")


if __name__ == '__main__':
    main()
