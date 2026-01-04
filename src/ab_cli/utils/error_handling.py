"""Error handling utilities for ab-cli.

Provides context managers and decorators for consistent error handling.
"""
import sys
from contextlib import contextmanager
from functools import wraps
from typing import Callable, Generator, TypeVar

from ab_cli.utils.exceptions import AbCliError
from ab_cli.utils.logging import log_error

F = TypeVar('F', bound=Callable)


@contextmanager
def cli_error_handler() -> Generator[None, None, None]:
    """Context manager for CLI error handling.

    Catches AbCliError exceptions and converts them to sys.exit() calls
    with appropriate error messages.

    Usage:
        def main():
            with cli_error_handler():
                require_git_repo()
                # ... rest of command logic
    """
    try:
        yield
    except AbCliError as e:
        log_error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)


def handle_cli_errors(func: F) -> F:
    """Decorator for CLI main functions.

    Wraps a function to catch AbCliError exceptions and convert them
    to sys.exit() calls with appropriate error messages.

    Usage:
        @handle_cli_errors
        def main():
            require_git_repo()
            # ... rest of command logic
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AbCliError as e:
            log_error(str(e))
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nAborted.")
            sys.exit(130)
    return wrapper  # type: ignore
