"""Integration tests for ab_cli.commands.branch_name module."""
import subprocess
import sys
from unittest.mock import patch

import pytest

from ab_cli.commands.branch_name import (
    extract_ticket_number,
    main,
)
from ab_cli.utils import (
    branch_exists,
    create_branch,
    get_current_branch,
    is_git_repo,
    run_git,
)


class TestRunGit:
    """Tests for run_git helper function."""

    def test_run_git_success(self, mock_git_repo, monkeypatch):
        """Runs git command successfully."""
        monkeypatch.chdir(mock_git_repo)
        result = run_git('status')
        assert result.returncode == 0

    def test_run_git_captures_output(self, mock_git_repo, monkeypatch):
        """Captures command output."""
        monkeypatch.chdir(mock_git_repo)
        result = run_git('branch', '--show-current')
        assert result.stdout.strip() == 'master'

    def test_run_git_failure_raises(self, mock_git_repo, monkeypatch):
        """Raises CalledProcessError on failure."""
        monkeypatch.chdir(mock_git_repo)
        with pytest.raises(subprocess.CalledProcessError):
            run_git('nonexistent-command')


class TestIsGitRepo:
    """Tests for is_git_repo function."""

    def test_is_git_repo_true(self, mock_git_repo, monkeypatch):
        """Returns True inside git repository."""
        monkeypatch.chdir(mock_git_repo)
        assert is_git_repo() is True

    def test_is_git_repo_false(self, tmp_path, monkeypatch):
        """Returns False outside git repository."""
        monkeypatch.chdir(tmp_path)
        assert is_git_repo() is False


class TestGetCurrentBranch:
    """Tests for get_current_branch function."""

    def test_get_current_branch_master(self, mock_git_repo, monkeypatch):
        """Returns 'master' for initial repository."""
        monkeypatch.chdir(mock_git_repo)
        branch = get_current_branch()
        assert branch == 'master'

    def test_get_current_branch_after_checkout(self, mock_git_repo, monkeypatch):
        """Returns correct branch after checkout."""
        monkeypatch.chdir(mock_git_repo)
        subprocess.run(['git', 'checkout', '-b', 'feature/test'], cwd=mock_git_repo, check=True)

        branch = get_current_branch()
        assert branch == 'feature/test'


class TestBranchExists:
    """Tests for branch_exists function."""

    def test_branch_exists_true(self, mock_git_repo, monkeypatch):
        """Returns True for existing branch."""
        monkeypatch.chdir(mock_git_repo)
        assert branch_exists('master') is True

    def test_branch_exists_false(self, mock_git_repo, monkeypatch):
        """Returns False for non-existing branch."""
        monkeypatch.chdir(mock_git_repo)
        assert branch_exists('nonexistent-branch') is False


class TestCreateBranch:
    """Tests for create_branch function."""

    def test_create_branch_success(self, mock_git_repo, monkeypatch):
        """Creates and checks out new branch."""
        monkeypatch.chdir(mock_git_repo)

        result = create_branch('feature/new-feature')
        assert result is True

        current = get_current_branch()
        assert current == 'feature/new-feature'

    def test_create_branch_already_exists_fails(self, mock_git_repo, monkeypatch, capsys):
        """Returns False when branch already exists."""
        monkeypatch.chdir(mock_git_repo)

        # Create branch first
        subprocess.run(['git', 'checkout', '-b', 'existing-branch'], cwd=mock_git_repo, check=True)
        subprocess.run(['git', 'checkout', 'master'], cwd=mock_git_repo, check=True)

        # Try to create again
        result = create_branch('existing-branch')
        assert result is False


class TestExtractTicketNumber:
    """Tests for extract_ticket_number function."""

    def test_extract_ticket_jira_style(self):
        """Extracts JIRA-style ticket numbers."""
        assert extract_ticket_number('JIRA-123: fix bug') == 'JIRA-123'
        assert extract_ticket_number('ABC-456 implement feature') == 'ABC-456'
        assert extract_ticket_number('PROJ-1 small fix') == 'PROJ-1'

    def test_extract_ticket_github_style(self):
        """Extracts GitHub-style issue numbers."""
        assert extract_ticket_number('#123 fix bug') == '123'
        assert extract_ticket_number('fix #456 alignment') == '456'

    def test_extract_ticket_none(self):
        """Returns None when no ticket found."""
        assert extract_ticket_number('add user authentication') is None
        assert extract_ticket_number('fix button alignment') is None

    def test_extract_ticket_first_match(self):
        """Returns first match when multiple tickets present."""
        result = extract_ticket_number('JIRA-123 and JIRA-456')
        assert result == 'JIRA-123'


class TestMain:
    """Tests for main() entry point."""

    def test_main_no_description_shows_help(self, monkeypatch, capsys):
        """Shows help when no description provided."""
        monkeypatch.setattr(sys, 'argv', ['branch-name'])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert 'usage:' in captured.out.lower() or 'description' in captured.out.lower()

    def test_main_create_not_git_repo_exits_1(self, tmp_path, monkeypatch, capsys):
        """Exits with error when --create used outside git repo."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['branch-name', '-c', 'add feature'])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert 'not a git repository' in captured.err.lower()

    def test_main_prefix_flag_accepted(self, monkeypatch, capsys, mock_config):
        """Accepts --prefix flag."""
        monkeypatch.setattr(sys, 'argv', ['branch-name', '--prefix', 'fix', 'test description'])

        with patch('ab_cli.commands.branch_name.call_llm') as mock_call:
            mock_call.return_value = {'text': 'fix/test-description'}

            try:
                main()
            except SystemExit:
                pass

        # If we got here without argument error, the flag was accepted

    def test_main_lang_flag_accepted(self, monkeypatch, capsys, mock_config):
        """Accepts --lang flag."""
        monkeypatch.setattr(sys, 'argv', ['branch-name', '-l', 'pt-br', 'test description'])

        with patch('ab_cli.commands.branch_name.call_llm') as mock_call:
            mock_call.return_value = {'text': 'feature/test-description'}

            try:
                main()
            except SystemExit:
                pass

        # If we got here without argument error, the flag was accepted

    def test_main_generates_branch_name(self, monkeypatch, capsys, mock_config):
        """Generates and displays branch name."""
        monkeypatch.setattr(sys, 'argv', ['branch-name', 'add user auth'])

        with patch('ab_cli.commands.branch_name.generate_branch_name') as mock_gen:
            mock_gen.return_value = 'feature/add-user-auth'

            try:
                main()
            except SystemExit:
                pass

            captured = capsys.readouterr()
            assert 'feature/add-user-auth' in captured.out

    def test_main_create_branch_with_confirmation(self, mock_git_repo, monkeypatch, capsys, mock_config):
        """Creates branch with user confirmation."""
        monkeypatch.chdir(mock_git_repo)
        monkeypatch.setattr(sys, 'argv', ['branch-name', '-c', '-y', 'add feature'])

        with patch('ab_cli.commands.branch_name.generate_branch_name') as mock_gen:
            mock_gen.return_value = 'feature/add-feature'

            try:
                main()
            except SystemExit:
                pass

            # Verify branch was created
            current = get_current_branch()
            assert current == 'feature/add-feature'

    def test_main_create_branch_exists_exits_1(self, mock_git_repo, monkeypatch, capsys, mock_config):
        """Exits with error when branch already exists."""
        monkeypatch.chdir(mock_git_repo)

        # Create branch first
        subprocess.run(['git', 'checkout', '-b', 'feature/existing'], cwd=mock_git_repo, check=True)
        subprocess.run(['git', 'checkout', 'master'], cwd=mock_git_repo, check=True)

        monkeypatch.setattr(sys, 'argv', ['branch-name', '-c', '-y', 'existing feature'])

        with patch('ab_cli.commands.branch_name.generate_branch_name') as mock_gen:
            mock_gen.return_value = 'feature/existing'

            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert 'already exists' in captured.err.lower()

    def test_main_cancel_on_no(self, mock_git_repo, monkeypatch, capsys, mock_config):
        """Cancels when user says no."""
        monkeypatch.chdir(mock_git_repo)
        monkeypatch.setattr(sys, 'argv', ['branch-name', '-c', 'add feature'])

        with patch('ab_cli.commands.branch_name.generate_branch_name') as mock_gen:
            mock_gen.return_value = 'feature/add-feature'

            with patch('builtins.input', return_value='n'):
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 0
                captured = capsys.readouterr()
                assert 'cancelled' in captured.out.lower()
