# Ai Linux Dev Utilities (ab)

Unified CLI utilities for development workflows, powered by LLMs via OpenRouter.

## Installation

### Quick Install (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/allanbatista/ai-linux-dev-utilities/master/install.sh | bash
```

This will:
- Clone the repository to `~/.local/share/ai-linux-dev-utilities`
- Create a Python virtual environment
- Install all dependencies
- Optionally create a symlink at `/usr/local/bin/ab`
- Optionally enable bash autocompletion

#### Install Options

```bash
# Install to custom directory
curl -fsSL https://raw.githubusercontent.com/allanbatista/ai-linux-dev-utilities/master/install.sh | bash -s -- -d ~/my-custom-dir

# Skip confirmation prompts (auto-accept all)
curl -fsSL https://raw.githubusercontent.com/allanbatista/ai-linux-dev-utilities/master/install.sh | bash -s -- -y

# Show help
curl -fsSL https://raw.githubusercontent.com/allanbatista/ai-linux-dev-utilities/master/install.sh | bash -s -- -h
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/allanbatista/ai-linux-dev-utilities.git
cd ai-linux-dev-utilities

# Run the local installer
./install.sh

# Or manually:
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Add to PATH (optional - requires sudo)
sudo ln -s $(pwd)/ab /usr/local/bin/ab

# Enable bash autocompletion (optional)
mkdir -p ~/.local/share/bash-completion/completions
ln -s $(pwd)/ab.bash-completion ~/.local/share/bash-completion/completions/ab
```

### Requirements

- Python 3.8+
- `git` (for .aiignore git root detection)
- `gh` CLI (optional, for `ab git pr-description -c`)

## Configuration

### API Key Setup

```bash
export OPENROUTER_API_KEY="your-api-key-here"
```

### Persistent Configuration

Manage with `ab config`:

```bash
ab config init              # Create default config
ab config show              # View current config
ab config set global.language pt-br    # Change language
ab config set models.default "openai/gpt-4o"  # Change default model
```

Configuration is stored in `~/.ab/config.json`:

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
    "default": "nvidia/nemotron-3-nano-30b-a3b:free",
    "small": "nvidia/nemotron-3-nano-30b-a3b:free",
    "medium": "openai/gpt-5-nano",
    "large": "x-ai/grok-4.1-fast"
  }
}
```

---

## Command Structure

Commands are organized into categories:

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

---

## Commands

### ab prompt

Send files and prompts to LLMs via OpenRouter API.

```bash
ab prompt [OPTIONS] [PATH...]
```

#### Features

- **Automatic binary detection**: Binary files are automatically skipped
- **`.aiignore` support**: Use gitignore-style patterns to exclude files
- **Multiple file/directory support**: Process entire directories recursively
- **Token management**: Control context and response token limits
- **Specialist personas**: Use pre-configured expert prompts
- **History tracking**: All interactions saved to `~/.ab/history/`

#### Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--prompt TEXT` | `-p` | Prompt to send to the LLM. Use `-` for stdin | - |
| `--lang LANG` | - | Output language | `pt-br` |
| `--max-tokens N` | `-n` | Max tokens for total context | 900000 |
| `--max-tokens-doc N` | `-nn` | Max tokens per file | 250000 |
| `--max-completion-tokens N` | `-m` | Max tokens for response | 16000 |
| `--unlimited` | `-u` | No limit on response tokens | false |
| `--model NAME` | - | OpenRouter model name | config default |
| `--specialist TYPE` | `-s` | Persona: `dev` or `rm` | - |
| `--set-default-model NAME` | - | Persist default model to config | - |
| `--only-output` | - | Return only model response (no logs) | false |
| `--json` | - | Parse and format response as JSON | false |
| `--relative-paths` | - | Show relative paths in output | false |
| `--filename-only` | - | Show only filename in output | false |

#### Examples

```bash
# Simple prompt (no files)
ab prompt -p "What is Python?"

# Analyze a single file
ab prompt script.py -p "Explain this code"

# Process entire directory
ab prompt src/ -p "Review for security issues"

# Use specific model
ab prompt --model "openai/gpt-5" file.py -p "Optimize this"

# Read prompt from stdin
echo "Summarize this code" | ab prompt src/ -p -

# Get JSON response
ab prompt data.json -p "Parse and validate" --only-output --json

# Use developer specialist persona
ab prompt app.py -s dev -p "Refactor this function"

# Unlimited response length
ab prompt -u -p "Write a comprehensive tutorial"

# Set default model
ab prompt --set-default-model "openai/gpt-5-mini"
```

#### .aiignore File

Create a `.aiignore` file to exclude files from processing. Uses gitignore syntax:

```gitignore
# Ignore logs
*.log

# Ignore directories
node_modules/
__pycache__/
.git/
dist/
build/

# Ignore sensitive files
.env
*.secret
credentials.json

# Negation (include this file even if matched above)
!important.log
```

The tool searches for `.aiignore` files from the current directory up to the git root, combining all patterns found.

---

### ab git auto-commit

Generate commit messages automatically by analyzing staged changes.

```bash
ab git auto-commit [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-a` | Stage all files (`git add -A`) before committing |
| `-y` | Skip confirmation prompt |
| `-l LANG` | Output language (default: `en`) |

```bash
# Generate and confirm commit message
ab git auto-commit

# Stage all and commit without confirmation
ab git auto-commit -a -y
```

---

### ab git pr-description

Generate pull request title and description by analyzing commits and diff.

```bash
ab git pr-description [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-c` | Create PR via `gh` CLI after generating |
| `-d` | Create as draft PR |
| `-b BRANCH` | Specify base branch |
| `-l LANG` | Output language (default: `en`) |
| `-y` | Skip confirmation prompt |

```bash
# Generate PR description
ab git pr-description

# Create PR directly
ab git pr-description -c

# Create draft PR against develop
ab git pr-description -c -d -b develop

# Generate in Portuguese
ab git pr-description -l pt-br
```

---

### ab git rewrite-history

Rewrite commit messages in git history using LLM.

```bash
ab git rewrite-history [OPTIONS] [RANGE]
```

| Option | Description |
|--------|-------------|
| `--dry-run`, `-n` | Preview changes without applying |
| `--smart` | LLM decides which commits need rewriting |
| `--force-all` | Rewrite all commits in range |
| `-y` | Skip confirmation prompts (batch mode) |
| `-l LANG` | Output language (default: `en`) |
| `--backup-branch NAME` | Custom backup branch name |
| `--skip-merges` | Skip merge commits |
| `--include-merges` | Include merge commits |

**Operation Modes:**
- **Interactive**: Prompts for each commit
- **Smart**: LLM evaluates if message needs rewriting (commits < 5 words are auto-rewritten)
- **Force-all**: Rewrites all commits in range

**Safety Features:**
- Creates backup branch before changes (`backup/pre-rewrite-TIMESTAMP`)
- Warning if commits were already pushed (requires force push)
- `--dry-run` mode for full preview

```bash
# Interactive mode
ab git rewrite-history

# Preview without changes
ab git rewrite-history --dry-run

# Rewrite last 5 commits
ab git rewrite-history HEAD~5..HEAD

# Batch mode in Portuguese
ab git rewrite-history -y -l pt-br

# Force rewrite all commits
ab git rewrite-history --force-all

# Smart mode (LLM decides)
ab git rewrite-history --smart
```

---

### ab util passgenerator

Generate secure passwords with customizable requirements.

```bash
ab util passgenerator LENGTH [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--min-digits N` | Minimum number of digits |
| `--no-punct` | Exclude punctuation characters |

```bash
# 16-character password
ab util passgenerator 16

# 20 chars with at least 4 digits
ab util passgenerator 20 --min-digits 4

# No punctuation
ab util passgenerator 12 --no-punct
```

---

## Automatic Model Selection

The `ab git auto-commit`, `ab git pr-description` and `ab git rewrite-history` commands automatically select models based on diff size:

| Estimated Tokens | Model |
|------------------|-------|
| ≤ 128k | `nvidia/nemotron-3-nano-30b-a3b:free` |
| ≤ 256k | `openai/gpt-5-nano` |
| > 256k | `x-ai/grok-4.1-fast` |

---

## History

All prompt interactions are saved to `~/.ab/history/` with:

- Timestamp and session ID
- Model and provider info
- Token usage and estimated cost
- Full prompt and response
- Files processed

View the index at `~/.ab/history/index.json`.

---

## License

MIT
