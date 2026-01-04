"""Custom exceptions for ab-cli.

Provides a hierarchy of exceptions for consistent error handling.
"""


class AbCliError(Exception):
    """Base exception for ab-cli.

    All custom exceptions should inherit from this class.
    """
    pass


class GitError(AbCliError):
    """Error in git operations.

    Raised when a git command fails or when not in a git repository.
    """
    pass


class LLMError(AbCliError):
    """Error in LLM API calls.

    Raised when the LLM API call fails, times out, or returns invalid response.
    """
    pass


class ConfigError(AbCliError):
    """Error in configuration.

    Raised when configuration is missing, invalid, or cannot be loaded.
    """
    pass


class FileOperationError(AbCliError):
    """Error in file operations.

    Raised when file read/write operations fail.
    """
    pass
