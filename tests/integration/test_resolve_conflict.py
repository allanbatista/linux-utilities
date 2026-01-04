"""Integration tests for ab_cli.commands.resolve_conflict module."""
import subprocess
import sys
from unittest.mock import patch

import pytest

from ab_cli.commands.resolve_conflict import (
    apply_resolution,
    get_conflicted_files,
    get_file_context,
    has_conflict_markers,
    is_git_repo,
    main,
    parse_conflicts,
)


class TestIsGitRepo:
    """Tests for is_git_repo function."""

    def test_is_git_repo_true(self, mock_git_repo, monkeypatch):
        """Returns True inside git repository."""
        monkeypatch.chdir(mock_git_repo)
        assert is_git_repo() is True

    def test_is_git_repo_false(self, tmp_path, monkeypatch):
        """Returns False outside git repository."""
        monkeypatch.chdir(tmp_path)
        assert is_git_repo() is False


class TestGetConflictedFiles:
    """Tests for get_conflicted_files function."""

    def test_get_conflicted_files_none(self, mock_git_repo, monkeypatch):
        """Returns empty list when no conflicts."""
        monkeypatch.chdir(mock_git_repo)
        result = get_conflicted_files()
        assert result == []

    def test_get_conflicted_files_with_conflict(self, mock_git_repo, monkeypatch):
        """Returns list of conflicted files."""
        monkeypatch.chdir(mock_git_repo)

        # Create a conflict scenario
        # Create a branch and modify a file
        subprocess.run(['git', 'checkout', '-b', 'feature'], cwd=mock_git_repo, check=True)
        (mock_git_repo / 'test.txt').write_text('feature content\n')
        subprocess.run(['git', 'add', '.'], cwd=mock_git_repo, check=True)
        subprocess.run(['git', 'commit', '-m', 'feature change'], cwd=mock_git_repo, check=True)

        # Go back to master and make conflicting change
        subprocess.run(['git', 'checkout', 'master'], cwd=mock_git_repo, check=True)
        (mock_git_repo / 'test.txt').write_text('master content\n')
        subprocess.run(['git', 'add', '.'], cwd=mock_git_repo, check=True)
        subprocess.run(['git', 'commit', '-m', 'master change'], cwd=mock_git_repo, check=True)

        # Try to merge (will conflict)
        subprocess.run(['git', 'merge', 'feature'], cwd=mock_git_repo, check=False)

        result = get_conflicted_files()
        assert 'test.txt' in result


class TestHasConflictMarkers:
    """Tests for has_conflict_markers function."""

    def test_has_conflict_markers_true(self):
        """Returns True when conflict markers present."""
        content = '''some code
<<<<<<< HEAD
master version
=======
feature version
>>>>>>> feature
more code'''
        assert has_conflict_markers(content) is True

    def test_has_conflict_markers_false(self):
        """Returns False when no conflict markers."""
        content = '''normal code
without any conflict markers
just regular content'''
        assert has_conflict_markers(content) is False

    def test_has_conflict_markers_partial(self):
        """Returns False when only partial markers."""
        # Only has <<<<<<< but not ======= and >>>>>>>
        content = '''<<<<<<< HEAD
some content'''
        assert has_conflict_markers(content) is False


class TestParseConflicts:
    """Tests for parse_conflicts function."""

    def test_parse_conflicts_single(self):
        """Parses single conflict correctly."""
        content = '''line1
<<<<<<< HEAD
master version
=======
feature version
>>>>>>> feature
line2'''
        conflicts = parse_conflicts(content)

        assert len(conflicts) == 1
        assert conflicts[0]['ours'] == ['master version']
        assert conflicts[0]['theirs'] == ['feature version']

    def test_parse_conflicts_multiple(self):
        """Parses multiple conflicts correctly."""
        content = '''line1
<<<<<<< HEAD
master 1
=======
feature 1
>>>>>>> feature
line2
<<<<<<< HEAD
master 2
=======
feature 2
>>>>>>> feature
line3'''
        conflicts = parse_conflicts(content)

        assert len(conflicts) == 2
        assert conflicts[0]['ours'] == ['master 1']
        assert conflicts[1]['ours'] == ['master 2']

    def test_parse_conflicts_multiline(self):
        """Parses multi-line conflict sections."""
        content = '''<<<<<<< HEAD
line1
line2
line3
=======
alt1
alt2
>>>>>>> feature'''
        conflicts = parse_conflicts(content)

        assert len(conflicts) == 1
        assert conflicts[0]['ours'] == ['line1', 'line2', 'line3']
        assert conflicts[0]['theirs'] == ['alt1', 'alt2']

    def test_parse_conflicts_empty(self):
        """Returns empty list for no conflicts."""
        content = 'normal content without conflicts'
        conflicts = parse_conflicts(content)
        assert conflicts == []


class TestGetFileContext:
    """Tests for get_file_context function."""

    def test_get_file_context_basic(self, tmp_path):
        """Returns context around conflict."""
        test_file = tmp_path / 'test.txt'
        lines = [f'line{i}\n' for i in range(1, 31)]
        test_file.write_text(''.join(lines))

        conflict = {
            'start_line': 15,
            'end_line': 17,
        }

        before, after = get_file_context(str(test_file), conflict, context_lines=5)

        # Should have lines before the conflict
        assert 'line10' in before or 'line11' in before
        # Should have lines after the conflict
        assert 'line18' in after or 'line19' in after

    def test_get_file_context_nonexistent(self):
        """Returns empty strings for nonexistent file."""
        conflict = {'start_line': 5, 'end_line': 10}
        before, after = get_file_context('/nonexistent/file.txt', conflict)
        assert before == ''
        assert after == ''


class TestApplyResolution:
    """Tests for apply_resolution function."""

    def test_apply_resolution_success(self, tmp_path):
        """Applies resolution to file successfully."""
        test_file = tmp_path / 'test.txt'
        test_file.write_text('''line1
<<<<<<< HEAD
master
=======
feature
>>>>>>> feature
line2
''')

        conflict = {
            'start_line': 2,
            'end_line': 6,
        }

        result = apply_resolution(str(test_file), conflict, 'merged content')
        assert result is True

        # Verify file content
        content = test_file.read_text()
        assert 'merged content' in content
        assert '<<<<<<<' not in content
        assert 'line1' in content
        assert 'line2' in content

    def test_apply_resolution_nonexistent_fails(self, tmp_path, capsys):
        """Returns False for nonexistent file."""
        conflict = {'start_line': 1, 'end_line': 5}
        result = apply_resolution(str(tmp_path / 'nonexistent.txt'), conflict, 'content')
        assert result is False


class TestMain:
    """Tests for main() entry point."""

    def test_main_not_git_repo_exits_1(self, tmp_path, monkeypatch, capsys):
        """Exits with error when not in git repo."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['resolve-conflict'])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert 'not inside a git repository' in captured.err.lower()

    def test_main_no_conflicts_exits_0(self, mock_git_repo, monkeypatch, capsys, mock_config):
        """Exits cleanly when no conflicts."""
        monkeypatch.chdir(mock_git_repo)
        monkeypatch.setattr(sys, 'argv', ['resolve-conflict'])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert 'no conflicted files' in captured.out.lower()

    def test_main_dry_run_flag_accepted(self, mock_git_repo, monkeypatch, capsys, mock_config):
        """Accepts --dry-run flag."""
        monkeypatch.chdir(mock_git_repo)
        monkeypatch.setattr(sys, 'argv', ['resolve-conflict', '--dry-run'])

        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should exit 0 (no conflicts to process)
        assert exc_info.value.code == 0

    def test_main_yes_flag_accepted(self, mock_git_repo, monkeypatch, capsys, mock_config):
        """Accepts -y flag."""
        monkeypatch.chdir(mock_git_repo)
        monkeypatch.setattr(sys, 'argv', ['resolve-conflict', '-y'])

        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should exit 0 (no conflicts to process)
        assert exc_info.value.code == 0

    def test_main_specific_file(self, mock_git_repo, monkeypatch, capsys, mock_config):
        """Accepts specific file argument."""
        monkeypatch.chdir(mock_git_repo)

        # Create a file with conflict markers
        conflict_file = mock_git_repo / 'conflict.txt'
        conflict_file.write_text('''<<<<<<< HEAD
master
=======
feature
>>>>>>> feature
''')

        monkeypatch.setattr(sys, 'argv', ['resolve-conflict', str(conflict_file)])

        with patch('ab_cli.commands.resolve_conflict.find_prompt_command') as mock_find:
            mock_find.side_effect = FileNotFoundError('abort')

            with pytest.raises(SystemExit):
                main()

        # If we got here without argument error, the argument was accepted

    def test_main_file_not_found_exits_1(self, mock_git_repo, monkeypatch, capsys, mock_config):
        """Exits with error when specified file not found."""
        monkeypatch.chdir(mock_git_repo)
        monkeypatch.setattr(sys, 'argv', ['resolve-conflict', 'nonexistent.txt'])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert 'not found' in captured.err.lower()

    def test_main_processes_conflict(self, mock_git_repo, monkeypatch, capsys, mock_config):
        """Processes conflict file and calls resolve_conflict."""
        monkeypatch.chdir(mock_git_repo)

        # Create a file with conflict markers
        conflict_file = mock_git_repo / 'conflict.txt'
        conflict_file.write_text('''<<<<<<< HEAD
master
=======
feature
>>>>>>> feature
''')

        monkeypatch.setattr(sys, 'argv', ['resolve-conflict', '--dry-run', str(conflict_file)])

        with patch('ab_cli.commands.resolve_conflict.resolve_conflict') as mock_resolve:
            mock_resolve.return_value = 'merged content'

            try:
                main()
            except SystemExit:
                pass

            # Verify resolve_conflict was called
            assert mock_resolve.called
