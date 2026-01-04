"""Centralized logging utilities for ab-cli.

Provides consistent colored output for all commands.
"""
import sys

# ANSI color codes
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
NC = '\033[0m'  # No Color


def log_info(msg: str) -> None:
    """Print an info message in blue."""
    print(f"{BLUE}[INFO]{NC} {msg}")


def log_success(msg: str) -> None:
    """Print a success message in green."""
    print(f"{GREEN}[SUCCESS]{NC} {msg}")


def log_warning(msg: str) -> None:
    """Print a warning message in yellow."""
    print(f"{YELLOW}[WARNING]{NC} {msg}")


def log_error(msg: str) -> None:
    """Print an error message in red to stderr."""
    print(f"{RED}[ERROR]{NC} {msg}", file=sys.stderr)


def log_debug(msg: str) -> None:
    """Print a debug message in cyan."""
    print(f"{CYAN}[DEBUG]{NC} {msg}")
