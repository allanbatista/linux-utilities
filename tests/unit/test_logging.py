"""Unit tests for ab_cli.utils.logging module."""


class TestLogFunctions:
    """Tests for logging functions."""

    def test_log_info(self, capsys):
        """log_info prints info message with blue prefix."""
        from ab_cli.utils.logging import log_info, BLUE, NC

        log_info("Test message")
        captured = capsys.readouterr()
        assert "Test message" in captured.out
        assert "[INFO]" in captured.out
        assert BLUE in captured.out
        assert NC in captured.out

    def test_log_success(self, capsys):
        """log_success prints success message with green prefix."""
        from ab_cli.utils.logging import log_success, GREEN, NC

        log_success("Success message")
        captured = capsys.readouterr()
        assert "Success message" in captured.out
        assert "[SUCCESS]" in captured.out
        assert GREEN in captured.out
        assert NC in captured.out

    def test_log_warning(self, capsys):
        """log_warning prints warning message with yellow prefix."""
        from ab_cli.utils.logging import log_warning, YELLOW, NC

        log_warning("Warning message")
        captured = capsys.readouterr()
        assert "Warning message" in captured.out
        assert "[WARNING]" in captured.out
        assert YELLOW in captured.out
        assert NC in captured.out

    def test_log_error(self, capsys):
        """log_error prints error message to stderr with red prefix."""
        from ab_cli.utils.logging import log_error, RED, NC

        log_error("Error message")
        captured = capsys.readouterr()
        assert "Error message" in captured.err
        assert "[ERROR]" in captured.err
        assert RED in captured.err
        assert NC in captured.err

    def test_log_debug(self, capsys):
        """log_debug prints debug message with cyan prefix."""
        from ab_cli.utils.logging import log_debug, CYAN, NC

        log_debug("Debug message")
        captured = capsys.readouterr()
        assert "Debug message" in captured.out
        assert "[DEBUG]" in captured.out
        assert CYAN in captured.out
        assert NC in captured.out


class TestColorConstants:
    """Tests for color constants."""

    def test_color_constants_are_strings(self):
        """All color constants are non-empty strings."""
        from ab_cli.utils.logging import RED, GREEN, YELLOW, BLUE, CYAN, NC

        for color in [RED, GREEN, YELLOW, BLUE, CYAN, NC]:
            assert isinstance(color, str)
            assert len(color) > 0

    def test_color_constants_are_ansi_codes(self):
        """Color constants are valid ANSI escape codes."""
        from ab_cli.utils.logging import RED, GREEN, YELLOW, BLUE, CYAN, NC

        for color in [RED, GREEN, YELLOW, BLUE, CYAN, NC]:
            assert color.startswith('\033[')


class TestUtilsModuleExports:
    """Tests for utils module exports."""

    def test_logging_functions_exported_from_utils(self):
        """Logging functions are exported from utils module."""
        from ab_cli.utils import log_info, log_success, log_warning, log_error, log_debug

        assert callable(log_info)
        assert callable(log_success)
        assert callable(log_warning)
        assert callable(log_error)
        assert callable(log_debug)

    def test_color_constants_exported_from_utils(self):
        """Color constants are exported from utils module."""
        from ab_cli.utils import RED, GREEN, YELLOW, BLUE, CYAN, NC

        assert isinstance(RED, str)
        assert isinstance(GREEN, str)
        assert isinstance(YELLOW, str)
        assert isinstance(BLUE, str)
        assert isinstance(CYAN, str)
        assert isinstance(NC, str)
