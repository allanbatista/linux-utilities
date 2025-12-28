#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory (resolve symlinks)
SCRIPT_PATH="$(readlink -f -- "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname -- "$SCRIPT_PATH")"

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Linux Utilities (ab) - Installer   ${NC}"
echo -e "${BLUE}======================================${NC}"
echo

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}[OK]${NC} Python 3 found: $PYTHON_VERSION"

# Create virtual environment
echo -e "\n${YELLOW}[1/4]${NC} Creating virtual environment..."
if [[ -d "$SCRIPT_DIR/.venv" ]]; then
    echo -e "  Virtual environment already exists, skipping..."
else
    python3 -m venv "$SCRIPT_DIR/.venv"
    echo -e "  ${GREEN}Created${NC} $SCRIPT_DIR/.venv"
fi

# Install dependencies
echo -e "\n${YELLOW}[2/4]${NC} Installing Python dependencies..."
"$SCRIPT_DIR/.venv/bin/pip" install --upgrade pip -q
"$SCRIPT_DIR/.venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" -q
echo -e "  ${GREEN}Installed${NC} all dependencies from requirements.txt"

# Add to PATH (optional)
echo -e "\n${YELLOW}[3/4]${NC} Setting up 'ab' command..."

INSTALL_PATH="/usr/local/bin/ab"
if [[ -L "$INSTALL_PATH" || -f "$INSTALL_PATH" ]]; then
    echo -e "  ${YELLOW}Warning:${NC} $INSTALL_PATH already exists"
    read -p "  Overwrite? [y/N] " -r REPLY || REPLY=""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo rm -f "$INSTALL_PATH"
        sudo ln -s "$SCRIPT_DIR/ab" "$INSTALL_PATH"
        echo -e "  ${GREEN}Symlink updated${NC}"
    else
        echo -e "  Skipped symlink creation"
    fi
else
    read -p "  Create symlink at $INSTALL_PATH? [Y/n] " -r REPLY || REPLY=""
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        sudo ln -s "$SCRIPT_DIR/ab" "$INSTALL_PATH"
        echo -e "  ${GREEN}Symlink created:${NC} $INSTALL_PATH -> $SCRIPT_DIR/ab"
    else
        echo -e "  Skipped. You can add to PATH manually:"
        echo -e "    export PATH=\"$SCRIPT_DIR:\$PATH\""
    fi
fi

# Setup bash completion (optional)
echo -e "\n${YELLOW}[4/4]${NC} Setting up bash completion..."

COMPLETION_DIR="$HOME/.local/share/bash-completion/completions"
COMPLETION_FILE="$COMPLETION_DIR/ab"

if [[ -L "$COMPLETION_FILE" || -f "$COMPLETION_FILE" ]]; then
    echo -e "  Bash completion already configured"
else
    read -p "  Enable bash autocompletion? [Y/n] " -r REPLY || REPLY=""
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        mkdir -p "$COMPLETION_DIR"
        ln -s "$SCRIPT_DIR/ab.bash-completion" "$COMPLETION_FILE"
        echo -e "  ${GREEN}Bash completion enabled${NC}"
        echo -e "  ${YELLOW}Note:${NC} Restart your shell or run: source ~/.bashrc"
    else
        echo -e "  Skipped bash completion setup"
    fi
fi

# Setup environment variable reminder
echo -e "\n${BLUE}======================================${NC}"
echo -e "${GREEN}  Installation complete!${NC}"
echo -e "${BLUE}======================================${NC}"
echo
echo -e "Next steps:"
echo -e "  1. Set your OpenRouter API key:"
echo -e "     ${YELLOW}export OPENROUTER_API_KEY=\"your-api-key\"${NC}"
echo -e ""
echo -e "  2. Add to your ~/.bashrc or ~/.zshrc for persistence:"
echo -e "     ${YELLOW}echo 'export OPENROUTER_API_KEY=\"your-api-key\"' >> ~/.bashrc${NC}"
echo -e ""
echo -e "  3. Test the installation:"
echo -e "     ${YELLOW}ab help${NC}"
echo -e "     ${YELLOW}ab prompt -p \"Hello, world!\"${NC}"
echo
