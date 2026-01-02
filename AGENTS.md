# Repository Guidelines

## Project Structure & Module Organization

This repository contains unified CLI utilities under the `ab` command. Current structure:

```
ai-linux-dev-utilities/
├── ab                    # Main command (dispatcher)
├── ab-config             # Configuration management CLI
├── ab-git                # Sub-dispatcher for git commands
├── ab-util               # Sub-dispatcher for utilities
├── ab-prompt             # Bash wrapper for prompt.py
├── ab.bash-completion    # Bash autocompletion
├── lib/                  # Shared Python libraries
│   └── ab_config.py      # Centralized configuration module
├── auto_commit.py        # Generate commit messages via LLM
├── pr_description.py     # Generate PR title/description via LLM
├── rewrite_history.py    # Rewrite commit messages via LLM
├── prompt.py             # CLI to send context to OpenRouter
├── passgenerator         # Secure password generator
├── install.sh            # Installation script (local and remote)
└── requirements.txt      # Python dependencies
```

User settings are stored in `~/.ab/config.json`. Call history in `~/.ab/history/`.

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

### ab git (git commands)
```bash
ab git auto-commit      # Generate commit message via LLM
ab git pr-description   # Generate PR title/description via LLM
ab git rewrite-history  # Rewrite commit messages via LLM
ab git help             # Show category help
```

### ab util (utilities)
```bash
ab util passgenerator   # Secure password generator
ab util help            # Show category help
```

### ab git auto-commit
Automatically generate commit messages by analyzing staged diff.
```bash
ab git auto-commit              # Generate message and confirm
ab git auto-commit -a           # Add all files (git add -A)
ab git auto-commit -y           # Skip confirmation
ab git auto-commit -a -y        # Add all and commit without confirmation
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
sudo ln -s $(pwd)/ab /usr/local/bin/ab
mkdir -p ~/.local/share/bash-completion/completions
ln -s $(pwd)/ab.bash-completion ~/.local/share/bash-completion/completions/ab
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
