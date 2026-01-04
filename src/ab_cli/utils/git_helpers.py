"""Git helper utilities for ab-cli.

Provides common git operations used across multiple commands.
"""
import subprocess
from typing import List, Optional

from ab_cli.utils.exceptions import GitError


def run_git(*args, capture: bool = True, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command.

    Args:
        *args: Git command arguments
        capture: Whether to capture output (default True)
        check: Whether to raise on non-zero exit (default True)

    Returns:
        CompletedProcess instance with stdout/stderr
    """
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


def require_git_repo() -> None:
    """Require the current directory to be inside a git repository.

    Raises:
        GitError: If not inside a git repository.
    """
    if not is_git_repo():
        raise GitError("Not inside a git repository")


def get_repo_root() -> str:
    """Get the root directory of the git repository."""
    result = run_git('rev-parse', '--show-toplevel')
    return result.stdout.strip()


def get_current_branch() -> str:
    """Get the current branch name."""
    result = run_git('rev-parse', '--abbrev-ref', 'HEAD')
    return result.stdout.strip()


def is_protected_branch(branch: str) -> bool:
    """Check if the branch is a protected branch (master/main/develop)."""
    protected = ['master', 'main', 'develop', 'development']
    return branch.lower() in protected


def branch_exists(branch_name: str) -> bool:
    """Check if a branch already exists."""
    try:
        run_git('rev-parse', '--verify', branch_name, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def create_branch(branch_name: str) -> bool:
    """Create and checkout a new branch.

    Returns True if successful, False otherwise.
    """
    try:
        run_git('checkout', '-b', branch_name)
        return True
    except subprocess.CalledProcessError:
        return False


# Staging and diff operations

def get_staged_files() -> str:
    """Get list of staged files (newline separated)."""
    result = run_git('diff', '--cached', '--name-only')
    return result.stdout.strip()


def get_unstaged_files() -> str:
    """Get list of unstaged modified files (newline separated)."""
    result = run_git('diff', '--name-only')
    return result.stdout.strip()


def get_untracked_files() -> str:
    """Get list of untracked files (newline separated)."""
    result = run_git('ls-files', '--others', '--exclude-standard')
    return result.stdout.strip()


def get_staged_diff() -> str:
    """Get the staged diff content."""
    result = run_git('diff', '--cached')
    return result.stdout


def get_staged_name_status() -> str:
    """Get staged files with status (A, M, D, etc.)."""
    result = run_git('diff', '--cached', '--name-status')
    return result.stdout.strip()


def stage_all_files() -> None:
    """Stage all files (git add -A)."""
    run_git('add', '-A')


def has_uncommitted_changes() -> bool:
    """Check if there are uncommitted changes (staged or unstaged)."""
    try:
        run_git('diff', '--quiet')
        run_git('diff', '--cached', '--quiet')
        return False
    except subprocess.CalledProcessError:
        return True


# Commit operations

def create_commit(message: str) -> None:
    """Create a git commit with the given message."""
    run_git('commit', '-m', message, capture=False)


def get_latest_commit() -> str:
    """Get the latest commit in oneline format."""
    result = run_git('log', '-1', '--oneline')
    return result.stdout.strip()


def get_recent_commits(count: int = 5) -> str:
    """Get recent commit messages for style reference."""
    try:
        result = run_git('log', '--oneline', f'-{count}', check=False)
        return result.stdout.strip()
    except Exception:
        return ""


def get_commit_message(commit_hash: str) -> str:
    """Get full commit message."""
    result = run_git('log', '-1', '--format=%B', commit_hash)
    return result.stdout.strip()


def get_commit_subject(commit_hash: str) -> str:
    """Get commit subject line only."""
    result = run_git('log', '-1', '--format=%s', commit_hash)
    return result.stdout.strip()


def get_short_hash(commit_hash: str) -> str:
    """Get short hash for a commit."""
    result = run_git('log', '-1', '--format=%h', commit_hash)
    return result.stdout.strip()


def is_merge_commit(commit_hash: str) -> bool:
    """Check if commit is a merge commit (has multiple parents)."""
    result = run_git('rev-list', '--parents', '-n', '1', commit_hash)
    parts = result.stdout.strip().split()
    return len(parts) > 2  # More than 1 parent


def get_commit_diff(commit_hash: str) -> str:
    """Get diff for a specific commit."""
    result = run_git('rev-list', '--parents', '-n', '1', commit_hash)
    parts = result.stdout.strip().split()
    parent_count = len(parts) - 1

    if parent_count == 0:
        # First commit - use diff-tree with --root
        result = run_git('diff-tree', '--root', '-p', commit_hash, check=False)
    else:
        result = run_git('show', '--format=', '-p', commit_hash, check=False)

    return result.stdout


def get_commit_files(commit_hash: str) -> str:
    """Get files changed in a commit with status."""
    result = run_git('diff-tree', '--no-commit-id', '--name-status', '-r',
                     commit_hash, check=False)
    return result.stdout.strip()


def list_commits(revision_range: str) -> List[str]:
    """List commits in range (oldest first).

    Args:
        revision_range: Git revision range (e.g., 'HEAD~5..HEAD' or '--root')

    Returns:
        List of commit hashes
    """
    if revision_range == '--root':
        result = run_git('rev-list', '--reverse', 'HEAD')
    else:
        result = run_git('rev-list', '--reverse', revision_range)
    commits = result.stdout.strip().split('\n')
    return [c for c in commits if c]


# Remote operations

def has_remotes() -> bool:
    """Check if repository has any remotes configured."""
    result = run_git('remote', check=False)
    return bool(result.stdout.strip())


def check_commits_pushed(first_commit: str) -> bool:
    """Check if commits have been pushed to remote.

    Returns True if commits are pushed to any remote.
    """
    if not has_remotes():
        return False

    try:
        # Get all remotes
        result = run_git('remote')
        remotes = result.stdout.strip().split('\n')

        for remote in remotes:
            if not remote:
                continue
            # Check if commit is reachable from any remote branch
            result = run_git('branch', '-r', '--contains', first_commit, check=False)
            if result.stdout.strip():
                return True
    except subprocess.CalledProcessError:
        pass

    return False


# Tag operations

def get_latest_tag() -> Optional[str]:
    """Get the latest tag, or None if no tags exist."""
    try:
        result = run_git('describe', '--tags', '--abbrev=0', check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def get_all_tags() -> List[str]:
    """Get all tags sorted by version."""
    result = run_git('tag', '--sort=-version:refname', check=False)
    tags = result.stdout.strip().split('\n')
    return [t for t in tags if t]


# Merge conflict operations

def get_conflicted_files() -> List[str]:
    """Get list of files with merge conflicts."""
    try:
        result = run_git('diff', '--name-only', '--diff-filter=U')
        if result.stdout.strip():
            return result.stdout.strip().split('\n')
    except subprocess.CalledProcessError:
        pass
    return []


# Base branch detection

def detect_base_branch() -> str:
    """Detect the base branch (main, master, or develop)."""
    for branch in ['main', 'master', 'develop']:
        if branch_exists(branch) or branch_exists(f'origin/{branch}'):
            return branch
    return 'main'  # Default fallback


def get_commits_ahead(base_branch: str) -> int:
    """Get number of commits ahead of base branch."""
    try:
        # Try with local branch first
        try:
            result = run_git('rev-list', '--count', f'{base_branch}..HEAD')
            return int(result.stdout.strip())
        except subprocess.CalledProcessError:
            # Try with origin prefix
            result = run_git('rev-list', '--count', f'origin/{base_branch}..HEAD')
            return int(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0


def get_diff_against_base(base_branch: str) -> str:
    """Get diff against base branch."""
    try:
        result = run_git('diff', f'{base_branch}...HEAD', check=False)
        return result.stdout
    except subprocess.CalledProcessError:
        try:
            result = run_git('diff', f'origin/{base_branch}...HEAD', check=False)
            return result.stdout
        except subprocess.CalledProcessError:
            return ""


def get_commits_log(base_branch: str) -> str:
    """Get commits log from base branch to HEAD."""
    try:
        result = run_git('log', '--oneline', f'{base_branch}..HEAD', check=False)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        try:
            result = run_git('log', '--oneline', f'origin/{base_branch}..HEAD',
                             check=False)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return ""


def get_files_changed(base_branch: str) -> str:
    """Get files changed from base branch."""
    try:
        result = run_git('diff', '--name-status', f'{base_branch}...HEAD', check=False)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        try:
            result = run_git('diff', '--name-status', f'origin/{base_branch}...HEAD',
                             check=False)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return ""
