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
sudo ln -s $(pwd)/bin/ab /usr/local/bin/ab

# Enable bash autocompletion (optional)
mkdir -p ~/.local/share/bash-completion/completions
ln -s $(pwd)/completions/ab.bash-completion ~/.local/share/bash-completion/completions/ab
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

### Git Commands (`ab git`)

| Command | Description |
|---------|-------------|
| `auto-commit` | Generate commit messages via LLM |
| `branch-name` | Generate branch name from task description |
| `changelog` | Generate changelog from commits |
| `pr-description` | Generate PR title/description via LLM |
| `resolve-conflict` | Resolve merge conflicts via LLM |
| `rewrite-history` | Rewrite commit messages via LLM |

### Utility Commands (`ab util`)

| Command | Description |
|---------|-------------|
| `explain` | Explain code, errors, or concepts via LLM |
| `gen-script` | Generate scripts from natural language |
| `passgenerator` | Secure password generator |

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

**Protected branch detection**: When on `master` or `main`, auto-commit will suggest creating a feature branch before committing.

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

### ab git branch-name

Generate branch names from task descriptions using LLM.

```bash
ab git branch-name [OPTIONS] "description"
```

| Option | Description |
|--------|-------------|
| `-c` | Create and checkout the branch |
| `-p PREFIX` | Force a specific prefix (feature, fix, chore, etc.) |
| `-y` | Skip confirmation when creating |
| `-l LANG` | Output language (default: `en`) |

```bash
# Suggest branch name
ab git branch-name "fix login bug"
# Output: fix/login-bug

# Create and checkout
ab git branch-name -c "add user authentication"

# Force prefix
ab git branch-name --prefix fix "button alignment"
# Output: fix/button-alignment

# With JIRA ticket
ab git branch-name "JIRA-123: implement payment gateway"
# Output: feature/JIRA-123-implement-payment
```

---

### ab git changelog

Generate changelog/release notes from commits using LLM.

```bash
ab git changelog [OPTIONS] [RANGE]
```

| Option | Description |
|--------|-------------|
| `-f FORMAT` | Output format: `markdown`, `plain`, `json` |
| `-c` | Group commits by type (feat/fix/chore) |
| `-o FILE` | Write output to file |
| `-l LANG` | Output language (default: `en`) |

```bash
# Since last tag to HEAD
ab git changelog

# Between two tags
ab git changelog v1.0.0..v2.0.0

# Last 10 commits in JSON
ab git changelog HEAD~10..HEAD -f json

# Write to file with categories
ab git changelog -c -o CHANGELOG.md
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

### ab git resolve-conflict

Analyze and resolve merge conflicts using LLM.

```bash
ab git resolve-conflict [OPTIONS] [FILE]
```

| Option | Description |
|--------|-------------|
| `-y` | Auto-apply resolutions without confirmation |
| `--dry-run` | Preview resolutions without applying |
| `-l LANG` | Output language (default: `en`) |

```bash
# Interactive mode for all conflicted files
ab git resolve-conflict

# Resolve specific file
ab git resolve-conflict src/app.py

# Preview suggestions only
ab git resolve-conflict --dry-run

# Auto-apply all resolutions
ab git resolve-conflict -y
```

**Features:**
- Detects conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`)
- Extracts both versions with surrounding context
- Suggests intelligent merged resolution
- Option to edit manually before applying

---

### ab util explain

Explain code, errors, or technical concepts using LLM with automatic context gathering.

```bash
ab util explain [OPTIONS] [INPUT]
```

| Option | Description |
|--------|-------------|
| `-c CONCEPT` | Explain a technical concept |
| `--history N` | Include last N lines from bash history |
| `--with-files` | Include directory listing and referenced files |
| `--context-dir PATH` | Directory for context gathering |
| `-v` | Verbose/detailed explanation |
| `-l LANG` | Output language (default: `en`) |

```bash
# Explain entire file
ab util explain src/app.py

# Explain specific line
ab util explain src/app.py:42

# Explain line range
ab util explain src/app.py:10-50

# Explain error message
ab util explain "error: ECONNREFUSED"

# Explain concept
ab util explain --concept "dependency injection"

# From stdin
echo "stack trace" | ab util explain -

# With bash history context
ab util explain --history 20 "command failed"

# With directory context
ab util explain --with-files "file not found"
```

---

### ab util gen-script

Generate bash/python scripts from natural language descriptions.

**Default behavior**: Generates minimal one-liner commands. Use `--full` for complete scripts with error handling.

```bash
ab util gen-script [OPTIONS] "description"
```

| Option | Description |
|--------|-------------|
| `--lang LANG` | Script language: `bash`, `python`, `sh`, `perl`, `ruby`, `node` |
| `--type TYPE` | Script type: `script`, `cron`, `oneshot` (default: oneshot) |
| `--full` | Generate complete script with error handling |
| `-o FILE` | Output file path (auto-enables full mode) |
| `--run` | Execute the generated script immediately |
| `-l LANG` | Output language for comments |

```bash
# One-liner output (default)
ab util gen-script "list all files larger than 100MB"
# Output: find . -size +100M

# Full script with error handling
ab util gen-script --full "backup database"

# Generate Python one-liner
ab util gen-script --lang python "parse CSV and sum column 3"

# Save to file (auto-full mode)
ab util gen-script -o backup.sh "compress and upload to S3"

# Execute immediately
ab util gen-script --run "show disk usage summary"

# Cron-suitable script
ab util gen-script --type cron "backup database daily"
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
