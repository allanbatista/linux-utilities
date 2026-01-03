"""Pytest configuration and fixtures for ab-cli tests."""
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset AbConfig singleton between tests."""
    from ab_cli.core import config as config_module

    # Save original values
    original_instance = config_module.AbConfig._instance

    # Reset singleton
    config_module.AbConfig._instance = None

    yield

    # Restore (cleanup)
    config_module.AbConfig._instance = original_instance


@pytest.fixture
def temp_config_dir(tmp_path: Path, monkeypatch) -> Path:
    """Create temporary config directory and patch config paths."""
    from ab_cli.core import config as config_module

    config_dir = tmp_path / ".ab"
    config_dir.mkdir(parents=True)

    config_file = config_dir / "config.json"
    history_dir = config_dir / "history"

    # Patch the module-level constants
    monkeypatch.setattr(config_module, "AB_CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_module, "AB_CONFIG_FILE", config_file)
    monkeypatch.setattr(config_module, "AB_HISTORY_DIR", history_dir)

    return config_dir


@pytest.fixture
def mock_config(temp_config_dir: Path) -> Dict[str, Any]:
    """Create a mock configuration file."""
    from ab_cli.core import config as config_module

    config_data = {
        "version": "1.0",
        "global": {
            "language": "en",
            "api_base": "https://openrouter.ai/api/v1",
            "api_key_env": "OPENROUTER_API_KEY",
            "timeout_seconds": 300
        },
        "models": {
            "small": "test/model-small",
            "medium": "test/model-medium",
            "large": "test/model-large",
            "default": "test/model-small",
            "thresholds": {
                "small_max_tokens": 128000,
                "medium_max_tokens": 256000
            }
        },
        "commands": {
            "auto-commit": {"language": "pt-br"},
            "pr-description": {},
            "rewrite-history": {
                "smart_mode": True,
                "skip_merges": True
            },
            "prompt": {
                "max_tokens": 900000,
                "max_tokens_doc": 250000,
                "max_completion_tokens": 16000
            }
        },
        "history": {
            "enabled": True,
            "directory": str(temp_config_dir / "history")
        }
    }

    config_file = config_module.AB_CONFIG_FILE
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)

    return config_data


@pytest.fixture
def mock_git_repo(tmp_path: Path) -> Path:
    """Create a mock git repository."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    # Initialize git repo
    subprocess.run(
        ["git", "init"],
        cwd=repo_dir,
        capture_output=True,
        check=True
    )

    # Configure git user for commits
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_dir,
        capture_output=True,
        check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        capture_output=True,
        check=True
    )

    # Create initial commit
    readme = repo_dir / "README.md"
    readme.write_text("# Test Repository\n")

    subprocess.run(
        ["git", "add", "README.md"],
        cwd=repo_dir,
        capture_output=True,
        check=True
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_dir,
        capture_output=True,
        check=True
    )

    return repo_dir


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run for git commands."""
    with patch("subprocess.run") as mock:
        mock.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr=""
        )
        yield mock


@pytest.fixture
def mock_requests():
    """Mock requests library for API calls."""
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50}
        }
        mock_post.return_value = mock_response
        yield mock_post


@pytest.fixture
def mock_input():
    """Mock user input."""
    with patch("builtins.input") as mock:
        yield mock


@pytest.fixture
def mock_env(monkeypatch):
    """Set up mock environment variables."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-api-key-12345")
    return {"OPENROUTER_API_KEY": "test-api-key-12345"}


@pytest.fixture
def capture_stdout(capsys):
    """Capture stdout for verification."""
    return capsys


@pytest.fixture
def mock_stdin():
    """Mock stdin for reading."""
    with patch("sys.stdin") as mock:
        yield mock
