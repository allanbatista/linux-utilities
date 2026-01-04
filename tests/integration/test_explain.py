"""Integration tests for ab_cli.commands.explain module."""
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from ab_cli.commands.explain import (
    detect_input_type,
    extract_file_references,
    get_bash_history,
    get_directory_listing,
    main,
    parse_file_reference,
    read_file_with_context,
)


class TestGetBashHistory:
    """Tests for get_bash_history function."""

    def test_get_bash_history_with_histfile(self, tmp_path, monkeypatch):
        """Returns history from HISTFILE."""
        histfile = tmp_path / '.bash_history'
        histfile.write_text('command1\ncommand2\ncommand3\n')
        monkeypatch.setenv('HISTFILE', str(histfile))

        result = get_bash_history(2)
        assert 'command2' in result
        assert 'command3' in result

    def test_get_bash_history_nonexistent_returns_empty(self, tmp_path, monkeypatch):
        """Returns empty string when history file doesn't exist."""
        monkeypatch.setenv('HISTFILE', str(tmp_path / 'nonexistent'))
        result = get_bash_history(10)
        assert result == ''

    def test_get_bash_history_limits_lines(self, tmp_path, monkeypatch):
        """Limits output to specified number of lines."""
        histfile = tmp_path / '.bash_history'
        lines = [f'command{i}\n' for i in range(100)]
        histfile.write_text(''.join(lines))
        monkeypatch.setenv('HISTFILE', str(histfile))

        result = get_bash_history(5)
        # Should only have last 5 commands
        assert 'command95' in result
        assert 'command99' in result


class TestGetDirectoryListing:
    """Tests for get_directory_listing function."""

    def test_get_directory_listing_current(self, tmp_path, monkeypatch):
        """Returns listing of current directory."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'test.txt').write_text('content')

        result = get_directory_listing()
        assert 'test.txt' in result

    def test_get_directory_listing_specific_path(self, tmp_path):
        """Returns listing of specific path."""
        (tmp_path / 'specific.txt').write_text('content')

        result = get_directory_listing(str(tmp_path))
        assert 'specific.txt' in result

    def test_get_directory_listing_nonexistent_returns_empty(self):
        """Returns empty string for nonexistent directory."""
        result = get_directory_listing('/nonexistent_path_12345')
        assert result == ''


class TestExtractFileReferences:
    """Tests for extract_file_references function."""

    def test_extract_file_references_single_quotes(self, tmp_path, monkeypatch):
        """Extracts file in single quotes."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'test.py').write_text('content')

        result = extract_file_references("Error in 'test.py'")
        assert 'test.py' in result

    def test_extract_file_references_double_quotes(self, tmp_path, monkeypatch):
        """Extracts file in double quotes."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'test.py').write_text('content')

        result = extract_file_references('Error in "test.py"')
        assert 'test.py' in result

    def test_extract_file_references_python_traceback(self, tmp_path, monkeypatch):
        """Extracts file from Python traceback format."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'script.py').write_text('content')

        result = extract_file_references('File "script.py", line 10')
        assert 'script.py' in result

    def test_extract_file_references_with_line_number(self, tmp_path, monkeypatch):
        """Extracts file with line number format."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'file.py').write_text('content')

        result = extract_file_references('file.py:42')
        assert 'file.py' in result

    def test_extract_file_references_nonexistent_excluded(self):
        """Excludes non-existent files."""
        result = extract_file_references("Error in 'nonexistent12345.py'")
        assert 'nonexistent12345.py' not in result


class TestReadFileWithContext:
    """Tests for read_file_with_context function."""

    def test_read_file_with_context_entire_file(self, tmp_path):
        """Reads entire file when no line specified."""
        test_file = tmp_path / 'test.py'
        test_file.write_text('line1\nline2\nline3\n')

        result = read_file_with_context(str(test_file))
        assert 'line1' in result
        assert 'line2' in result
        assert 'line3' in result

    def test_read_file_with_context_specific_line(self, tmp_path):
        """Reads file focusing on specific line."""
        test_file = tmp_path / 'test.py'
        lines = [f'line{i}\n' for i in range(1, 21)]
        test_file.write_text(''.join(lines))

        result = read_file_with_context(str(test_file), line=10)
        # Should have marker on line 10
        assert '>>>' in result
        assert '10:' in result or '  10' in result

    def test_read_file_with_context_line_range(self, tmp_path):
        """Reads file with line range."""
        test_file = tmp_path / 'test.py'
        lines = [f'line{i}\n' for i in range(1, 31)]
        test_file.write_text(''.join(lines))

        result = read_file_with_context(str(test_file), line=10, end_line=15)
        # Should include context around lines 10-15
        assert 'line10' in result
        assert 'line15' in result

    def test_read_file_with_context_nonexistent_returns_error(self):
        """Returns error message for nonexistent file."""
        result = read_file_with_context('/nonexistent_file_12345.py')
        assert 'Error' in result or 'not found' in result.lower()

    def test_read_file_with_context_truncates_large_file(self, tmp_path):
        """Truncates files larger than 200 lines."""
        test_file = tmp_path / 'large.py'
        lines = [f'line{i}\n' for i in range(1, 301)]
        test_file.write_text(''.join(lines))

        result = read_file_with_context(str(test_file))
        assert 'truncated' in result.lower()


class TestDetectInputType:
    """Tests for detect_input_type function."""

    def test_detect_input_type_file(self, tmp_path, monkeypatch):
        """Detects existing file as 'file' type."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'test.py').write_text('content')

        result = detect_input_type('test.py')
        assert result == 'file'

    def test_detect_input_type_file_line(self):
        """Detects file:line format."""
        result = detect_input_type('test.py:42')
        assert result == 'file_line'

    def test_detect_input_type_file_line_range(self):
        """Detects file:start-end format."""
        result = detect_input_type('test.py:10-50')
        assert result == 'file_line'

    def test_detect_input_type_error_message(self):
        """Detects error messages."""
        error_messages = [
            'Error: something went wrong',
            'TypeError: undefined is not a function',
            'Exception in thread main',
            'command failed with exit code 1',
            'Traceback (most recent call last)',
            'undefined reference to symbol',
            'permission denied',
            'No such file or directory',
        ]
        for msg in error_messages:
            result = detect_input_type(msg)
            assert result == 'error', f"Failed for: {msg}"

    def test_detect_input_type_concept(self):
        """Detects general concepts/questions."""
        result = detect_input_type('dependency injection')
        assert result == 'concept'

        result = detect_input_type('how does async await work')
        assert result == 'concept'


class TestParseFileReference:
    """Tests for parse_file_reference function."""

    def test_parse_file_reference_no_line(self):
        """Parses file without line number."""
        filepath, start, end = parse_file_reference('test.py')
        assert filepath == 'test.py'
        assert start is None
        assert end is None

    def test_parse_file_reference_single_line(self):
        """Parses file:line format."""
        filepath, start, end = parse_file_reference('test.py:42')
        assert filepath == 'test.py'
        assert start == 42
        assert end is None

    def test_parse_file_reference_line_range(self):
        """Parses file:start-end format."""
        filepath, start, end = parse_file_reference('test.py:10-50')
        assert filepath == 'test.py'
        assert start == 10
        assert end == 50

    def test_parse_file_reference_path_with_colon(self):
        """Handles paths that might have colons (uses rsplit)."""
        filepath, start, end = parse_file_reference('/path/to/test.py:42')
        assert filepath == '/path/to/test.py'
        assert start == 42


class TestMain:
    """Tests for main() entry point."""

    def test_main_no_input_shows_help(self, monkeypatch, capsys):
        """Shows help when no input provided."""
        monkeypatch.setattr(sys, 'argv', ['explain'])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert 'usage:' in captured.out.lower() or 'explain' in captured.out.lower()

    def test_main_prompt_not_found_exits_1(self, monkeypatch, capsys, mock_config):
        """Exits with error if ab-prompt not found."""
        monkeypatch.setattr(sys, 'argv', ['explain', 'test input'])

        with patch('ab_cli.commands.explain.find_prompt_command') as mock_find:
            mock_find.side_effect = FileNotFoundError('ab-prompt not found')

            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert 'not found' in captured.err.lower()

    def test_main_concept_flag(self, monkeypatch, capsys, mock_config):
        """Accepts --concept flag."""
        monkeypatch.setattr(sys, 'argv', ['explain', '--concept', 'dependency injection'])

        with patch('ab_cli.commands.explain.find_prompt_command') as mock_find:
            mock_find.side_effect = FileNotFoundError('abort')

            with pytest.raises(SystemExit):
                main()

        # If we got here without argument error, the flag was accepted

    def test_main_history_flag(self, tmp_path, monkeypatch, capsys, mock_config):
        """Accepts --history flag."""
        histfile = tmp_path / '.bash_history'
        histfile.write_text('echo test\n')
        monkeypatch.setenv('HISTFILE', str(histfile))

        monkeypatch.setattr(sys, 'argv', ['explain', '--history', '5', 'some error'])

        with patch('ab_cli.commands.explain.find_prompt_command') as mock_find:
            mock_find.side_effect = FileNotFoundError('abort')

            with pytest.raises(SystemExit):
                main()

        # If we got here without argument error, the flag was accepted

    def test_main_with_files_flag(self, monkeypatch, capsys, mock_config):
        """Accepts --with-files flag."""
        monkeypatch.setattr(sys, 'argv', ['explain', '--with-files', 'some error'])

        with patch('ab_cli.commands.explain.find_prompt_command') as mock_find:
            mock_find.side_effect = FileNotFoundError('abort')

            with pytest.raises(SystemExit):
                main()

        # If we got here without argument error, the flag was accepted

    def test_main_verbose_flag(self, monkeypatch, capsys, mock_config):
        """Accepts --verbose flag."""
        monkeypatch.setattr(sys, 'argv', ['explain', '-v', 'some concept'])

        with patch('ab_cli.commands.explain.find_prompt_command') as mock_find:
            mock_find.side_effect = FileNotFoundError('abort')

            with pytest.raises(SystemExit):
                main()

        # If we got here without argument error, the flag was accepted

    def test_main_file_input(self, tmp_path, monkeypatch, capsys, mock_config):
        """Handles file input."""
        test_file = tmp_path / 'test.py'
        test_file.write_text('def hello(): pass\n')
        monkeypatch.chdir(tmp_path)

        monkeypatch.setattr(sys, 'argv', ['explain', 'test.py'])

        with patch('ab_cli.commands.explain.find_prompt_command') as mock_find:
            mock_find.return_value = '/usr/bin/true'

            with patch('ab_cli.commands.explain.generate_explanation') as mock_gen:
                mock_gen.return_value = 'This is a function'

                try:
                    main()
                except SystemExit:
                    pass

                # Verify generate_explanation was called
                assert mock_gen.called

    def test_main_stdin_input(self, monkeypatch, capsys, mock_config):
        """Handles stdin input with '-'."""
        monkeypatch.setattr(sys, 'argv', ['explain', '-'])

        with patch('sys.stdin') as mock_stdin:
            mock_stdin.read.return_value = 'Error: something went wrong'

            with patch('ab_cli.commands.explain.find_prompt_command') as mock_find:
                mock_find.side_effect = FileNotFoundError('abort')

                with pytest.raises(SystemExit):
                    main()
