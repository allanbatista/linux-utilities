"""Unit tests for ab_cli.utils.exceptions module."""
import pytest


class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""

    def test_ab_cli_error_is_exception(self):
        """AbCliError inherits from Exception."""
        from ab_cli.utils.exceptions import AbCliError

        assert issubclass(AbCliError, Exception)

    def test_git_error_inherits_from_ab_cli_error(self):
        """GitError inherits from AbCliError."""
        from ab_cli.utils.exceptions import GitError, AbCliError

        assert issubclass(GitError, AbCliError)
        assert issubclass(GitError, Exception)

    def test_llm_error_inherits_from_ab_cli_error(self):
        """LLMError inherits from AbCliError."""
        from ab_cli.utils.exceptions import LLMError, AbCliError

        assert issubclass(LLMError, AbCliError)
        assert issubclass(LLMError, Exception)

    def test_config_error_inherits_from_ab_cli_error(self):
        """ConfigError inherits from AbCliError."""
        from ab_cli.utils.exceptions import ConfigError, AbCliError

        assert issubclass(ConfigError, AbCliError)
        assert issubclass(ConfigError, Exception)

    def test_file_operation_error_inherits_from_ab_cli_error(self):
        """FileOperationError inherits from AbCliError."""
        from ab_cli.utils.exceptions import FileOperationError, AbCliError

        assert issubclass(FileOperationError, AbCliError)
        assert issubclass(FileOperationError, Exception)


class TestExceptionRaising:
    """Tests for raising exceptions."""

    def test_raise_ab_cli_error(self):
        """AbCliError can be raised with message."""
        from ab_cli.utils.exceptions import AbCliError

        with pytest.raises(AbCliError) as exc_info:
            raise AbCliError("Test error message")

        assert "Test error message" in str(exc_info.value)

    def test_raise_git_error(self):
        """GitError can be raised with message."""
        from ab_cli.utils.exceptions import GitError

        with pytest.raises(GitError) as exc_info:
            raise GitError("Git operation failed")

        assert "Git operation failed" in str(exc_info.value)

    def test_raise_llm_error(self):
        """LLMError can be raised with message."""
        from ab_cli.utils.exceptions import LLMError

        with pytest.raises(LLMError) as exc_info:
            raise LLMError("API call failed")

        assert "API call failed" in str(exc_info.value)

    def test_raise_config_error(self):
        """ConfigError can be raised with message."""
        from ab_cli.utils.exceptions import ConfigError

        with pytest.raises(ConfigError) as exc_info:
            raise ConfigError("Invalid configuration")

        assert "Invalid configuration" in str(exc_info.value)

    def test_raise_file_operation_error(self):
        """FileOperationError can be raised with message."""
        from ab_cli.utils.exceptions import FileOperationError

        with pytest.raises(FileOperationError) as exc_info:
            raise FileOperationError("File not found")

        assert "File not found" in str(exc_info.value)


class TestExceptionCatching:
    """Tests for catching exceptions."""

    def test_catch_git_error_as_ab_cli_error(self):
        """GitError can be caught as AbCliError."""
        from ab_cli.utils.exceptions import GitError, AbCliError

        try:
            raise GitError("Git error")
        except AbCliError as e:
            assert "Git error" in str(e)
        else:
            pytest.fail("GitError should be catchable as AbCliError")

    def test_catch_llm_error_as_ab_cli_error(self):
        """LLMError can be caught as AbCliError."""
        from ab_cli.utils.exceptions import LLMError, AbCliError

        try:
            raise LLMError("LLM error")
        except AbCliError as e:
            assert "LLM error" in str(e)
        else:
            pytest.fail("LLMError should be catchable as AbCliError")

    def test_catch_all_custom_exceptions_as_ab_cli_error(self):
        """All custom exceptions can be caught as AbCliError."""
        from ab_cli.utils.exceptions import (
            AbCliError, GitError, LLMError, ConfigError, FileOperationError
        )

        exceptions = [
            GitError("git"),
            LLMError("llm"),
            ConfigError("config"),
            FileOperationError("file"),
        ]

        for exc in exceptions:
            try:
                raise exc
            except AbCliError:
                pass  # Expected
            else:
                pytest.fail(f"{type(exc).__name__} should be catchable as AbCliError")


class TestUtilsModuleExceptions:
    """Tests for exceptions exported from utils module."""

    def test_exceptions_exported_from_utils(self):
        """All exceptions are exported from utils module."""
        from ab_cli.utils import (
            AbCliError,
            GitError,
            LLMError,
            ConfigError,
            FileOperationError,
        )

        assert issubclass(AbCliError, Exception)
        assert issubclass(GitError, AbCliError)
        assert issubclass(LLMError, AbCliError)
        assert issubclass(ConfigError, AbCliError)
        assert issubclass(FileOperationError, AbCliError)
