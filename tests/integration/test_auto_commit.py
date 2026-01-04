"""Integration tests for ab_cli.commands.auto_commit module."""
import subprocess
import sys
from unittest.mock import patch

import pytest

from ab_cli.commands.auto_commit import (
    create_commit,
    get_latest_commit,
    get_recent_commits,
    get_repo_root,
    get_staged_diff,
    get_staged_files,
    get_staged_name_status,
    get_unstaged_files,
    get_untracked_files,
    is_git_repo,
    main,
    stage_all_files,
)


class TestGitRepoDetection:
    """Tests for git repository detection."""

    def test_is_git_repo_true(self, mock_git_repo, monkeypatch):
        """Detects git repository correctly."""
        monkeypatch.chdir(mock_git_repo)
        assert is_git_repo() is True

    def test_is_git_repo_false(self, tmp_path, monkeypatch):
        """Returns False outside git repository."""
        monkeypatch.chdir(tmp_path)
        assert is_git_repo() is False


class TestStagedFiles:
    """Tests for staged file operations."""

    def test_get_staged_files_empty(self, mock_git_repo, monkeypatch):
        """Returns empty string when no files staged."""
        monkeypatch.chdir(mock_git_repo)
        result = get_staged_files()
        assert result == ""

    def test_get_staged_files_with_files(self, mock_git_repo, monkeypatch):
        """Returns staged file list."""
        monkeypatch.chdir(mock_git_repo)

        # Create and stage a file
        test_file = mock_git_repo / "test.txt"
        test_file.write_text("test content")
        subprocess.run(["git", "add", "test.txt"], cwd=mock_git_repo, check=True)

        result = get_staged_files()
        assert "test.txt" in result

    def test_get_staged_diff(self, mock_git_repo, monkeypatch):
        """Returns diff content for staged files."""
        monkeypatch.chdir(mock_git_repo)

        # Create and stage a file
        test_file = mock_git_repo / "test.txt"
        test_file.write_text("test content\n")
        subprocess.run(["git", "add", "test.txt"], cwd=mock_git_repo, check=True)

        result = get_staged_diff()
        assert "+test content" in result

    def test_get_staged_name_status(self, mock_git_repo, monkeypatch):
        """Returns staged files with status."""
        monkeypatch.chdir(mock_git_repo)

        # Create and stage a file
        test_file = mock_git_repo / "new_file.txt"
        test_file.write_text("content")
        subprocess.run(["git", "add", "new_file.txt"], cwd=mock_git_repo, check=True)

        result = get_staged_name_status()
        assert "A" in result  # Added file
        assert "new_file.txt" in result


class TestUnstagedFiles:
    """Tests for unstaged file operations."""

    def test_get_unstaged_files_empty(self, mock_git_repo, monkeypatch):
        """Returns empty string when no unstaged changes."""
        monkeypatch.chdir(mock_git_repo)
        result = get_unstaged_files()
        assert result == ""

    def test_get_unstaged_files_with_changes(self, mock_git_repo, monkeypatch):
        """Returns modified files not staged."""
        monkeypatch.chdir(mock_git_repo)

        # Modify existing file
        readme = mock_git_repo / "README.md"
        readme.write_text("Modified content\n")

        result = get_unstaged_files()
        assert "README.md" in result


class TestUntrackedFiles:
    """Tests for untracked file operations."""

    def test_get_untracked_files_empty(self, mock_git_repo, monkeypatch):
        """Returns empty string when no untracked files."""
        monkeypatch.chdir(mock_git_repo)
        result = get_untracked_files()
        assert result == ""

    def test_get_untracked_files_with_files(self, mock_git_repo, monkeypatch):
        """Returns untracked file list."""
        monkeypatch.chdir(mock_git_repo)

        # Create untracked file
        new_file = mock_git_repo / "untracked.txt"
        new_file.write_text("new content")

        result = get_untracked_files()
        assert "untracked.txt" in result


class TestStageAndCommit:
    """Tests for staging and committing."""

    def test_stage_all_files(self, mock_git_repo, monkeypatch):
        """Stages all files with git add -A."""
        monkeypatch.chdir(mock_git_repo)

        # Create untracked files
        (mock_git_repo / "file1.txt").write_text("content1")
        (mock_git_repo / "file2.txt").write_text("content2")

        stage_all_files()

        # Check files are staged
        staged = get_staged_files()
        assert "file1.txt" in staged
        assert "file2.txt" in staged

    def test_create_commit(self, mock_git_repo, monkeypatch):
        """Creates git commit with message."""
        monkeypatch.chdir(mock_git_repo)

        # Create and stage a file
        (mock_git_repo / "test.txt").write_text("content")
        stage_all_files()

        create_commit("Test commit message")

        # Verify commit
        latest = get_latest_commit()
        assert "Test commit message" in latest

    def test_get_latest_commit(self, mock_git_repo, monkeypatch):
        """Returns latest commit in oneline format."""
        monkeypatch.chdir(mock_git_repo)
        result = get_latest_commit()
        assert "Initial commit" in result

    def test_get_recent_commits(self, mock_git_repo, monkeypatch):
        """Returns recent commit messages."""
        monkeypatch.chdir(mock_git_repo)

        # Create more commits
        for i in range(3):
            (mock_git_repo / f"file{i}.txt").write_text(f"content{i}")
            subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)
            subprocess.run(["git", "commit", "-m", f"Commit {i}"], cwd=mock_git_repo, check=True)

        result = get_recent_commits(5)
        assert "Commit 0" in result
        assert "Commit 1" in result
        assert "Commit 2" in result


class TestRepoRoot:
    """Tests for repository root detection."""

    def test_get_repo_root(self, mock_git_repo, monkeypatch):
        """Returns repository root directory."""
        monkeypatch.chdir(mock_git_repo)
        result = get_repo_root()
        assert result == str(mock_git_repo)

    def test_get_repo_root_from_subdir(self, mock_git_repo, monkeypatch):
        """Returns root from subdirectory."""
        subdir = mock_git_repo / "subdir"
        subdir.mkdir()
        monkeypatch.chdir(subdir)

        result = get_repo_root()
        assert result == str(mock_git_repo)


class TestMain:
    """Tests for main() entry point."""

    def test_main_not_git_repo_exits_1(self, tmp_path, monkeypatch, capsys):
        """Exits with error when not in git repository."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["auto-commit"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Not inside a git repository" in captured.err

    def test_main_no_changes_exits_0(self, mock_git_repo, monkeypatch, capsys):
        """Exits cleanly when no changes to commit."""
        monkeypatch.chdir(mock_git_repo)
        monkeypatch.setattr(sys, "argv", ["auto-commit"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "No changes to commit" in captured.out

    def test_main_prompt_not_found_exits_1(self, mock_git_repo, monkeypatch, capsys):
        """Exits with error if API call fails."""
        monkeypatch.chdir(mock_git_repo)

        # Create changes
        (mock_git_repo / "test.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)

        monkeypatch.setattr(sys, "argv", ["auto-commit", "-y"])

        # Mock call_llm_with_model_info to return None (API failure)
        # Also mock is_protected_branch to avoid input() prompt
        with patch("ab_cli.commands.auto_commit.call_llm_with_model_info") as mock_call:
            with patch("ab_cli.commands.auto_commit.is_protected_branch", return_value=False):
                mock_call.return_value = (None, "test-model", 100)

                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1

    def test_main_auto_add_flag(self, mock_git_repo, monkeypatch, mock_input):
        """'-a' flag stages all files."""
        monkeypatch.chdir(mock_git_repo)

        # Create unstaged file
        (mock_git_repo / "unstaged.txt").write_text("content")

        # Verify file is not staged initially
        assert "unstaged.txt" not in get_staged_files()

        monkeypatch.setattr(sys, "argv", ["auto-commit", "-a", "-y"])

        # Mock call_llm_with_model_info to fail after staging happens
        call_count = [0]
        original_stage = stage_all_files

        def mock_stage():
            original_stage()
            call_count[0] += 1

        # Also mock is_protected_branch to avoid input() prompt
        with patch("ab_cli.commands.auto_commit.stage_all_files", side_effect=mock_stage):
            with patch("ab_cli.commands.auto_commit.call_llm_with_model_info") as mock_call:
                with patch("ab_cli.commands.auto_commit.is_protected_branch", return_value=False):
                    mock_call.return_value = (None, "test-model", 100)  # Fail after staging

                    with pytest.raises(SystemExit):
                        main()

        # Verify staging was called (the flag was honored)
        assert call_count[0] >= 1

    def test_main_user_cancels(self, mock_git_repo, monkeypatch, capsys):
        """Handles user cancellation during staging prompt."""
        monkeypatch.chdir(mock_git_repo)

        # Create unstaged file
        (mock_git_repo / "test.txt").write_text("content")

        monkeypatch.setattr(sys, "argv", ["auto-commit"])

        with patch("builtins.input", return_value="n"):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 0

    def test_main_lang_flag(self, mock_git_repo, monkeypatch, capsys):
        """'-l' flag sets language."""
        monkeypatch.chdir(mock_git_repo)

        # Create and stage changes
        (mock_git_repo / "test.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=mock_git_repo, check=True)

        monkeypatch.setattr(sys, "argv", ["auto-commit", "-l", "pt-br", "-y"])

        # Also mock is_protected_branch to avoid input() prompt
        with patch("ab_cli.commands.auto_commit.call_llm_with_model_info") as mock_call:
            with patch("ab_cli.commands.auto_commit.is_protected_branch", return_value=False):
                mock_call.return_value = (None, "test-model", 100)  # Fail to abort

                with pytest.raises(SystemExit):
                    main()

        captured = capsys.readouterr()
        # Language should be in info output
        assert "pt-br" in captured.out or captured.err
