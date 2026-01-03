"""Unit tests for ab_cli.commands.config_cli module."""
import json
import sys
from argparse import Namespace

import pytest

from ab_cli.commands.config_cli import (
    cmd_get,
    cmd_init,
    cmd_list_keys,
    cmd_path,
    cmd_set,
    cmd_show,
    main,
)
from ab_cli.core.config import DEFAULT_CONFIG, get_config


class TestCmdShow:
    """Tests for cmd_show command."""

    def test_cmd_show_displays_config(self, mock_config, capsys):
        """Shows JSON output when config exists."""
        args = Namespace()
        cmd_show(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "version" in output
        assert "global" in output

    def test_cmd_show_no_config_shows_defaults(self, temp_config_dir, capsys):
        """Shows defaults when no config file exists."""
        args = Namespace()
        cmd_show(args)

        captured = capsys.readouterr()
        assert "No configuration file found" in captured.out
        assert "Using default configuration" in captured.out


class TestCmdGet:
    """Tests for cmd_get command."""

    def test_cmd_get_existing_key(self, mock_config, capsys):
        """Returns value for existing key."""
        args = Namespace(key="global.language")
        cmd_get(args)

        captured = capsys.readouterr()
        assert captured.out.strip() == "en"

    def test_cmd_get_nested_dict_as_json(self, mock_config, capsys):
        """Returns dict values as JSON."""
        args = Namespace(key="models.thresholds")
        cmd_get(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "small_max_tokens" in output

    def test_cmd_get_missing_key_exits_1(self, mock_config, capsys):
        """Exits with error for missing key."""
        args = Namespace(key="nonexistent.key.path")

        with pytest.raises(SystemExit) as exc_info:
            cmd_get(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Key not found" in captured.err

    def test_cmd_get_falls_back_to_defaults(self, temp_config_dir, capsys):
        """Falls back to DEFAULT_CONFIG for missing keys."""
        args = Namespace(key="global.language")
        cmd_get(args)

        captured = capsys.readouterr()
        assert captured.out.strip() == DEFAULT_CONFIG["global"]["language"]


class TestCmdSet:
    """Tests for cmd_set command."""

    def test_cmd_set_string_value(self, mock_config, capsys, temp_config_dir):
        """Sets string value correctly."""
        args = Namespace(key="global.language", value="fr")
        cmd_set(args)

        # Verify set
        config = get_config()
        config.reload()
        assert config.get("global.language") == "fr"

        captured = capsys.readouterr()
        assert "Set global.language = fr" in captured.out

    def test_cmd_set_bool_true(self, mock_config, capsys, temp_config_dir):
        """'true' string converts to True boolean."""
        args = Namespace(key="history.enabled", value="true")
        cmd_set(args)

        config = get_config()
        config.reload()
        assert config.get("history.enabled") is True

    def test_cmd_set_bool_false(self, mock_config, capsys, temp_config_dir):
        """'false' string converts to False boolean."""
        args = Namespace(key="history.enabled", value="false")
        cmd_set(args)

        config = get_config()
        config.reload()
        assert config.get("history.enabled") is False

    def test_cmd_set_int_value(self, mock_config, capsys, temp_config_dir):
        """Numeric string converts to integer."""
        args = Namespace(key="global.timeout_seconds", value="600")
        cmd_set(args)

        config = get_config()
        config.reload()
        assert config.get("global.timeout_seconds") == 600

    def test_cmd_set_json_value(self, mock_config, capsys, temp_config_dir):
        """JSON string is parsed correctly."""
        args = Namespace(key="custom.data", value='{"nested": true}')
        cmd_set(args)

        config = get_config()
        config.reload()
        assert config.get("custom.data") == {"nested": True}

    def test_cmd_set_auto_creates_config(self, temp_config_dir, capsys):
        """Auto-creates config if it doesn't exist."""
        from ab_cli.core import config as config_module

        args = Namespace(key="global.language", value="de")
        cmd_set(args)

        captured = capsys.readouterr()
        assert "Created config file" in captured.out
        assert config_module.AB_CONFIG_FILE.exists()


class TestCmdInit:
    """Tests for cmd_init command."""

    def test_cmd_init_creates_config(self, temp_config_dir, capsys):
        """Creates default config file."""
        from ab_cli.core import config as config_module

        args = Namespace(force=False)
        cmd_init(args)

        assert config_module.AB_CONFIG_FILE.exists()
        captured = capsys.readouterr()
        assert "Created default config" in captured.out

    def test_cmd_init_existing_without_force_exits(self, mock_config, capsys):
        """Exits with error if config exists without --force."""
        args = Namespace(force=False)

        with pytest.raises(SystemExit) as exc_info:
            cmd_init(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Config already exists" in captured.out

    def test_cmd_init_force_overwrites(self, mock_config, temp_config_dir, capsys, monkeypatch):
        """--force replaces existing config."""
        from ab_cli.core import config as config_module
        from ab_cli.commands import config_cli

        # Patch the AB_CONFIG_FILE in config_cli module
        monkeypatch.setattr(config_cli, "AB_CONFIG_FILE", config_module.AB_CONFIG_FILE)

        # Modify existing config
        config = get_config()
        config.set("global.language", "custom")

        args = Namespace(force=True)
        cmd_init(args)

        captured = capsys.readouterr()
        assert "Backed up existing config" in captured.out
        assert "Created default config" in captured.out

        # Backup should exist
        backup_file = config_module.AB_CONFIG_FILE.parent / (config_module.AB_CONFIG_FILE.name + ".bak")
        assert backup_file.exists()


class TestCmdPath:
    """Tests for cmd_path command."""

    def test_cmd_path_shows_path(self, temp_config_dir, capsys, monkeypatch):
        """Shows config file path."""
        from ab_cli.core import config as config_module
        from ab_cli.commands import config_cli

        # Also patch the AB_CONFIG_FILE in config_cli module
        monkeypatch.setattr(config_cli, "AB_CONFIG_FILE", config_module.AB_CONFIG_FILE)

        args = Namespace()
        cmd_path(args)

        captured = capsys.readouterr()
        assert str(config_module.AB_CONFIG_FILE) in captured.out


class TestCmdListKeys:
    """Tests for cmd_list_keys command."""

    def test_cmd_list_keys(self, capsys):
        """Lists all available config keys."""
        args = Namespace()
        cmd_list_keys(args)

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")

        # Should include known keys
        assert any("global.language" in line for line in lines)
        assert any("models.default" in line for line in lines)
        assert any("version" in line for line in lines)


class TestMain:
    """Tests for main() entry point."""

    def test_main_no_command_shows_help(self, capsys, monkeypatch):
        """No command shows help and exits 0."""
        monkeypatch.setattr(sys, "argv", ["ab-config"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0

    def test_main_show_command(self, mock_config, capsys, monkeypatch):
        """'show' command works."""
        monkeypatch.setattr(sys, "argv", ["ab-config", "show"])
        main()

        captured = capsys.readouterr()
        assert "version" in captured.out

    def test_main_get_command(self, mock_config, capsys, monkeypatch):
        """'get' command works."""
        monkeypatch.setattr(sys, "argv", ["ab-config", "get", "version"])
        main()

        captured = capsys.readouterr()
        assert "1.0" in captured.out

    def test_main_path_command(self, temp_config_dir, capsys, monkeypatch):
        """'path' command works."""
        monkeypatch.setattr(sys, "argv", ["ab-config", "path"])
        main()

        captured = capsys.readouterr()
        assert "config.json" in captured.out
