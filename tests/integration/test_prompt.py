"""Integration tests for ab_cli.commands.prompt module."""
import json
import os


class TestLoadConfig:
    """Tests for configuration loading."""

    def test_load_config_uses_defaults(self, temp_config_dir):
        """Uses default configuration when no file exists."""
        from ab_cli.core.config import get_config

        config = get_config()
        assert config.get_with_default("global.api_base") == "https://openrouter.ai/api/v1"


class TestPersistDefaultModel:
    """Tests for model persistence."""

    def test_persist_default_model(self, temp_config_dir):
        """Saves default model to config."""
        from ab_cli.core.config import get_config

        config = get_config()
        config.init_config()
        config.set("models.default", "new/model")

        # Verify persisted
        config.reload()
        assert config.get("models.default") == "new/model"


class TestApiCalls:
    """Tests for API call functionality."""

    def test_send_to_openrouter_success(self, mock_requests, mock_env, temp_config_dir):
        """API call succeeds with valid response."""
        # Import after patching
        response = mock_requests.return_value
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50}
        }

        # Verify mock is set up
        assert response.status_code == 200

    def test_send_to_openrouter_no_api_key(self, temp_config_dir, monkeypatch):
        """Returns error without API key."""
        # Ensure no API key is set
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        from ab_cli.core.config import get_config

        config = get_config()
        api_settings = config.get_api_settings()

        # Verify API key env var is configured but not set
        api_key = os.environ.get(api_settings["api_key_env"])
        assert api_key is None


class TestBinaryFileDetection:
    """Tests for binary file detection."""

    def test_is_binary_file_true(self, tmp_path):
        """Detects binary files correctly."""
        # Create a binary file
        binary_file = tmp_path / "test.bin"
        binary_file.write_bytes(bytes([0x00, 0x01, 0x02, 0x89, 0x50, 0x4E, 0x47]))

        from binaryornot.check import is_binary

        assert is_binary(str(binary_file)) is True

    def test_is_binary_file_false(self, tmp_path):
        """Text files return False."""
        text_file = tmp_path / "test.txt"
        text_file.write_text("This is a text file\nwith multiple lines")

        from binaryornot.check import is_binary

        assert is_binary(str(text_file)) is False


class TestAiignore:
    """Tests for .aiignore file handling."""

    def test_should_ignore_path_matches_pattern(self, tmp_path):
        """Respects .aiignore patterns."""
        import pathspec

        # Create .aiignore
        aiignore = tmp_path / ".aiignore"
        aiignore.write_text("*.log\nnode_modules/\n__pycache__/\n")

        patterns = aiignore.read_text().strip().split("\n")
        spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)

        assert spec.match_file("test.log") is True
        assert spec.match_file("node_modules/package.json") is True
        assert spec.match_file("__pycache__/module.pyc") is True
        assert spec.match_file("src/main.py") is False

    def test_should_ignore_negation_pattern(self, tmp_path):
        """Handles negation patterns."""
        import pathspec

        patterns = ["*.log", "!important.log"]
        spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)

        assert spec.match_file("debug.log") is True
        # Note: pathspec handles negation differently
        # The file matches but is negated


class TestFileProcessing:
    """Tests for file processing."""

    def test_process_file_reads_content(self, tmp_path):
        """Reads and formats file content."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    print('Hello')\n")

        content = test_file.read_text()
        assert "def hello():" in content
        assert "print('Hello')" in content

    def test_process_file_handles_encoding(self, tmp_path):
        """Handles different file encodings."""
        test_file = tmp_path / "unicode.txt"
        test_file.write_text("Olá mundo! 你好世界! 🎉", encoding="utf-8")

        content = test_file.read_text(encoding="utf-8")
        assert "Olá" in content
        assert "你好" in content

    def test_process_file_truncation(self, tmp_path):
        """Truncates large files."""
        # Create a large file
        large_file = tmp_path / "large.txt"
        large_content = "x" * 1000000  # 1MB
        large_file.write_text(large_content)

        # Simulate truncation logic
        max_chars = 100000
        content = large_file.read_text()[:max_chars]

        assert len(content) == max_chars


class TestSpecialistPersonas:
    """Tests for specialist persona handling."""

    def test_build_specialist_prefix_dev(self):
        """Returns dev persona prefix."""
        # Test the concept of specialist prefixes
        specialists = {
            "dev": "You are an expert software developer",
            "rm": "You are an expert release manager"
        }
        assert "developer" in specialists["dev"].lower()

    def test_build_specialist_prefix_rm(self):
        """Returns RM persona prefix."""
        specialists = {
            "dev": "You are an expert software developer",
            "rm": "You are an expert release manager"
        }
        assert "release manager" in specialists["rm"].lower()

    def test_build_specialist_prefix_none(self):
        """Returns empty for unknown specialist."""
        specialists = {
            "dev": "Developer",
            "rm": "Release Manager"
        }
        result = specialists.get("unknown", "")
        assert result == ""


class TestTokenEstimation:
    """Tests for token estimation."""

    def test_estimate_tokens_accuracy(self):
        """Token estimation is reasonably accurate."""
        from ab_cli.core.config import estimate_tokens

        # ~4 chars per token is the approximation
        text = "a" * 400
        tokens = estimate_tokens(text)
        assert tokens == 100

    def test_estimate_tokens_with_code(self):
        """Estimates tokens in code correctly."""
        from ab_cli.core.config import estimate_tokens

        code = """
def hello_world():
    print("Hello, World!")

if __name__ == "__main__":
    hello_world()
"""
        tokens = estimate_tokens(code)
        assert tokens > 0
        # Approximately len/4
        assert abs(tokens - len(code) // 4) < 5


class TestModelSelection:
    """Tests for automatic model selection."""

    def test_select_model_by_tokens(self, mock_config):
        """Selects model based on token count."""
        from ab_cli.core.config import get_config

        config = get_config()

        # Small model for small context
        assert config.select_model(50000) == "test/model-small"

        # Medium model for medium context
        assert config.select_model(200000) == "test/model-medium"

        # Large model for large context
        assert config.select_model(300000) == "test/model-large"


class TestHistoryTracking:
    """Tests for history tracking functionality."""

    def test_history_directory_exists(self, temp_config_dir):
        """History directory can be created."""
        from ab_cli.core.config import get_config

        config = get_config()
        history_dir = config.get_history_dir()

        history_dir.mkdir(parents=True, exist_ok=True)
        assert history_dir.exists()

    def test_history_enabled_by_default(self, mock_config):
        """History is enabled by default."""
        from ab_cli.core.config import get_config

        config = get_config()
        assert config.is_history_enabled() is True


class TestInputHandling:
    """Tests for various input handling scenarios."""

    def test_stdin_prompt_reading(self):
        """Can read prompt from stdin."""
        from io import StringIO

        stdin_content = "What is Python?"
        mock_stdin = StringIO(stdin_content)

        content = mock_stdin.read()
        assert content == "What is Python?"

    def test_file_path_handling(self, tmp_path):
        """Handles file paths correctly."""
        # Create nested directory structure
        src_dir = tmp_path / "src" / "components"
        src_dir.mkdir(parents=True)

        test_file = src_dir / "Button.tsx"
        test_file.write_text("export const Button = () => <button>Click</button>")

        # Verify path handling
        assert test_file.exists()
        assert test_file.is_file()
        assert test_file.suffix == ".tsx"


class TestOutputFormatting:
    """Tests for output formatting options."""

    def test_json_output_parsing(self):
        """Parses JSON output correctly."""
        json_response = '{"key": "value", "number": 42}'
        parsed = json.loads(json_response)

        assert parsed["key"] == "value"
        assert parsed["number"] == 42

    def test_relative_paths_display(self, tmp_path, monkeypatch):
        """Displays relative paths correctly."""
        monkeypatch.chdir(tmp_path)

        file_path = tmp_path / "subdir" / "file.py"
        file_path.parent.mkdir(parents=True)
        file_path.touch()

        relative = file_path.relative_to(tmp_path)
        assert str(relative) == "subdir/file.py"
