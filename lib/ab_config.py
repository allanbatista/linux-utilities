"""
Centralized configuration module for ab CLI utilities.
Handles loading, saving, and managing configuration.
"""
import json
import os
import pathlib
from typing import Any, Dict, Optional

AB_CONFIG_DIR = pathlib.Path.home() / ".ab"
AB_CONFIG_FILE = AB_CONFIG_DIR / "config.json"
AB_HISTORY_DIR = AB_CONFIG_DIR / "history"

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": "1.0",
    "global": {
        "language": "en",
        "api_base": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "timeout_seconds": 300
    },
    "models": {
        "small": "nvidia/nemotron-3-nano-30b-a3b:free",
        "medium": "openai/gpt-5-nano",
        "large": "x-ai/grok-4.1-fast",
        "default": "nvidia/nemotron-3-nano-30b-a3b:free",
        "thresholds": {
            "small_max_tokens": 128000,
            "medium_max_tokens": 256000
        }
    },
    "commands": {
        "auto-commit": {},
        "pr-description": {},
        "rewrite-history": {
            "smart_mode": True,
            "skip_merges": True
        },
        "prompt": {
            "max_tokens": 900000,
            "max_tokens_doc": 250000,
            "max_completion_tokens": 16000
        },
        "passgenerator": {
            "default_length": 16
        }
    },
    "history": {
        "enabled": True,
        "directory": str(AB_HISTORY_DIR)
    }
}


class AbConfig:
    """Configuration manager for ab CLI (singleton)."""

    _instance: Optional['AbConfig'] = None
    _config: Dict[str, Any]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config = {}
            cls._instance._loaded = False
        return cls._instance

    def _ensure_loaded(self) -> None:
        """Ensure configuration is loaded."""
        if not self._loaded:
            self._load()

    def _load(self) -> None:
        """Load configuration from file or use defaults."""
        if AB_CONFIG_FILE.exists():
            try:
                with open(AB_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not read {AB_CONFIG_FILE}: {e}")
                self._config = self._deep_copy(DEFAULT_CONFIG)
        else:
            self._config = self._deep_copy(DEFAULT_CONFIG)
        self._loaded = True

    def _deep_copy(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Deep copy a dictionary."""
        return json.loads(json.dumps(d))

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries, override takes precedence."""
        result = self._deep_copy(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def reload(self) -> None:
        """Force reload configuration from file."""
        self._loaded = False
        self._ensure_loaded()

    def get(self, path: str, default: Any = None) -> Any:
        """
        Get config value by dot-notation path.

        Example: config.get('global.language', 'en')
        """
        self._ensure_loaded()
        keys = path.split('.')
        value = self._config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value if value is not None else default

    def set(self, path: str, value: Any) -> None:
        """
        Set config value by dot-notation path and persist.

        Example: config.set('global.language', 'pt-br')
        """
        self._ensure_loaded()
        keys = path.split('.')
        config = self._config

        # Navigate to parent
        for key in keys[:-1]:
            config = config.setdefault(key, {})

        # Set value
        config[keys[-1]] = value
        self._save()

    def _save(self) -> None:
        """Save configuration to file."""
        AB_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(AB_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)

    def get_with_default(self, path: str) -> Any:
        """Get config value with fallback to DEFAULT_CONFIG."""
        value = self.get(path)
        if value is not None:
            return value

        # Fallback to default
        keys = path.split('.')
        default_value = DEFAULT_CONFIG
        for key in keys:
            if isinstance(default_value, dict) and key in default_value:
                default_value = default_value[key]
            else:
                return None
        return default_value

    def select_model(self, tokens: int) -> str:
        """
        Select model based on token count.

        Returns appropriate model for the given context size.
        """
        self._ensure_loaded()

        thresholds = self.get('models.thresholds', {})
        small_max = thresholds.get('small_max_tokens', 128000)
        medium_max = thresholds.get('medium_max_tokens', 256000)

        if tokens <= small_max:
            return self.get_with_default('models.small')
        elif tokens <= medium_max:
            return self.get_with_default('models.medium')
        else:
            return self.get_with_default('models.large')

    def get_command_setting(self, command: str, setting: str, default: Any = None) -> Any:
        """
        Get command-specific setting with fallback to global.

        Precedence:
        1. commands.<command>.<setting>
        2. global.<setting>
        3. default parameter
        """
        self._ensure_loaded()

        # Try command-specific first
        cmd_value = self.get(f'commands.{command}.{setting}')
        if cmd_value is not None:
            return cmd_value

        # Fallback to global
        global_value = self.get(f'global.{setting}')
        if global_value is not None:
            return global_value

        return default

    def get_api_settings(self) -> Dict[str, Any]:
        """Get API-related settings."""
        self._ensure_loaded()
        return {
            'api_base': self.get_with_default('global.api_base'),
            'api_key_env': self.get_with_default('global.api_key_env'),
            'timeout_seconds': self.get_with_default('global.timeout_seconds'),
        }

    def get_history_dir(self) -> pathlib.Path:
        """Get history directory path."""
        self._ensure_loaded()
        dir_str = self.get('history.directory', str(AB_HISTORY_DIR))
        # Expand ~ if present
        return pathlib.Path(os.path.expanduser(dir_str))

    def is_history_enabled(self) -> bool:
        """Check if history tracking is enabled."""
        return self.get('history.enabled', True)

    def init_config(self) -> bool:
        """
        Initialize configuration file with defaults.
        Returns True if created, False if already exists.
        """
        if AB_CONFIG_FILE.exists():
            return False

        AB_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._config = self._deep_copy(DEFAULT_CONFIG)
        self._save()
        self._loaded = True
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Return full configuration as dictionary."""
        self._ensure_loaded()
        return self._deep_copy(self._config)

    def config_exists(self) -> bool:
        """Check if config file exists."""
        return AB_CONFIG_FILE.exists()

    @staticmethod
    def get_config_path() -> pathlib.Path:
        """Get config file path."""
        return AB_CONFIG_FILE

    @staticmethod
    def get_config_dir() -> pathlib.Path:
        """Get config directory path."""
        return AB_CONFIG_DIR


def get_config() -> AbConfig:
    """Get the singleton config instance."""
    return AbConfig()


def estimate_tokens(text: str) -> int:
    """
    Estimate token count from text.
    Uses ~4 characters per token approximation.
    """
    return len(text) // 4


# Convenience functions for common operations
def get_language(command: str = None) -> str:
    """Get language setting, optionally for a specific command."""
    config = get_config()
    if command:
        return config.get_command_setting(command, 'language', 'en')
    return config.get_with_default('global.language')


def get_default_model() -> str:
    """Get the default model."""
    return get_config().get_with_default('models.default')


def select_model_for_tokens(tokens: int) -> str:
    """Select appropriate model for given token count."""
    return get_config().select_model(tokens)
