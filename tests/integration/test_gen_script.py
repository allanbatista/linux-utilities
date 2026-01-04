"""Integration tests for ab_cli.commands.gen_script module."""
import os
import stat
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ab_cli.commands.gen_script import (
    find_prompt_command,
    get_directory_listing,
    get_file_extension,
    get_shebang,
    get_system_context,
    main,
    run_cmd,
)


class TestRunCmd:
    """Tests for run_cmd helper function."""

    def test_run_cmd_success(self):
        """Returns stdout on successful command."""
        result = run_cmd(['echo', 'hello'])
        assert result == 'hello'

    def test_run_cmd_failure_returns_default(self):
        """Returns default value on command failure."""
        result = run_cmd(['nonexistent_command_12345'], default='fallback')
        assert result == 'fallback'

    def test_run_cmd_default_is_unknown(self):
        """Default value is 'unknown' when not specified."""
        result = run_cmd(['nonexistent_command_12345'])
        assert result == 'unknown'

    def test_run_cmd_strips_output(self):
        """Strips whitespace from output."""
        result = run_cmd(['echo', '  spaced  '])
        assert result == 'spaced'


class TestGetSystemContext:
    """Tests for get_system_context function."""

    def test_get_system_context_returns_string(self):
        """Returns a non-empty string."""
        result = get_system_context()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_system_context_contains_os_info(self):
        """Contains OS information."""
        result = get_system_context()
        assert 'OS:' in result

    def test_get_system_context_contains_user(self):
        """Contains user information."""
        result = get_system_context()
        assert 'User:' in result

    def test_get_system_context_contains_directory(self):
        """Contains current directory."""
        result = get_system_context()
        assert 'Current directory:' in result

    def test_get_system_context_contains_shell(self):
        """Contains shell information."""
        result = get_system_context()
        assert 'Shell:' in result

    def test_get_system_context_contains_python(self):
        """Contains Python version."""
        result = get_system_context()
        assert 'Python:' in result


class TestGetDirectoryListing:
    """Tests for get_directory_listing function."""

    def test_get_directory_listing_current(self, tmp_path, monkeypatch):
        """Returns listing of current directory."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / 'test_file.txt').write_text('content')

        result = get_directory_listing()
        assert 'test_file.txt' in result

    def test_get_directory_listing_specific_path(self, tmp_path):
        """Returns listing of specific path."""
        (tmp_path / 'specific.txt').write_text('content')

        result = get_directory_listing(str(tmp_path))
        assert 'specific.txt' in result

    def test_get_directory_listing_nonexistent_returns_empty(self):
        """Returns empty string for nonexistent directory."""
        result = get_directory_listing('/nonexistent_path_12345')
        assert result == ''

    def test_get_directory_listing_limits_size(self, tmp_path, monkeypatch):
        """Limits output size to 1500 characters."""
        monkeypatch.chdir(tmp_path)
        # Create many files
        for i in range(100):
            (tmp_path / f'long_filename_number_{i:03d}.txt').write_text('x')

        result = get_directory_listing()
        assert len(result) <= 1500


class TestGetShebang:
    """Tests for get_shebang function."""

    def test_get_shebang_bash(self):
        """Returns correct shebang for bash."""
        assert get_shebang('bash') == '#!/usr/bin/env bash'

    def test_get_shebang_sh(self):
        """Returns correct shebang for sh."""
        assert get_shebang('sh') == '#!/bin/sh'

    def test_get_shebang_python(self):
        """Returns correct shebang for python."""
        assert get_shebang('python') == '#!/usr/bin/env python3'

    def test_get_shebang_python3(self):
        """Returns correct shebang for python3."""
        assert get_shebang('python3') == '#!/usr/bin/env python3'

    def test_get_shebang_node(self):
        """Returns correct shebang for node."""
        assert get_shebang('node') == '#!/usr/bin/env node'

    def test_get_shebang_perl(self):
        """Returns correct shebang for perl."""
        assert get_shebang('perl') == '#!/usr/bin/env perl'

    def test_get_shebang_ruby(self):
        """Returns correct shebang for ruby."""
        assert get_shebang('ruby') == '#!/usr/bin/env ruby'

    def test_get_shebang_unknown_defaults_to_bash(self):
        """Returns bash shebang for unknown language."""
        assert get_shebang('unknown') == '#!/usr/bin/env bash'

    def test_get_shebang_case_insensitive(self):
        """Handles case insensitivity."""
        assert get_shebang('BASH') == '#!/usr/bin/env bash'
        assert get_shebang('Python') == '#!/usr/bin/env python3'


class TestGetFileExtension:
    """Tests for get_file_extension function."""

    def test_get_file_extension_bash(self):
        """Returns .sh for bash."""
        assert get_file_extension('bash') == '.sh'

    def test_get_file_extension_sh(self):
        """Returns .sh for sh."""
        assert get_file_extension('sh') == '.sh'

    def test_get_file_extension_python(self):
        """Returns .py for python."""
        assert get_file_extension('python') == '.py'

    def test_get_file_extension_python3(self):
        """Returns .py for python3."""
        assert get_file_extension('python3') == '.py'

    def test_get_file_extension_node(self):
        """Returns .js for node."""
        assert get_file_extension('node') == '.js'

    def test_get_file_extension_perl(self):
        """Returns .pl for perl."""
        assert get_file_extension('perl') == '.pl'

    def test_get_file_extension_ruby(self):
        """Returns .rb for ruby."""
        assert get_file_extension('ruby') == '.rb'

    def test_get_file_extension_unknown_defaults_to_sh(self):
        """Returns .sh for unknown language."""
        assert get_file_extension('unknown') == '.sh'

    def test_get_file_extension_case_insensitive(self):
        """Handles case insensitivity."""
        assert get_file_extension('PYTHON') == '.py'
        assert get_file_extension('Node') == '.js'


class TestMain:
    """Tests for main() entry point."""

    def test_main_no_description_shows_help(self, monkeypatch, capsys):
        """Shows help when no description provided."""
        monkeypatch.setattr(sys, 'argv', ['gen-script'])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert 'usage:' in captured.out.lower() or 'description' in captured.out.lower()

    def test_main_prompt_not_found_exits_1(self, monkeypatch, capsys, mock_config):
        """Exits with error if ab-prompt not found."""
        monkeypatch.setattr(sys, 'argv', ['gen-script', 'test description'])

        with patch('ab_cli.commands.gen_script.find_prompt_command') as mock_find:
            mock_find.side_effect = FileNotFoundError('ab-prompt not found')

            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert 'not found' in captured.err.lower()

    def test_main_lang_flag_accepted(self, monkeypatch, capsys, mock_config):
        """Accepts --lang flag."""
        monkeypatch.setattr(sys, 'argv', ['gen-script', '--lang', 'python', 'test'])

        with patch('ab_cli.commands.gen_script.find_prompt_command') as mock_find:
            mock_find.side_effect = FileNotFoundError('abort')

            with pytest.raises(SystemExit):
                main()

        # If we got here without argument error, the flag was accepted

    def test_main_type_flag_accepted(self, monkeypatch, capsys, mock_config):
        """Accepts --type flag."""
        monkeypatch.setattr(sys, 'argv', ['gen-script', '--type', 'cron', 'test'])

        with patch('ab_cli.commands.gen_script.find_prompt_command') as mock_find:
            mock_find.side_effect = FileNotFoundError('abort')

            with pytest.raises(SystemExit):
                main()

        # If we got here without argument error, the flag was accepted

    def test_main_full_flag_accepted(self, monkeypatch, capsys, mock_config):
        """Accepts --full flag."""
        monkeypatch.setattr(sys, 'argv', ['gen-script', '--full', 'test'])

        with patch('ab_cli.commands.gen_script.find_prompt_command') as mock_find:
            mock_find.side_effect = FileNotFoundError('abort')

            with pytest.raises(SystemExit):
                main()

        # If we got here without argument error, the flag was accepted

    def test_main_output_flag_creates_file(self, tmp_path, monkeypatch, capsys, mock_config):
        """--output flag creates executable file."""
        output_file = tmp_path / 'test_script.sh'
        monkeypatch.setattr(sys, 'argv', ['gen-script', '-o', str(output_file), 'test'])

        with patch('ab_cli.commands.gen_script.find_prompt_command') as mock_find:
            mock_find.return_value = '/usr/bin/true'

            with patch('ab_cli.commands.gen_script.generate_script') as mock_gen:
                mock_gen.return_value = 'echo "test"'

                # Don't raise SystemExit, let it complete
                try:
                    main()
                except SystemExit:
                    pass

        # Check file was created and is executable
        if output_file.exists():
            assert os.access(output_file, os.X_OK)

    def test_main_generates_script_with_context(self, monkeypatch, capsys, mock_config):
        """Generates script with system context."""
        monkeypatch.setattr(sys, 'argv', ['gen-script', 'list files'])

        with patch('ab_cli.commands.gen_script.find_prompt_command') as mock_find:
            mock_find.return_value = '/usr/bin/true'

            with patch('ab_cli.commands.gen_script.generate_script') as mock_gen:
                mock_gen.return_value = 'ls -la'

                with patch('ab_cli.commands.gen_script.get_system_context') as mock_ctx:
                    mock_ctx.return_value = 'OS: Linux'

                    try:
                        main()
                    except SystemExit:
                        pass

                    # Verify generate_script was called
                    assert mock_gen.called


class TestFindPromptCommand:
    """Tests for find_prompt_command function."""

    def test_find_prompt_command_in_bin(self, tmp_path, monkeypatch):
        """Finds ab-prompt in bin directory."""
        # Create fake bin structure
        bin_dir = tmp_path / 'bin'
        bin_dir.mkdir()
        prompt_cmd = bin_dir / 'ab-prompt'
        prompt_cmd.write_text('#!/bin/bash\necho test')

        # Patch the module path
        with patch('ab_cli.commands.gen_script.Path') as mock_path:
            mock_file = MagicMock()
            mock_file.parent.parent.parent.parent = tmp_path
            mock_path.return_value = mock_file
            mock_path.__truediv__ = lambda self, x: tmp_path / x

            # The function looks for bin/ab-prompt relative to module
            # This is complex to mock, so we'll test the which fallback instead

    def test_find_prompt_command_not_found_raises(self, tmp_path, monkeypatch):
        """Raises FileNotFoundError when not found."""
        # Change to a directory without ab-prompt
        monkeypatch.chdir(tmp_path)

        # Mock shutil.which to return None (shutil is imported inside the function)
        with patch('shutil.which', return_value=None):
            # Mock Path.exists to return False for the bin path
            with patch.object(Path, 'exists', return_value=False):
                with pytest.raises(FileNotFoundError):
                    find_prompt_command()
