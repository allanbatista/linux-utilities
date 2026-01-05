# Repository Guidelines

## Project Structure & Module Organization

This repository contains unified CLI utilities under the `ab` command. Project follows Python src-layout:

```
ai-linux-dev-utilities/
├── bin/                          # Bash dispatchers (entry points)
│   ├── ab                        # Main command (dispatcher)
│   ├── ab-config                 # Configuration CLI wrapper
│   ├── ab-git                    # Sub-dispatcher for git commands
│   ├── ab-models                 # Models listing wrapper
│   ├── ab-util                   # Sub-dispatcher for utilities
│   └── ab-prompt                 # Prompt wrapper
│
├── src/ab_cli/                   # Python package (main implementation)
│   ├── __init__.py
│   ├── core/                     # Shared modules
│   │   ├── __init__.py
│   │   └── config.py             # Centralized configuration module
│   ├── commands/                 # CLI commands
│   │   ├── __init__.py
│   │   ├── auto_commit.py        # Generate commit messages via LLM
│   │   ├── branch_name.py        # Generate branch names from descriptions
│   │   ├── changelog.py          # Generate changelog from commits
│   │   ├── config_cli.py         # Configuration management CLI
│   │   ├── explain.py            # Explain code, errors, or concepts
│   │   ├── gen_script.py         # Generate scripts from descriptions
│   │   ├── models.py             # List available LLM models
│   │   ├── pr_description.py     # Generate PR title/description via LLM
│   │   ├── prompt.py             # CLI to send context to OpenRouter
│   │   ├── resolve_conflict.py   # Resolve merge conflicts via LLM
│   │   └── rewrite_history.py    # Rewrite commit messages via LLM
│   └── utils/
│       └── __init__.py
│
├── scripts/                      # Standalone bash utilities
│   └── passgenerator             # Secure password generator
│
├── tests/                        # Test directory
│   ├── conftest.py               # pytest fixtures
│   ├── unit/                     # Unit tests
│   └── integration/              # Integration tests
│
├── completions/                  # Shell completions
│   └── ab.bash-completion
│
├── pyproject.toml                # Modern Python packaging
├── requirements.txt              # Python dependencies
├── install.sh                    # Installation script
├── AGENTS.md                     # This file
└── README.md                     # User documentation
```

User settings are stored in `~/.ab/config.json`. Call history in `~/.ab/history/`.

---

## Testing Requirements (NON-NEGOTIABLE)

**Tests are a mandatory requirement for all code changes.** This is not optional.

### Rules

1. **Every new command MUST have integration tests** in `tests/integration/test_<command>.py`
2. **Every new utility function MUST have unit tests** in `tests/unit/`
3. **All tests MUST pass before any code is considered complete**
4. **PRs without tests will NOT be accepted**

### Test Structure

```
tests/
├── conftest.py           # Shared fixtures (mock_git_repo, mock_config, etc.)
├── unit/                 # Unit tests for isolated functions
│   ├── test_config.py
│   ├── test_config_cli.py
│   └── test_utils.py
└── integration/          # Integration tests for commands
    ├── test_auto_commit.py
    ├── test_branch_name.py
    ├── test_changelog.py
    ├── test_explain.py
    ├── test_gen_script.py
    ├── test_pr_description.py
    ├── test_resolve_conflict.py
    └── test_rewrite_history.py
```

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/integration/test_gen_script.py -v

# Run with coverage
python -m pytest tests/ --cov=src/ab_cli --cov-report=term-missing
```

### What to Test

For each command, test:
- **Helper functions** (parsing, validation, git operations)
- **main() entry point** with different flags
- **Error cases** (not in git repo, file not found, etc.)
- **Edge cases** (empty input, special characters, etc.)

### Test Patterns

Use fixtures from `conftest.py`:
```python
def test_example(self, mock_git_repo, monkeypatch, mock_config):
    monkeypatch.chdir(mock_git_repo)
    # ... test code
```

Mock LLM calls to avoid external dependencies:
```python
with patch('ab_cli.commands.xxx.find_prompt_command') as mock:
    mock.side_effect = FileNotFoundError('abort test')
```

---

## Available Commands

### ab (unified command)
```bash
ab <category|command> [arguments...]

# Categories:
ab git <command>        # Git utilities powered by LLM
ab util <command>       # General utilities

# Root commands:
ab prompt               # Send context to LLM (OpenRouter)
ab config               # Manage configuration
ab models               # List available LLM models
ab help                 # Show help
```

### ab config (configuration management)
```bash
ab config show              # Display current configuration
ab config get <key>         # Get a specific config value
ab config set <key> <value> # Set a config value
ab config init              # Create default configuration
ab config path              # Show config file path
ab config edit              # Open config in editor
ab config list-keys         # List all available config keys
```

### ab models (list LLM models)
List and explore available LLM models from OpenRouter API.
```bash
ab models                              # List all models (table format)
ab models list                         # Same as above
ab models list --free                  # Show only free models
ab models list --search <term>         # Search by name/description
ab models list --context-min <n>       # Filter by minimum context length
ab models list --modality <type>       # Filter by modality (text, image, audio, video)
ab models list --sort <field>          # Sort by: name, context, price
ab models list --limit <n>             # Limit results (default: 50)
ab models list --json                  # Output as JSON
ab models info <model-id>              # Show detailed info for a model
ab models info <model-id> --json       # Model details as JSON
```

**Examples:**
```bash
ab models list --free --search llama   # Free Llama models
ab models list --context-min 128000    # Models with 128k+ context
ab models list --modality image        # Vision models
ab models info openai/gpt-4o           # Details for GPT-4o
```

### ab git (git commands)
```bash
ab git auto-commit      # Generate commit message via LLM
ab git branch-name      # Generate branch name from task description
ab git changelog        # Generate changelog from commits
ab git pr-description   # Generate PR title/description via LLM
ab git resolve-conflict # Resolve merge conflicts via LLM
ab git rewrite-history  # Rewrite commit messages via LLM
ab git help             # Show category help
```

### ab util (utilities)
```bash
ab util explain         # Explain code, errors, or concepts via LLM
ab util gen-script      # Generate scripts from natural language
ab util passgenerator   # Secure password generator
ab util help            # Show category help
```

### ab git auto-commit
Automatically generate commit messages by analyzing staged diff.

**Protected branch detection**: When on `master` or `main`, auto-commit will suggest creating a feature branch before committing.

```bash
ab git auto-commit              # Generate message and confirm
ab git auto-commit -a           # Add all files (git add -A)
ab git auto-commit -y           # Skip confirmation
ab git auto-commit -a -y        # Add all and commit without confirmation
```

### ab git branch-name
Generate branch names from task descriptions using LLM.
```bash
ab git branch-name "fix login bug"                    # Suggest: fix/login-bug
ab git branch-name "add user authentication"          # Suggest: feature/add-user-authentication
ab git branch-name "JIRA-123: implement payment"      # Suggest: feature/JIRA-123-implement-payment
ab git branch-name -c "new feature"                   # Create and checkout the branch
ab git branch-name --prefix fix "button alignment"    # Force prefix: fix/button-alignment
ab git branch-name -y "task description"              # Skip confirmation when creating
```

### ab git changelog
Generate changelog/release notes from commits using LLM.
```bash
ab git changelog                        # Since last tag to HEAD
ab git changelog v1.0.0..v2.0.0         # Between two tags
ab git changelog HEAD~10..HEAD          # Last 10 commits
ab git changelog --format markdown      # Markdown output (default)
ab git changelog --format plain         # Plain text output
ab git changelog --format json          # JSON output
ab git changelog -c                     # Group by type (feat/fix/chore)
ab git changelog -o CHANGELOG.md        # Write to file
```

### ab git pr-description
Generate PR title and description by analyzing commits and diff relative to base branch.
```bash
ab git pr-description              # Generate title and description
ab git pr-description -c           # Generate and create PR via gh CLI
ab git pr-description -c -d        # Create as draft
ab git pr-description -b develop   # Specify base branch
ab git pr-description -c -y        # Create PR without confirmation
```

### ab git rewrite-history
Rewrite commit messages in git history using LLM.
```bash
ab git rewrite-history                     # Interactive menu to choose mode
ab git rewrite-history --dry-run           # Preview without applying changes
ab git rewrite-history HEAD~5..HEAD        # Rewrite last 5 commits
ab git rewrite-history -y -l pt-br         # Batch mode in Portuguese
ab git rewrite-history --force-all         # Force rewrite all
ab git rewrite-history --smart             # LLM decides which need rewriting
```

**Operation modes:**
- **Interactive**: Prompts for each commit whether to rewrite
- **Smart**: LLM evaluates if message needs rewriting (commits < 5 words are auto-rewritten)
- **Force-all**: Rewrites all commits in range

**Safety features:**
- Creates backup branch before changes (`backup/pre-rewrite-TIMESTAMP`)
- Warning if commits were already pushed (requires force push)
- `--dry-run` mode for full preview

### ab git resolve-conflict
Analyze and resolve merge conflicts using LLM.
```bash
ab git resolve-conflict              # Interactive mode for all conflicted files
ab git resolve-conflict file.py      # Resolve specific file
ab git resolve-conflict -y           # Auto-apply suggestions
ab git resolve-conflict --dry-run    # Preview suggestions only
```

**Features:**
- Detects conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`)
- Extracts both versions with surrounding context
- Suggests intelligent merged resolution
- Option to edit manually before applying

### ab prompt
Send file context to OpenRouter and return LLM response.
```bash
ab prompt -p "question"                    # Send simple prompt
ab prompt file.py -p "explain"             # Send file as context
ab prompt src/ -p "summarize the code"     # Send entire directory
ab prompt --model "openai/gpt-4o" -p "hi"  # Specify model
ab prompt --only-output -p "hi"            # Return only response
ab prompt --set-default-model "model"      # Set default model
```

### ab util explain
Explain code, errors, or technical concepts using LLM with automatic context gathering.
```bash
ab util explain file.py                 # Explain entire file
ab util explain file.py:42              # Explain specific line
ab util explain file.py:10-50           # Explain line range
ab util explain "error: ECONNREFUSED"   # Explain error message
ab util explain --concept "dependency injection"  # Explain concept
echo "stack trace" | ab util explain -  # Explain from stdin
ab util explain --history 20 "error"    # Include last 20 bash commands as context
ab util explain --with-files "not found" # Include directory listing
ab util explain -v "complex topic"      # Verbose/detailed explanation
```

**Context gathering:**
- `--history N`: Include last N lines from bash history
- `--with-files`: Include `ls -la` output and auto-read files mentioned in errors
- `--context-dir PATH`: Specify directory for context gathering

### ab util gen-script
Generate bash/python scripts from natural language descriptions.

**Default**: Generates minimal one-liner commands. Use `--full` for complete scripts.

```bash
ab util gen-script "list all files larger than 100MB"   # One-liner output
ab util gen-script --full "backup database"             # Full script with error handling
ab util gen-script --type cron "backup daily at 3am"    # Cron-suitable script
ab util gen-script --lang python "parse CSV sum col 3"  # Python one-liner
ab util gen-script -o backup.sh "compress and upload"   # Auto-full when saving
ab util gen-script --run "show disk usage"              # Execute immediately
```

**Options:**
- `--lang`: Script language (bash, python, sh, perl, ruby, node)
- `--type`: Script type (script, cron, oneshot - default: oneshot)
- `--full`: Generate complete script with error handling
- `-o`: Output file path (auto-enables full mode)
- `--run`: Execute the generated script immediately

### ab util passgenerator
Generate secure passwords with validations.
```bash
ab util passgenerator 16                    # 16-character password
ab util passgenerator 20 --min-digits 4     # Minimum 4 digits
ab util passgenerator 12 --no-punct         # No punctuation
```

## Installation

### Quick Install (Recommended)
```bash
curl -fsSL https://raw.githubusercontent.com/allanbatista/ai-linux-dev-utilities/master/install.sh | bash
```

### Install with Options
```bash
# Custom directory
curl -fsSL https://raw.githubusercontent.com/allanbatista/ai-linux-dev-utilities/master/install.sh | bash -s -- -d ~/my-directory

# Skip confirmations (accept all)
curl -fsSL https://raw.githubusercontent.com/allanbatista/ai-linux-dev-utilities/master/install.sh | bash -s -- -y
```

### Manual Installation
```bash
# Clone repository
git clone https://github.com/allanbatista/ai-linux-dev-utilities.git
cd ai-linux-dev-utilities

# Run local installer
./install.sh

# Or manually:
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
sudo ln -s $(pwd)/bin/ab /usr/local/bin/ab
mkdir -p ~/.local/share/bash-completion/completions
ln -s $(pwd)/completions/ab.bash-completion ~/.local/share/bash-completion/completions/ab
```

## Configuration

### OpenRouter API Key
```bash
export OPENROUTER_API_KEY="your-api-key-here"
```

### Configuration File (~/.ab/config.json)

Create or manage with `ab config`:
```bash
ab config init              # Create default config
ab config show              # View current config
ab config set global.language pt-br    # Change language
ab config set models.default "openai/gpt-4o"  # Change default model
```

**Full config structure:**
```json
{
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
    "rewrite-history": {
      "smart_mode": true,
      "skip_merges": true
    },
    "prompt": {
      "max_tokens": 900000,
      "max_tokens_doc": 250000,
      "max_completion_tokens": 16000
    }
  },
  "history": {
    "enabled": true,
    "directory": "~/.ab/history"
  }
}
```

### Config Precedence

1. CLI arguments (highest priority)
2. Command-specific config (`commands.<cmd>.<key>`)
3. Global config (`global.<key>`)
4. Hardcoded defaults (lowest)

## Automatic Model Selection

The `auto-commit`, `pr-description` and `rewrite-history` commands automatically select models based on diff size:

| Estimated Tokens | Model |
|------------------|-------|
| ≤ 128k | `nvidia/nemotron-3-nano-30b-a3b:free` |
| ≤ 256k | `openai/gpt-5-nano` |
| > 256k | `x-ai/grok-4.1-fast` |

These thresholds and models are configurable via `ab config`.

## Coding Style & Naming Conventions

- **Python**: PEP 8, 4-space indents, `snake_case` for functions
- **Bash**: POSIX-friendly, use `shellcheck` for validation
- **CLI options**: kebab-case (`--only-output`, `--max-tokens`)
- Type hints in new Python code

## Commit & Pull Request Guidelines

Use conventional commit prefixes (`feat:`, `fix:`, `chore:`) with imperative summaries. You can use `ab git auto-commit` to generate messages.

```bash
# Recommended workflow
ab git auto-commit -a           # Generate and commit
ab git pr-description -c        # Generate and create PR
```

## Security & Configuration Tips

- Do not commit `~/.ab/config.json` or files containing keys
- Load `OPENROUTER_API_KEY` from environment
- Avoid echoing secrets in logs

---

## Development & Testing

### Step 1: Running Tests with pytest

Run the test suite locally to verify all functionality:

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
python -m pytest tests/ -v

# Run with coverage report
python -m pytest tests/ --cov=src/ab_cli --cov-report=term-missing

# Run specific test file
python -m pytest tests/integration/test_auto_commit.py -v

# Run specific test class or method
python -m pytest tests/unit/test_config.py::TestAbConfig -v
```

**Expected output**: All 387+ tests should pass.

### Step 2: Running GitHub Actions Locally with act

Use [act](https://github.com/nektos/act) to run GitHub Actions workflows locally before pushing:

```bash
# Install act (if not installed)
# macOS: brew install act
# Linux: curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Run all workflows
act

# Run specific workflow job
act -j test                    # Run test job
act -j lint                    # Run lint job
act -j shellcheck              # Run shellcheck job

# Run with specific Python version
act -j test --matrix python-version:3.12

# Use custom Docker image for better compatibility
act -j test -P ubuntu-latest=catthehacker/ubuntu:act-latest

# List available jobs
act -l
```

**Expected output**: All jobs should succeed (Codecov upload may fail locally without token).

### Step 3: Testing with Docker

Use Docker to test installation and commands in a clean environment:

```bash
# Build the Docker image
docker build -t ab-cli-test .

# Run ab help
docker run --rm ab-cli-test ab help

# Run ab git help
docker run --rm ab-cli-test ab git help

# Test config show
docker run --rm ab-cli-test ab config show

# Test passgenerator
docker run --rm ab-cli-test ab util passgenerator 16

# Run tests inside Docker
docker run --rm ab-cli-test bash -c "cd /app && pytest tests/ -v"

# Interactive shell for debugging
docker run --rm -it ab-cli-test bash
```

**Dockerfile location**: `/Dockerfile` in project root.

**Expected output**: All commands should work, tests should pass (387+ tests).

### Quick Validation Script

Run all 3 steps in sequence:

```bash
#!/bin/bash
set -e

echo "=== Step 1: Running pytest ==="
python -m pytest tests/ -v --tb=short

echo ""
echo "=== Step 2: Running act (test job) ==="
act -j test --matrix python-version:3.12 -P ubuntu-latest=catthehacker/ubuntu:act-latest

echo ""
echo "=== Step 3: Testing with Docker ==="
docker build -t ab-cli-test .
docker run --rm ab-cli-test ab help
docker run --rm ab-cli-test bash -c "cd /app && pytest tests/ -v --tb=short -q | tail -5"

echo ""
echo "✅ All validation steps passed!"
```
