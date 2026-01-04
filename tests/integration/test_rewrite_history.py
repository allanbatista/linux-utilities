"""Integration tests for ab_cli.commands.rewrite_history module."""
import subprocess
import sys
from unittest.mock import patch

import pytest

from ab_cli.commands.rewrite_history import (
    check_commits_pushed,
    count_words,
    create_backup_branch,
    get_commit_diff,
    get_commit_files,
    get_commit_message,
    get_commit_subject,
    get_short_hash,
    has_remotes,
    has_uncommitted_changes,
    is_merge_commit,
    list_commits,
    main,
)


class TestMergeCommitDetection:
    """Tests for merge commit detection."""

    def test_is_merge_commit_false(self, mock_git_repo, monkeypatch):
        """Non-merge commit returns False."""
        monkeypatch.chdir(mock_git_repo)

        # Get initial commit hash
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=mock_git_repo,
            capture_output=True,
            text=True,
            check=True
        )
        commit_hash = result.stdout.strip()

        assert is_merge_commit(commit_hash) is False

    def test_is_merge_commit_true(self, mock_git_repo, monkeypatch):
        """Merge commit returns True."""
        monkeypatch.chdir(mock_git_repo)

        # Create a branch and merge it
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=mock_git_repo, check=True)
        (mock_git_repo / "feature.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Feature commit"], cwd=mock_git_repo, check=True)

        subprocess.run(["git", "checkout", "master"], cwd=mock_git_repo, check=True)
        (mock_git_repo / "master.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Master commit"], cwd=mock_git_repo, check=True)

        subprocess.run(
            ["git", "merge", "--no-ff", "feature", "-m", "Merge feature"],
            cwd=mock_git_repo,
            check=True
        )

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=mock_git_repo,
            capture_output=True,
            text=True,
            check=True
        )
        merge_hash = result.stdout.strip()

        assert is_merge_commit(merge_hash) is True


class TestUncommittedChanges:
    """Tests for uncommitted changes detection."""

    def test_has_uncommitted_changes_false(self, mock_git_repo, monkeypatch):
        """Returns False when working directory is clean."""
        monkeypatch.chdir(mock_git_repo)
        assert has_uncommitted_changes() is False

    def test_has_uncommitted_changes_true_unstaged(self, mock_git_repo, monkeypatch):
        """Returns True with unstaged changes."""
        monkeypatch.chdir(mock_git_repo)

        # Modify a file
        (mock_git_repo / "README.md").write_text("Modified")

        assert has_uncommitted_changes() is True

    def test_has_uncommitted_changes_true_staged(self, mock_git_repo, monkeypatch):
        """Returns True with staged changes."""
        monkeypatch.chdir(mock_git_repo)

        # Stage a new file
        (mock_git_repo / "new.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)

        assert has_uncommitted_changes() is True


class TestListCommits:
    """Tests for commit listing."""

    def test_list_commits_range(self, mock_git_repo, monkeypatch):
        """Lists commits in range."""
        monkeypatch.chdir(mock_git_repo)

        # Create more commits
        for i in range(3):
            (mock_git_repo / f"file{i}.txt").write_text(f"content{i}")
            subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)
            subprocess.run(["git", "commit", "-m", f"Commit {i}"], cwd=mock_git_repo, check=True)

        commits = list_commits("HEAD~3..HEAD")
        assert len(commits) == 3

    def test_list_commits_all(self, mock_git_repo, monkeypatch):
        """Lists all commits with --root."""
        monkeypatch.chdir(mock_git_repo)

        # Create more commits
        (mock_git_repo / "file.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Second commit"], cwd=mock_git_repo, check=True)

        commits = list_commits("--root")
        assert len(commits) >= 2  # Initial + Second


class TestBackupBranch:
    """Tests for backup branch creation."""

    def test_create_backup_branch(self, mock_git_repo, monkeypatch):
        """Creates backup branch with timestamp."""
        monkeypatch.chdir(mock_git_repo)

        branch_name = create_backup_branch()

        assert branch_name.startswith("backup/pre-rewrite-")

        # Verify branch exists
        result = subprocess.run(
            ["git", "branch", "--list", branch_name],
            cwd=mock_git_repo,
            capture_output=True,
            text=True,
            check=True
        )
        assert branch_name in result.stdout

    def test_create_backup_branch_custom_name(self, mock_git_repo, monkeypatch):
        """Creates backup branch with custom name."""
        monkeypatch.chdir(mock_git_repo)

        branch_name = create_backup_branch("custom/backup-name")

        assert branch_name == "custom/backup-name"


class TestCommitsPushed:
    """Tests for pushed commits detection."""

    def test_check_commits_pushed_no_remotes(self, mock_git_repo, monkeypatch):
        """Returns False when no remotes configured."""
        monkeypatch.chdir(mock_git_repo)

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=mock_git_repo,
            capture_output=True,
            text=True,
            check=True
        )
        commit_hash = result.stdout.strip()

        assert check_commits_pushed(commit_hash) is False

    def test_has_remotes_false(self, mock_git_repo, monkeypatch):
        """Returns False when no remotes."""
        monkeypatch.chdir(mock_git_repo)
        assert has_remotes() is False


class TestCommitOperations:
    """Tests for commit information operations."""

    def test_get_commit_message(self, mock_git_repo, monkeypatch):
        """Returns full commit message."""
        monkeypatch.chdir(mock_git_repo)

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=mock_git_repo,
            capture_output=True,
            text=True,
            check=True
        )
        commit_hash = result.stdout.strip()

        message = get_commit_message(commit_hash)
        assert "Initial commit" in message

    def test_get_commit_subject(self, mock_git_repo, monkeypatch):
        """Returns commit subject line."""
        monkeypatch.chdir(mock_git_repo)

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=mock_git_repo,
            capture_output=True,
            text=True,
            check=True
        )
        commit_hash = result.stdout.strip()

        subject = get_commit_subject(commit_hash)
        assert "Initial commit" in subject

    def test_get_short_hash(self, mock_git_repo, monkeypatch):
        """Returns short hash."""
        monkeypatch.chdir(mock_git_repo)

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=mock_git_repo,
            capture_output=True,
            text=True,
            check=True
        )
        commit_hash = result.stdout.strip()

        short_hash = get_short_hash(commit_hash)
        assert len(short_hash) == 7  # Default short hash length

    def test_get_commit_diff(self, mock_git_repo, monkeypatch):
        """Returns commit diff."""
        monkeypatch.chdir(mock_git_repo)

        # Create a new commit with changes
        (mock_git_repo / "test.txt").write_text("test content\n")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Add test file"], cwd=mock_git_repo, check=True)

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=mock_git_repo,
            capture_output=True,
            text=True,
            check=True
        )
        commit_hash = result.stdout.strip()

        diff = get_commit_diff(commit_hash)
        assert "+test content" in diff

    def test_get_commit_files(self, mock_git_repo, monkeypatch):
        """Returns files changed in commit."""
        monkeypatch.chdir(mock_git_repo)

        # Create a new commit with a file change (initial commits may not show files)
        (mock_git_repo / "testfile.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Add testfile"], cwd=mock_git_repo, check=True)

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=mock_git_repo,
            capture_output=True,
            text=True,
            check=True
        )
        commit_hash = result.stdout.strip()

        files = get_commit_files(commit_hash)
        assert "testfile.txt" in files


class TestCountWords:
    """Tests for word counting utility."""

    def test_count_words_simple(self):
        """Counts words correctly."""
        assert count_words("one two three") == 3

    def test_count_words_empty(self):
        """Returns 0 for empty string."""
        assert count_words("") == 0

    def test_count_words_multiline(self):
        """Counts words across lines."""
        assert count_words("line one\nline two") == 4


class TestMain:
    """Tests for main() entry point."""

    def test_main_not_git_repo_exits_1(self, tmp_path, monkeypatch, capsys):
        """Exits with error when not in git repository."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["rewrite-history", "--dry-run"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    def test_main_uncommitted_changes_exits_1(self, mock_git_repo, monkeypatch, capsys):
        """Exits with error when uncommitted changes exist."""
        monkeypatch.chdir(mock_git_repo)

        # Create more commits first so HEAD~1..HEAD works
        (mock_git_repo / "file1.txt").write_text("content1")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Second commit"], cwd=mock_git_repo, check=True)

        # Now create uncommitted changes by modifying a tracked file
        (mock_git_repo / "file1.txt").write_text("modified content")

        # Pass a revision range to skip interactive menu
        monkeypatch.setattr(sys, "argv", ["rewrite-history", "--dry-run", "HEAD~1..HEAD"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "uncommitted changes" in captured.err.lower()

    def test_main_dry_run(self, mock_git_repo, monkeypatch, capsys):
        """'--dry-run' makes no changes."""
        monkeypatch.chdir(mock_git_repo)

        # Create commits to analyze
        for i in range(2):
            (mock_git_repo / f"file{i}.txt").write_text(f"content{i}")
            subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)
            subprocess.run(["git", "commit", "-m", "fix"], cwd=mock_git_repo, check=True)

        # Get initial HEAD
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=mock_git_repo,
            capture_output=True,
            text=True,
            check=True
        )
        initial_head = result.stdout.strip()

        monkeypatch.setattr(sys, "argv", ["rewrite-history", "--dry-run", "--force-all", "HEAD~2..HEAD"])

        with patch("ab_cli.commands.rewrite_history.generate_new_message", return_value="New message"):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 0

        # Verify HEAD unchanged
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=mock_git_repo,
            capture_output=True,
            text=True,
            check=True
        )
        assert result.stdout.strip() == initial_head

        captured = capsys.readouterr()
        assert "Dry-run mode" in captured.out

    def test_main_skip_merges_flag(self, mock_git_repo, monkeypatch, capsys):
        """'--skip-merges' skips merge commits."""
        monkeypatch.chdir(mock_git_repo)

        # Create additional commit on master first
        (mock_git_repo / "base.txt").write_text("base content")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Base commit"], cwd=mock_git_repo, check=True)

        # Create a merge commit
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=mock_git_repo, check=True)
        (mock_git_repo / "feature.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Feature"], cwd=mock_git_repo, check=True)

        subprocess.run(["git", "checkout", "master"], cwd=mock_git_repo, check=True)
        (mock_git_repo / "master.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Master"], cwd=mock_git_repo, check=True)

        subprocess.run(
            ["git", "merge", "--no-ff", "feature", "-m", "Merge"],
            cwd=mock_git_repo,
            check=True
        )

        # Use HEAD~3..HEAD to cover the commits including merge (now we have enough)
        monkeypatch.setattr(sys, "argv", [
            "rewrite-history", "--dry-run", "--force-all", "--skip-merges", "HEAD~3..HEAD"
        ])

        with patch("ab_cli.commands.rewrite_history.generate_new_message", return_value="New"):
            with pytest.raises(SystemExit):
                main()

        captured = capsys.readouterr()
        assert "Skipping merge commit" in captured.out
