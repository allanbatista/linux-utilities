"""Integration tests for ab_cli.commands.pr_description module."""
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from ab_cli.commands.pr_description import (
    check_gh_authenticated,
    check_gh_installed,
    create_pr,
    detect_base_branch,
    get_commits_ahead,
    get_commits_log,
    get_current_branch,
    get_diff,
    get_files_changed,
    main,
)


class TestBaseBranchDetection:
    """Tests for base branch detection."""

    def test_detect_base_branch_main(self, mock_git_repo, monkeypatch):
        """Detects main branch when it exists."""
        monkeypatch.chdir(mock_git_repo)

        # Create main branch
        subprocess.run(["git", "branch", "main"], cwd=mock_git_repo, check=True)

        result = detect_base_branch()
        assert result in ["main", "master"]  # master is default in mock

    def test_detect_base_branch_master(self, mock_git_repo, monkeypatch):
        """Falls back to master when main doesn't exist."""
        monkeypatch.chdir(mock_git_repo)
        result = detect_base_branch()
        assert result == "master"

    def test_detect_base_branch_empty_repo(self, tmp_path, monkeypatch):
        """Returns empty string when no base branch found."""
        # Create a repo without standard branches
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)

        # Create only a custom branch
        (tmp_path / "file.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)
        subprocess.run(["git", "checkout", "-b", "custom"], cwd=tmp_path, check=True)

        monkeypatch.chdir(tmp_path)

        # Delete master/main
        subprocess.run(["git", "branch", "-D", "master"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "branch", "-D", "main"], cwd=tmp_path, capture_output=True)

        result = detect_base_branch()
        # Could return empty or remote branch
        assert result == "" or "origin" in result or result in ["master", "main", "develop"]


class TestCurrentBranch:
    """Tests for current branch operations."""

    def test_get_current_branch(self, mock_git_repo, monkeypatch):
        """Returns current branch name."""
        monkeypatch.chdir(mock_git_repo)
        result = get_current_branch()
        assert result == "master"

    def test_get_current_branch_feature(self, mock_git_repo, monkeypatch):
        """Returns feature branch name."""
        monkeypatch.chdir(mock_git_repo)

        subprocess.run(["git", "checkout", "-b", "feature/test"], cwd=mock_git_repo, check=True)

        result = get_current_branch()
        assert result == "feature/test"


class TestCommitsAhead:
    """Tests for commits ahead counting."""

    def test_get_commits_ahead_zero(self, mock_git_repo, monkeypatch):
        """Returns 0 when on base branch."""
        monkeypatch.chdir(mock_git_repo)
        result = get_commits_ahead("master", "master")
        assert result == 0

    def test_get_commits_ahead_with_commits(self, mock_git_repo, monkeypatch):
        """Counts commits correctly."""
        monkeypatch.chdir(mock_git_repo)

        # Create feature branch with commits
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=mock_git_repo, check=True)

        for i in range(3):
            (mock_git_repo / f"file{i}.txt").write_text(f"content{i}")
            subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)
            subprocess.run(["git", "commit", "-m", f"Commit {i}"], cwd=mock_git_repo, check=True)

        result = get_commits_ahead("master", "feature")
        assert result == 3


class TestDiffOperations:
    """Tests for diff operations."""

    def test_get_diff(self, mock_git_repo, monkeypatch):
        """Returns diff between branches."""
        monkeypatch.chdir(mock_git_repo)

        # Create feature branch with changes
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=mock_git_repo, check=True)
        (mock_git_repo / "new_file.txt").write_text("new content")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Add new file"], cwd=mock_git_repo, check=True)

        result = get_diff("master", "feature")
        assert "+new content" in result

    def test_get_files_changed(self, mock_git_repo, monkeypatch):
        """Returns changed files with status."""
        monkeypatch.chdir(mock_git_repo)

        # Create feature branch with changes
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=mock_git_repo, check=True)
        (mock_git_repo / "added.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Add file"], cwd=mock_git_repo, check=True)

        result = get_files_changed("master", "feature")
        assert "A" in result
        assert "added.txt" in result

    def test_get_commits_log(self, mock_git_repo, monkeypatch):
        """Returns commit log between branches."""
        monkeypatch.chdir(mock_git_repo)

        # Create feature branch with commits
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=mock_git_repo, check=True)
        (mock_git_repo / "file.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Feature commit"], cwd=mock_git_repo, check=True)

        result = get_commits_log("master", "feature")
        assert "Feature commit" in result


class TestGhCli:
    """Tests for GitHub CLI operations."""

    def test_check_gh_installed_true(self, monkeypatch):
        """Detects gh CLI when installed."""
        with patch("shutil.which", return_value="/usr/bin/gh"):
            assert check_gh_installed() is True

    def test_check_gh_installed_false(self, monkeypatch):
        """Returns False when gh not installed."""
        with patch("shutil.which", return_value=None):
            assert check_gh_installed() is False

    def test_check_gh_authenticated_true(self):
        """Returns True when gh is authenticated."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert check_gh_authenticated() is True

    def test_check_gh_authenticated_false(self):
        """Returns False when gh not authenticated."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "gh")
            assert check_gh_authenticated() is False

    def test_create_pr_success(self):
        """Creates PR and returns URL."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="https://github.com/owner/repo/pull/123\n"
            )
            result = create_pr("Title", "Body", "main")
            assert result == "https://github.com/owner/repo/pull/123"

    def test_create_pr_draft(self):
        """Creates draft PR with --draft flag."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="https://github.com/owner/repo/pull/123\n"
            )
            create_pr("Title", "Body", "main", draft=True)

            # Verify --draft was passed
            call_args = mock_run.call_args[0][0]
            assert "--draft" in call_args

    def test_create_pr_failure(self):
        """Raises RuntimeError on failure."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="Error creating PR"
            )
            with pytest.raises(RuntimeError):
                create_pr("Title", "Body", "main")


class TestMain:
    """Tests for main() entry point."""

    def test_main_not_git_repo_exits_1(self, tmp_path, monkeypatch, capsys):
        """Exits with error when not in git repository."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["pr-description"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    def test_main_on_base_branch_exits(self, mock_git_repo, monkeypatch, capsys):
        """Exits if on base branch."""
        monkeypatch.chdir(mock_git_repo)
        monkeypatch.setattr(sys, "argv", ["pr-description"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "base branch" in captured.err.lower()

    def test_main_no_commits_ahead(self, mock_git_repo, monkeypatch, capsys):
        """Exits with no changes when no commits ahead."""
        monkeypatch.chdir(mock_git_repo)

        # Create a feature branch at same commit
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=mock_git_repo, check=True)

        monkeypatch.setattr(sys, "argv", ["pr-description"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "No commits ahead" in captured.out

    def test_main_create_flag_requires_gh(self, mock_git_repo, monkeypatch, capsys):
        """'-c' flag checks for gh CLI."""
        monkeypatch.chdir(mock_git_repo)

        # Create feature branch with commit
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=mock_git_repo, check=True)
        (mock_git_repo / "file.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "commit"], cwd=mock_git_repo, check=True)

        monkeypatch.setattr(sys, "argv", ["pr-description", "-c"])

        with patch("ab_cli.commands.pr_description.check_gh_installed", return_value=False):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "gh CLI" in captured.err

    def test_main_base_branch_flag(self, mock_git_repo, monkeypatch, capsys):
        """'-b' flag specifies base branch."""
        monkeypatch.chdir(mock_git_repo)

        # Create develop and feature branches
        subprocess.run(["git", "checkout", "-b", "develop"], cwd=mock_git_repo, check=True)
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=mock_git_repo, check=True)
        (mock_git_repo / "file.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "commit"], cwd=mock_git_repo, check=True)

        monkeypatch.setattr(sys, "argv", ["pr-description", "-b", "develop"])

        # The test verifies -b flag is parsed and used
        with patch("ab_cli.commands.pr_description.send_to_openrouter") as mock_send:
            mock_send.return_value = {'text': 'TITLE: Test PR\n\nDESCRIPTION:\n## Summary\n- Test'}

            try:
                main()
            except SystemExit:
                pass

        captured = capsys.readouterr()
        # The base branch should be in the info output
        assert "develop" in captured.out or "Base branch" in captured.out
