"""Unit tests for ab_cli.commands.models module."""
import json
import sys
from argparse import Namespace
from unittest.mock import MagicMock, patch

import pytest

from ab_cli.commands.models import (
    cmd_info,
    cmd_list,
    fetch_models,
    filter_models,
    format_context,
    format_price,
    get_modalities,
    main,
    sort_models,
    truncate,
)


# Sample model data for testing
SAMPLE_MODELS = [
    {
        "id": "openai/gpt-4o",
        "name": "GPT-4o",
        "description": "OpenAI's most advanced multimodal model",
        "context_length": 128000,
        "pricing": {"prompt": "0.0000025", "completion": "0.00001"},
        "architecture": {
            "input_modalities": ["text", "image"],
            "output_modalities": ["text"],
        },
        "top_provider": {"max_completion_tokens": 16384},
        "supported_parameters": ["temperature", "top_p", "max_tokens"],
    },
    {
        "id": "anthropic/claude-3-haiku",
        "name": "Claude 3 Haiku",
        "description": "Fast and efficient Claude model",
        "context_length": 200000,
        "pricing": {"prompt": "0.00000025", "completion": "0.00000125"},
        "architecture": {
            "input_modalities": ["text", "image"],
            "output_modalities": ["text"],
        },
        "top_provider": {"max_completion_tokens": 4096},
        "supported_parameters": ["temperature", "top_p"],
    },
    {
        "id": "meta-llama/llama-3-8b:free",
        "name": "Llama 3 8B",
        "description": "Free Llama model",
        "context_length": 8192,
        "pricing": {"prompt": "0", "completion": "0"},
        "architecture": {
            "input_modalities": ["text"],
            "output_modalities": ["text"],
        },
        "top_provider": {"max_completion_tokens": 2048},
        "supported_parameters": ["temperature"],
    },
    {
        "id": "google/gemini-pro-vision",
        "name": "Gemini Pro Vision",
        "description": "Google's vision model",
        "context_length": 32000,
        "pricing": {"prompt": "0.00000025", "completion": "0.0000005"},
        "architecture": {
            "input_modalities": ["text", "image", "video"],
            "output_modalities": ["text"],
        },
        "top_provider": {"max_completion_tokens": 8192},
        "supported_parameters": ["temperature", "top_p"],
    },
]


class TestFormatPrice:
    """Tests for format_price function."""

    def test_format_price_free(self):
        """Returns FREE for zero pricing."""
        pricing = {"prompt": "0", "completion": "0"}
        result = format_price(pricing)
        assert "FREE" in result

    def test_format_price_paid(self):
        """Formats paid pricing correctly."""
        pricing = {"prompt": "0.0000025", "completion": "0.00001"}
        result = format_price(pricing)
        # Remove ANSI codes for comparison
        clean_result = result.replace("\033[0;32m", "").replace("\033[0m", "")
        assert "$2.50" in clean_result
        assert "$10.00" in clean_result

    def test_format_price_none(self):
        """Returns N/A for None pricing."""
        result = format_price(None)
        assert result == "N/A"

    def test_format_price_empty(self):
        """Returns N/A for empty pricing dict."""
        result = format_price({})
        assert result == "N/A"  # Empty dict is falsy, returns N/A


class TestFormatContext:
    """Tests for format_context function."""

    def test_format_context_millions(self):
        """Formats millions correctly."""
        result = format_context(1000000)
        assert result == "1.0M"

    def test_format_context_thousands(self):
        """Formats thousands correctly."""
        result = format_context(128000)
        assert result == "128k"

    def test_format_context_small(self):
        """Formats small values correctly."""
        result = format_context(512)
        assert result == "512"

    def test_format_context_none(self):
        """Returns N/A for None."""
        result = format_context(None)
        assert result == "N/A"


class TestGetModalities:
    """Tests for get_modalities function."""

    def test_get_modalities_multiple(self):
        """Returns comma-separated modalities."""
        model = {"architecture": {"input_modalities": ["text", "image"]}}
        result = get_modalities(model)
        assert "text" in result
        assert "image" in result

    def test_get_modalities_empty(self):
        """Returns 'text' for empty modalities."""
        model = {"architecture": {}}
        result = get_modalities(model)
        assert result == "text"

    def test_get_modalities_fallback(self):
        """Falls back to modality field."""
        model = {"architecture": {"modality": "text->text"}}
        result = get_modalities(model)
        assert result == "text->text"


class TestTruncate:
    """Tests for truncate function."""

    def test_truncate_short(self):
        """Doesn't truncate short text."""
        result = truncate("hello", 10)
        assert result == "hello"

    def test_truncate_exact(self):
        """Doesn't truncate exact length."""
        result = truncate("hello", 5)
        assert result == "hello"

    def test_truncate_long(self):
        """Truncates long text with ellipsis."""
        result = truncate("hello world", 8)
        assert result == "hello..."
        assert len(result) == 8


class TestFilterModels:
    """Tests for filter_models function."""

    def test_filter_free(self):
        """Filters free models."""
        args = Namespace(free=True, search=None, context_min=None, modality=None)
        result = filter_models(SAMPLE_MODELS, args)
        assert len(result) == 1
        assert result[0]["id"] == "meta-llama/llama-3-8b:free"

    def test_filter_search(self):
        """Filters by search term."""
        args = Namespace(free=False, search="claude", context_min=None, modality=None)
        result = filter_models(SAMPLE_MODELS, args)
        assert len(result) == 1
        assert result[0]["id"] == "anthropic/claude-3-haiku"

    def test_filter_search_case_insensitive(self):
        """Search is case insensitive."""
        args = Namespace(free=False, search="GPT", context_min=None, modality=None)
        result = filter_models(SAMPLE_MODELS, args)
        assert len(result) == 1
        assert result[0]["id"] == "openai/gpt-4o"

    def test_filter_context_min(self):
        """Filters by minimum context."""
        args = Namespace(free=False, search=None, context_min=100000, modality=None)
        result = filter_models(SAMPLE_MODELS, args)
        assert len(result) == 2
        assert all(m["context_length"] >= 100000 for m in result)

    def test_filter_modality(self):
        """Filters by modality."""
        args = Namespace(free=False, search=None, context_min=None, modality="video")
        result = filter_models(SAMPLE_MODELS, args)
        assert len(result) == 1
        assert result[0]["id"] == "google/gemini-pro-vision"

    def test_filter_combined(self):
        """Combines multiple filters."""
        args = Namespace(free=False, search=None, context_min=100000, modality="image")
        result = filter_models(SAMPLE_MODELS, args)
        assert len(result) == 2

    def test_filter_no_matches(self):
        """Returns empty for no matches."""
        args = Namespace(free=True, search="nonexistent", context_min=None, modality=None)
        result = filter_models(SAMPLE_MODELS, args)
        assert len(result) == 0


class TestSortModels:
    """Tests for sort_models function."""

    def test_sort_by_name(self):
        """Sorts by name alphabetically."""
        result = sort_models(SAMPLE_MODELS, "name")
        names = [m["name"] for m in result]
        assert names == sorted(names, key=str.lower)

    def test_sort_by_context(self):
        """Sorts by context length descending."""
        result = sort_models(SAMPLE_MODELS, "context")
        contexts = [m["context_length"] for m in result]
        assert contexts == sorted(contexts, reverse=True)

    def test_sort_by_price(self):
        """Sorts by price ascending."""
        result = sort_models(SAMPLE_MODELS, "price")
        # Free model should be first
        assert result[0]["id"] == "meta-llama/llama-3-8b:free"


class TestFetchModels:
    """Tests for fetch_models function."""

    def test_fetch_models_success(self):
        """Successfully fetches models."""
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": SAMPLE_MODELS}
            mock_get.return_value = mock_response

            result = fetch_models("https://api.test.com", "test-key")

            assert result == SAMPLE_MODELS
            mock_get.assert_called_once()

    def test_fetch_models_error(self, capsys):
        """Returns None on error."""
        import requests

        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.RequestException("Network error")

            result = fetch_models("https://api.test.com", "test-key")

            assert result is None
            captured = capsys.readouterr()
            assert "Failed to fetch" in captured.err


class TestCmdList:
    """Tests for cmd_list command."""

    def test_cmd_list_success(self, mock_config, mock_env, capsys):
        """Lists models successfully."""
        with patch("ab_cli.commands.models.fetch_models") as mock_fetch:
            mock_fetch.return_value = SAMPLE_MODELS

            args = Namespace(
                free=False,
                search=None,
                context_min=None,
                modality=None,
                limit=50,
                sort="name",
                json=False,
            )
            cmd_list(args)

            captured = capsys.readouterr()
            assert "openai/gpt-4o" in captured.out
            assert "GPT-4o" in captured.out

    def test_cmd_list_json(self, mock_config, mock_env, capsys):
        """Outputs JSON when requested."""
        with patch("ab_cli.commands.models.fetch_models") as mock_fetch:
            mock_fetch.return_value = SAMPLE_MODELS

            args = Namespace(
                free=False,
                search=None,
                context_min=None,
                modality=None,
                limit=50,
                sort="name",
                json=True,
            )
            cmd_list(args)

            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert isinstance(output, list)
            assert len(output) == len(SAMPLE_MODELS)

    def test_cmd_list_no_api_key(self, mock_config, capsys, monkeypatch):
        """Exits with error when no API key."""
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        args = Namespace(
            free=False,
            search=None,
            context_min=None,
            modality=None,
            limit=50,
            sort="name",
            json=False,
        )

        with pytest.raises(SystemExit) as exc_info:
            cmd_list(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "not set" in captured.err

    def test_cmd_list_with_limit(self, mock_config, mock_env, capsys):
        """Respects limit parameter."""
        with patch("ab_cli.commands.models.fetch_models") as mock_fetch:
            mock_fetch.return_value = SAMPLE_MODELS

            args = Namespace(
                free=False,
                search=None,
                context_min=None,
                modality=None,
                limit=2,
                sort="name",
                json=True,
            )
            cmd_list(args)

            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert len(output) == 2


class TestCmdInfo:
    """Tests for cmd_info command."""

    def test_cmd_info_exact_match(self, mock_config, mock_env, capsys):
        """Shows info for exact model ID match."""
        with patch("ab_cli.commands.models.fetch_models") as mock_fetch:
            mock_fetch.return_value = SAMPLE_MODELS

            args = Namespace(model_id="openai/gpt-4o", json=False)
            cmd_info(args)

            captured = capsys.readouterr()
            assert "openai/gpt-4o" in captured.out
            assert "GPT-4o" in captured.out
            assert "128,000" in captured.out

    def test_cmd_info_partial_match(self, mock_config, mock_env, capsys):
        """Finds model with partial ID match."""
        with patch("ab_cli.commands.models.fetch_models") as mock_fetch:
            mock_fetch.return_value = SAMPLE_MODELS

            args = Namespace(model_id="gpt-4o", json=False)
            cmd_info(args)

            captured = capsys.readouterr()
            assert "openai/gpt-4o" in captured.out

    def test_cmd_info_not_found(self, mock_config, mock_env, capsys):
        """Exits with error when model not found."""
        with patch("ab_cli.commands.models.fetch_models") as mock_fetch:
            mock_fetch.return_value = SAMPLE_MODELS

            args = Namespace(model_id="nonexistent/model", json=False)

            with pytest.raises(SystemExit) as exc_info:
                cmd_info(args)

            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "not found" in captured.err

    def test_cmd_info_json(self, mock_config, mock_env, capsys):
        """Outputs JSON when requested."""
        with patch("ab_cli.commands.models.fetch_models") as mock_fetch:
            mock_fetch.return_value = SAMPLE_MODELS

            args = Namespace(model_id="openai/gpt-4o", json=True)
            cmd_info(args)

            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert output["id"] == "openai/gpt-4o"
            assert output["name"] == "GPT-4o"

    def test_cmd_info_multiple_matches(self, mock_config, mock_env, capsys):
        """Exits with error for ambiguous partial match."""
        with patch("ab_cli.commands.models.fetch_models") as mock_fetch:
            mock_fetch.return_value = SAMPLE_MODELS

            # "a" matches multiple models (llama, gemma, etc.)
            args = Namespace(model_id="llama", json=False)
            cmd_info(args)

            # Should succeed because only one llama model
            captured = capsys.readouterr()
            assert "Llama" in captured.out


class TestMain:
    """Tests for main() entry point."""

    def test_main_no_command_defaults_to_list(self, mock_config, mock_env, capsys, monkeypatch):
        """No command defaults to list."""
        monkeypatch.setattr(sys, "argv", ["ab-models"])

        with patch("ab_cli.commands.models.fetch_models") as mock_fetch:
            mock_fetch.return_value = SAMPLE_MODELS
            main()

            captured = capsys.readouterr()
            assert "openai/gpt-4o" in captured.out

    def test_main_list_command(self, mock_config, mock_env, capsys, monkeypatch):
        """'list' command works."""
        monkeypatch.setattr(sys, "argv", ["ab-models", "list", "--limit", "2"])

        with patch("ab_cli.commands.models.fetch_models") as mock_fetch:
            mock_fetch.return_value = SAMPLE_MODELS
            main()

            captured = capsys.readouterr()
            # Should show table output
            assert "ID" in captured.out or "openai" in captured.out

    def test_main_list_free(self, mock_config, mock_env, capsys, monkeypatch):
        """'list --free' filters correctly."""
        monkeypatch.setattr(sys, "argv", ["ab-models", "list", "--free", "--json"])

        with patch("ab_cli.commands.models.fetch_models") as mock_fetch:
            mock_fetch.return_value = SAMPLE_MODELS
            main()

            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert len(output) == 1
            assert output[0]["id"] == "meta-llama/llama-3-8b:free"

    def test_main_info_command(self, mock_config, mock_env, capsys, monkeypatch):
        """'info' command works."""
        monkeypatch.setattr(sys, "argv", ["ab-models", "info", "openai/gpt-4o"])

        with patch("ab_cli.commands.models.fetch_models") as mock_fetch:
            mock_fetch.return_value = SAMPLE_MODELS
            main()

            captured = capsys.readouterr()
            assert "GPT-4o" in captured.out

    def test_main_help(self, capsys, monkeypatch):
        """'--help' shows help."""
        monkeypatch.setattr(sys, "argv", ["ab-models", "--help"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "List and explore available LLM models" in captured.out
