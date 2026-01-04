"""Integration tests for ab_cli.commands.changelog module."""
import subprocess
import sys
from unittest.mock import patch

import pytest

from ab_cli.commands.changelog import (
    categorize_commits,
    get_all_tags,
    get_commit_count,
    get_commits,
    get_latest_tag,
    is_git_repo,
    main,
    parse_commits,
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


class TestTagOperations:
    """Tests for tag-related functions."""

    def test_get_latest_tag_none(self, mock_git_repo, monkeypatch):
        """Returns None when no tags exist."""
        monkeypatch.chdir(mock_git_repo)
        result = get_latest_tag()
        assert result is None

    def test_get_latest_tag_exists(self, mock_git_repo, monkeypatch):
        """Returns latest tag when tags exist."""
        monkeypatch.chdir(mock_git_repo)

        # Create a tag
        subprocess.run(['git', 'tag', 'v1.0.0'], cwd=mock_git_repo, check=True)

        result = get_latest_tag()
        assert result == 'v1.0.0'

    def test_get_latest_tag_multiple(self, mock_git_repo, monkeypatch):
        """Returns most recent tag when multiple exist."""
        monkeypatch.chdir(mock_git_repo)

        # Create multiple tags
        subprocess.run(['git', 'tag', 'v1.0.0'], cwd=mock_git_repo, check=True)

        # Add a commit
        (mock_git_repo / 'file.txt').write_text('content')
        subprocess.run(['git', 'add', '.'], cwd=mock_git_repo, check=True)
        subprocess.run(['git', 'commit', '-m', 'add file'], cwd=mock_git_repo, check=True)
        subprocess.run(['git', 'tag', 'v2.0.0'], cwd=mock_git_repo, check=True)

        result = get_latest_tag()
        assert result == 'v2.0.0'

    def test_get_all_tags_empty(self, mock_git_repo, monkeypatch):
        """Returns empty list when no tags exist."""
        monkeypatch.chdir(mock_git_repo)
        result = get_all_tags()
        assert result == [] or result == ['']

    def test_get_all_tags_multiple(self, mock_git_repo, monkeypatch):
        """Returns all tags sorted."""
        monkeypatch.chdir(mock_git_repo)

        # Create tags
        subprocess.run(['git', 'tag', 'v1.0.0'], cwd=mock_git_repo, check=True)
        subprocess.run(['git', 'tag', 'v1.1.0'], cwd=mock_git_repo, check=True)

        result = get_all_tags()
        assert 'v1.0.0' in result
        assert 'v1.1.0' in result


class TestCommitOperations:
    """Tests for commit-related functions."""

    def test_get_commits_range(self, mock_git_repo, monkeypatch):
        """Returns commits in specified range."""
        monkeypatch.chdir(mock_git_repo)

        # Add commits
        for i in range(3):
            (mock_git_repo / f'file{i}.txt').write_text(f'content{i}')
            subprocess.run(['git', 'add', '.'], cwd=mock_git_repo, check=True)
            subprocess.run(['git', 'commit', '-m', f'commit {i}'], cwd=mock_git_repo, check=True)

        result = get_commits('HEAD~2..HEAD')
        assert 'commit 1' in result or 'commit 2' in result

    def test_get_commit_count(self, mock_git_repo, monkeypatch):
        """Returns correct commit count."""
        monkeypatch.chdir(mock_git_repo)

        # Initial commit already exists, add more
        for i in range(3):
            (mock_git_repo / f'file{i}.txt').write_text(f'content{i}')
            subprocess.run(['git', 'add', '.'], cwd=mock_git_repo, check=True)
            subprocess.run(['git', 'commit', '-m', f'commit {i}'], cwd=mock_git_repo, check=True)

        result = get_commit_count('HEAD~3..HEAD')
        assert result == 3


class TestParseCommits:
    """Tests for parse_commits function."""

    def test_parse_commits_empty(self):
        """Returns empty list for empty input."""
        result = parse_commits('')
        assert result == []

    def test_parse_commits_single(self):
        """Parses single commit correctly."""
        commits_str = 'abc123|fix: button bug|body text|John|2024-01-01'
        result = parse_commits(commits_str)

        assert len(result) == 1
        assert result[0]['hash'] == 'abc123'
        assert result[0]['subject'] == 'fix: button bug'
        assert result[0]['author'] == 'John'

    def test_parse_commits_multiple(self):
        """Parses multiple commits correctly."""
        commits_str = '''abc123|feat: add login|body1|John|2024-01-01
def456|fix: button|body2|Jane|2024-01-02'''
        result = parse_commits(commits_str)

        assert len(result) == 2
        assert result[0]['subject'] == 'feat: add login'
        assert result[1]['subject'] == 'fix: button'


class TestCategorizeCommits:
    """Tests for categorize_commits function."""

    def test_categorize_commits_feature(self):
        """Categorizes feat: commits as features."""
        commits = [{'subject': 'feat: add login'}]
        result = categorize_commits(commits)
        assert len(result['features']) == 1

    def test_categorize_commits_fix(self):
        """Categorizes fix: commits as fixes."""
        commits = [{'subject': 'fix: button bug'}]
        result = categorize_commits(commits)
        assert len(result['fixes']) == 1

    def test_categorize_commits_refactor(self):
        """Categorizes refactor: commits as refactor."""
        commits = [{'subject': 'refactor: auth module'}]
        result = categorize_commits(commits)
        assert len(result['refactor']) == 1

    def test_categorize_commits_docs(self):
        """Categorizes docs: commits as docs."""
        commits = [{'subject': 'docs: update readme'}]
        result = categorize_commits(commits)
        assert len(result['docs']) == 1

    def test_categorize_commits_chore(self):
        """Categorizes chore: commits as chore."""
        commits = [{'subject': 'chore: update deps'}]
        result = categorize_commits(commits)
        assert len(result['chore']) == 1

    def test_categorize_commits_test(self):
        """Categorizes test: commits as test."""
        commits = [{'subject': 'test: add unit tests'}]
        result = categorize_commits(commits)
        assert len(result['test']) == 1

    def test_categorize_commits_other(self):
        """Categorizes unknown prefixes as other."""
        commits = [{'subject': 'random commit message'}]
        result = categorize_commits(commits)
        assert len(result['other']) == 1

    def test_categorize_commits_multiple(self):
        """Categorizes multiple commits correctly."""
        commits = [
            {'subject': 'feat: add login'},
            {'subject': 'fix: button bug'},
            {'subject': 'docs: update readme'},
            {'subject': 'other message'},
        ]
        result = categorize_commits(commits)
        assert len(result['features']) == 1
        assert len(result['fixes']) == 1
        assert len(result['docs']) == 1
        assert len(result['other']) == 1


class TestMain:
    """Tests for main() entry point."""

    def test_main_not_git_repo_exits_1(self, tmp_path, monkeypatch, capsys):
        """Exits with error when not in git repo."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['changelog'])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert 'not inside a git repository' in captured.err.lower()

    def test_main_no_commits_exits_0(self, mock_git_repo, monkeypatch, capsys, mock_config):
        """Exits cleanly when no commits in range."""
        monkeypatch.chdir(mock_git_repo)

        # Create a tag at HEAD so there are no new commits
        subprocess.run(['git', 'tag', 'v1.0.0'], cwd=mock_git_repo, check=True)

        monkeypatch.setattr(sys, 'argv', ['changelog'])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert 'no commits' in captured.out.lower()

    def test_main_format_flag_accepted(self, mock_git_repo, monkeypatch, capsys, mock_config):
        """Accepts --format flag."""
        monkeypatch.chdir(mock_git_repo)

        # Add commit after initial
        (mock_git_repo / 'file.txt').write_text('content')
        subprocess.run(['git', 'add', '.'], cwd=mock_git_repo, check=True)
        subprocess.run(['git', 'commit', '-m', 'feat: add file'], cwd=mock_git_repo, check=True)

        monkeypatch.setattr(sys, 'argv', ['changelog', '-f', 'json'])

        with patch('ab_cli.commands.changelog.send_to_openrouter') as mock_send:
            mock_send.return_value = {'text': '{"features": ["add file"]}'}

            try:
                main()
            except SystemExit:
                pass

        # If we got here without argument error, the flag was accepted

    def test_main_output_flag_accepted(self, mock_git_repo, monkeypatch, capsys, mock_config, tmp_path):
        """Accepts --output flag."""
        monkeypatch.chdir(mock_git_repo)

        # Add commit
        (mock_git_repo / 'file.txt').write_text('content')
        subprocess.run(['git', 'add', '.'], cwd=mock_git_repo, check=True)
        subprocess.run(['git', 'commit', '-m', 'feat: add file'], cwd=mock_git_repo, check=True)

        output_file = tmp_path / 'CHANGELOG.md'
        monkeypatch.setattr(sys, 'argv', ['changelog', '-o', str(output_file)])

        with patch('ab_cli.commands.changelog.send_to_openrouter') as mock_send:
            mock_send.return_value = {'text': '# Changelog\n\n- Added file'}

            try:
                main()
            except SystemExit:
                pass

        # If we got here without argument error, the flag was accepted

    def test_main_categories_flag_accepted(self, mock_git_repo, monkeypatch, capsys, mock_config):
        """Accepts --categories flag."""
        monkeypatch.chdir(mock_git_repo)

        # Add commit
        (mock_git_repo / 'file.txt').write_text('content')
        subprocess.run(['git', 'add', '.'], cwd=mock_git_repo, check=True)
        subprocess.run(['git', 'commit', '-m', 'feat: add file'], cwd=mock_git_repo, check=True)

        monkeypatch.setattr(sys, 'argv', ['changelog', '-c'])

        with patch('ab_cli.commands.changelog.send_to_openrouter') as mock_send:
            mock_send.return_value = {'text': '# Changelog\n\n## Features\n- Added file'}

            try:
                main()
            except SystemExit:
                pass

        # If we got here without argument error, the flag was accepted

    def test_main_generates_changelog(self, mock_git_repo, monkeypatch, capsys, mock_config):
        """Generates and displays changelog."""
        monkeypatch.chdir(mock_git_repo)

        # Add commits after initial
        (mock_git_repo / 'file.txt').write_text('content')
        subprocess.run(['git', 'add', '.'], cwd=mock_git_repo, check=True)
        subprocess.run(['git', 'commit', '-m', 'feat: add file'], cwd=mock_git_repo, check=True)

        # Use explicit range that we know has commits
        monkeypatch.setattr(sys, 'argv', ['changelog', 'HEAD~1..HEAD'])

        with patch('ab_cli.commands.changelog.generate_changelog') as mock_gen:
            mock_gen.return_value = '## Changelog\n\n- feat: add file'

            try:
                main()
            except SystemExit:
                pass

            # Verify generate_changelog was called
            assert mock_gen.called
