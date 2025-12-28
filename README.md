# Linux Utilities (ab)

Unified CLI utilities for development workflows, powered by LLMs via OpenRouter.

## Installation

### Quick Install (Recommended)

```bash
# Clone the repository
git clone <repo-url>
cd linux-utilities

# Run the installer
./install.sh
```

The installer will:
- Create a Python virtual environment
- Install all dependencies
- Optionally create a symlink at `/usr/local/bin/ab`
- Optionally enable bash autocompletion

### Manual Installation

```bash
# Clone the repository
git clone <repo-url>
cd linux-utilities

# Create virtual environment and install dependencies
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
- `gh` CLI (optional, for `pr-description -c`)

## Configuration

### API Key Setup

```bash
export OPENROUTER_API_KEY="your-api-key-here"
```

### Persistent Configuration

Create `~/.prompt/config.json`:

```json
{
  "model": "nvidia/nemotron-3-nano-30b-a3b:free",
  "api_base": "https://openrouter.ai/api/v1",
  "api_key_env": "OPENROUTER_API_KEY",
  "request": { "timeout_seconds": 300 }
}
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
- **History tracking**: All interactions saved to `~/.prompt/history/`

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
ab prompt --model "openai/gpt-4o" file.py -p "Optimize this"

# Read prompt from stdin
echo "Summarize this code" | ab prompt src/ -p -

# Get JSON response
ab prompt data.json -p "Parse and validate" --only-output --json

# Use developer specialist persona
ab prompt app.py -s dev -p "Refactor this function"

# Unlimited response length
ab prompt -u -p "Write a comprehensive tutorial"

# Set default model
ab prompt --set-default-model "openai/gpt-4o-mini"
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

### ab auto-commit

Generate commit messages automatically by analyzing staged changes.

```bash
ab auto-commit [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-a` | Stage all files (`git add -A`) before committing |
| `-y` | Skip confirmation prompt |
| `-l LANG` | Output language (default: `en`) |

```bash
# Generate and confirm commit message
ab auto-commit

# Stage all and commit without confirmation
ab auto-commit -a -y
```

---

### ab pr-description

Generate pull request title and description by analyzing commits and diff.

```bash
ab pr-description [OPTIONS]
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
ab pr-description

# Create PR directly
ab pr-description -c

# Create draft PR against develop
ab pr-description -c -d -b develop

# Generate in Portuguese
ab pr-description -l pt-br
```

---

### ab passgenerator

Generate secure passwords with customizable requirements.

```bash
ab passgenerator LENGTH [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--min-digits N` | Minimum number of digits |
| `--no-punct` | Exclude punctuation characters |

```bash
# 16-character password
ab passgenerator 16

# 20 chars with at least 4 digits
ab passgenerator 20 --min-digits 4

# No punctuation
ab passgenerator 12 --no-punct
```

---

## Automatic Model Selection

The `auto-commit` and `pr-description` commands automatically select models based on diff size:

| Estimated Tokens | Model |
|------------------|-------|
| ≤ 128k | `nvidia/nemotron-3-nano-30b-a3b:free` |
| ≤ 256k | `openai/gpt-5-nano` |
| > 256k | `x-ai/grok-4.1-fast` |

---

## History

All prompt interactions are saved to `~/.prompt/history/` with:

- Timestamp and session ID
- Model and provider info
- Token usage and estimated cost
- Full prompt and response
- Files processed

View the index at `~/.prompt/history/index.json`.

---

## License

MIT
