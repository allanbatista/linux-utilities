"""Unit tests for ab_cli.utils.error_handling module."""
import pytest

from ab_cli.utils import (
    cli_error_handler,
    handle_cli_errors,
    AbCliError,
    GitError,
    LLMError,
    ConfigError,
)


class TestCliErrorHandler:
    """Tests for cli_error_handler context manager."""

    def test_passes_through_normal_execution(self):
        """Normal execution passes through without issues."""
        result = []
        with cli_error_handler():
            result.append(1)
            result.append(2)
        assert result == [1, 2]

    def test_catches_ab_cli_error_and_exits(self, capsys):
        """Catches AbCliError and exits with code 1."""
        with pytest.raises(SystemExit) as exc_info:
            with cli_error_handler():
                raise AbCliError("Test error message")

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Test error message" in captured.err

    def test_catches_git_error_subclass(self, capsys):
        """Catches GitError (subclass of AbCliError)."""
        with pytest.raises(SystemExit) as exc_info:
            with cli_error_handler():
                raise GitError("Not inside a git repository")

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Not inside a git repository" in captured.err

    def test_catches_llm_error_subclass(self, capsys):
        """Catches LLMError (subclass of AbCliError)."""
        with pytest.raises(SystemExit) as exc_info:
            with cli_error_handler():
                raise LLMError("API call failed")

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "API call failed" in captured.err

    def test_catches_config_error_subclass(self, capsys):
        """Catches ConfigError (subclass of AbCliError)."""
        with pytest.raises(SystemExit) as exc_info:
            with cli_error_handler():
                raise ConfigError("Invalid configuration")

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Invalid configuration" in captured.err

    def test_catches_keyboard_interrupt(self, capsys):
        """Catches KeyboardInterrupt and exits with code 130."""
        with pytest.raises(SystemExit) as exc_info:
            with cli_error_handler():
                raise KeyboardInterrupt()

        assert exc_info.value.code == 130
        captured = capsys.readouterr()
        assert "Aborted" in captured.out

    def test_does_not_catch_other_exceptions(self):
        """Does not catch non-AbCliError exceptions."""
        with pytest.raises(ValueError):
            with cli_error_handler():
                raise ValueError("Not an AbCliError")


class TestHandleCliErrors:
    """Tests for handle_cli_errors decorator."""

    def test_passes_through_normal_execution(self):
        """Normal execution passes through without issues."""
        @handle_cli_errors
        def my_func():
            return 42

        result = my_func()
        assert result == 42

    def test_preserves_function_arguments(self):
        """Preserves function arguments."""
        @handle_cli_errors
        def add(a, b):
            return a + b

        result = add(3, 5)
        assert result == 8

    def test_catches_ab_cli_error_and_exits(self, capsys):
        """Catches AbCliError and exits with code 1."""
        @handle_cli_errors
        def failing_func():
            raise AbCliError("Decorated error")

        with pytest.raises(SystemExit) as exc_info:
            failing_func()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Decorated error" in captured.err

    def test_catches_git_error_subclass(self, capsys):
        """Catches GitError (subclass of AbCliError)."""
        @handle_cli_errors
        def git_command():
            raise GitError("Git operation failed")

        with pytest.raises(SystemExit) as exc_info:
            git_command()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Git operation failed" in captured.err

    def test_catches_keyboard_interrupt(self, capsys):
        """Catches KeyboardInterrupt and exits with code 130."""
        @handle_cli_errors
        def interruptible():
            raise KeyboardInterrupt()

        with pytest.raises(SystemExit) as exc_info:
            interruptible()

        assert exc_info.value.code == 130

    def test_does_not_catch_other_exceptions(self):
        """Does not catch non-AbCliError exceptions."""
        @handle_cli_errors
        def bad_func():
            raise TypeError("Type error")

        with pytest.raises(TypeError):
            bad_func()

    def test_preserves_function_name(self):
        """Preserves function __name__ attribute."""
        @handle_cli_errors
        def my_named_function():
            pass

        assert my_named_function.__name__ == "my_named_function"

    def test_preserves_function_docstring(self):
        """Preserves function __doc__ attribute."""
        @handle_cli_errors
        def documented_func():
            """This is the docstring."""
            pass

        assert documented_func.__doc__ == "This is the docstring."


class TestRequireGitRepo:
    """Tests for require_git_repo function."""

    def test_require_git_repo_in_git_dir(self, mock_git_repo, monkeypatch):
        """Does not raise when inside git repository."""
        from ab_cli.utils import require_git_repo

        monkeypatch.chdir(mock_git_repo)
        # Should not raise
        require_git_repo()

    def test_require_git_repo_outside_git_dir(self, tmp_path, monkeypatch):
        """Raises GitError when outside git repository."""
        from ab_cli.utils import require_git_repo

        monkeypatch.chdir(tmp_path)
        with pytest.raises(GitError) as exc_info:
            require_git_repo()

        assert "Not inside a git repository" in str(exc_info.value)


class TestUtilsModuleExports:
    """Tests for exports from utils module."""

    def test_error_handling_exported_from_utils(self):
        """Error handling functions are exported from utils."""
        from ab_cli import utils

        assert hasattr(utils, 'cli_error_handler')
        assert hasattr(utils, 'handle_cli_errors')
        assert hasattr(utils, 'require_git_repo')
