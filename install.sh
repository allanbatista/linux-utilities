#!/usr/bin/env bash
set -euo pipefail

# Repository configuration
REPO_URL="https://github.com/allanbatista/ai-linux-dev-utilities.git"
REPO_NAME="ai-linux-dev-utilities"
DEFAULT_INSTALL_DIR="$HOME/.local/share/$REPO_NAME"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  AI Linux Dev Utilities (ab) - Installer  ${NC}"
echo -e "${BLUE}============================================${NC}"
echo

# Detect if running via curl/pipe or locally
detect_install_mode() {
    # Check if SCRIPT_DIR is already a cloned repo
    if [[ -f "${BASH_SOURCE[0]:-}" ]]; then
        local script_path
        script_path="$(readlink -f -- "${BASH_SOURCE[0]}")"
        local script_dir
        script_dir="$(dirname -- "$script_path")"

        # If we're in a directory with the bin/ab script, assume local install
        if [[ -f "$script_dir/bin/ab" && -f "$script_dir/requirements.txt" ]]; then
            echo "local $script_dir"
            return
        fi
    fi

    echo "remote $DEFAULT_INSTALL_DIR"
}

# Parse command line arguments
INSTALL_DIR=""
SKIP_CONFIRM=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        -y|--yes)
            SKIP_CONFIRM="yes"
            shift
            ;;
        -h|--help)
            echo "Usage: install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -d, --dir DIR    Installation directory (default: $DEFAULT_INSTALL_DIR)"
            echo "  -y, --yes        Skip confirmation prompts"
            echo "  -h, --help       Show this help message"
            echo ""
            echo "Remote install (recommended):"
            echo "  curl -fsSL https://raw.githubusercontent.com/allanbatista/ai-linux-dev-utilities/master/install.sh | bash"
            echo ""
            echo "With custom directory:"
            echo "  curl -fsSL https://raw.githubusercontent.com/allanbatista/ai-linux-dev-utilities/master/install.sh | bash -s -- -d ~/my-dir"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Detect install mode
read -r INSTALL_MODE DETECTED_DIR <<< "$(detect_install_mode)"

# Use detected directory if not overridden
if [[ -z "$INSTALL_DIR" ]]; then
    INSTALL_DIR="$DETECTED_DIR"
fi

echo -e "Install mode: ${YELLOW}$INSTALL_MODE${NC}"
echo -e "Install directory: ${YELLOW}$INSTALL_DIR${NC}"
echo

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}[OK]${NC} Python 3 found: $PYTHON_VERSION"

# Check git (required for remote install)
if [[ "$INSTALL_MODE" == "remote" ]]; then
    if ! command -v git &> /dev/null; then
        echo -e "${RED}Error: git is required but not installed.${NC}"
        exit 1
    fi
    echo -e "${GREEN}[OK]${NC} Git found"
fi

# Clone repository if remote install
if [[ "$INSTALL_MODE" == "remote" ]]; then
    echo -e "\n${YELLOW}[1/5]${NC} Cloning repository..."

    if [[ -d "$INSTALL_DIR" ]]; then
        if [[ -d "$INSTALL_DIR/.git" ]]; then
            echo -e "  Repository already exists, updating..."
            git -C "$INSTALL_DIR" pull --quiet
            echo -e "  ${GREEN}Updated${NC} $INSTALL_DIR"
        else
            echo -e "${RED}Error: $INSTALL_DIR exists but is not a git repository${NC}"
            echo -e "Remove it manually or choose a different directory with -d"
            exit 1
        fi
    else
        mkdir -p "$(dirname "$INSTALL_DIR")"
        git clone --quiet "$REPO_URL" "$INSTALL_DIR"
        echo -e "  ${GREEN}Cloned${NC} to $INSTALL_DIR"
    fi

    STEP_OFFSET=1
else
    STEP_OFFSET=0
fi

TOTAL_STEPS=$((4 + STEP_OFFSET))

# Create virtual environment
STEP=$((1 + STEP_OFFSET))
echo -e "\n${YELLOW}[$STEP/$TOTAL_STEPS]${NC} Creating virtual environment..."
if [[ -d "$INSTALL_DIR/.venv" ]]; then
    echo -e "  Virtual environment already exists, skipping..."
else
    python3 -m venv "$INSTALL_DIR/.venv"
    echo -e "  ${GREEN}Created${NC} $INSTALL_DIR/.venv"
fi

# Install dependencies
STEP=$((2 + STEP_OFFSET))
echo -e "\n${YELLOW}[$STEP/$TOTAL_STEPS]${NC} Installing Python dependencies..."
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip -q
"$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q
echo -e "  ${GREEN}Installed${NC} all dependencies from requirements.txt"

# Add to PATH (optional)
STEP=$((3 + STEP_OFFSET))
echo -e "\n${YELLOW}[$STEP/$TOTAL_STEPS]${NC} Setting up 'ab' command..."

INSTALL_PATH="/usr/local/bin/ab"
if [[ -L "$INSTALL_PATH" || -f "$INSTALL_PATH" ]]; then
    echo -e "  ${YELLOW}Warning:${NC} $INSTALL_PATH already exists"
    if [[ "$SKIP_CONFIRM" == "yes" ]]; then
        REPLY="y"
    else
        read -p "  Overwrite? [y/N] " -r REPLY || REPLY=""
    fi
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo rm -f "$INSTALL_PATH"
        sudo ln -s "$INSTALL_DIR/bin/ab" "$INSTALL_PATH"
        echo -e "  ${GREEN}Symlink updated${NC}"
    else
        echo -e "  Skipped symlink creation"
    fi
else
    if [[ "$SKIP_CONFIRM" == "yes" ]]; then
        REPLY="y"
    else
        read -p "  Create symlink at $INSTALL_PATH? [Y/n] " -r REPLY || REPLY=""
    fi
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        sudo ln -s "$INSTALL_DIR/bin/ab" "$INSTALL_PATH"
        echo -e "  ${GREEN}Symlink created:${NC} $INSTALL_PATH -> $INSTALL_DIR/bin/ab"
    else
        echo -e "  Skipped. You can add to PATH manually:"
        echo -e "    export PATH=\"$INSTALL_DIR/bin:\$PATH\""
    fi
fi

# Setup bash completion (optional)
STEP=$((4 + STEP_OFFSET))
echo -e "\n${YELLOW}[$STEP/$TOTAL_STEPS]${NC} Setting up bash completion..."

COMPLETION_DIR="$HOME/.local/share/bash-completion/completions"
COMPLETION_FILE="$COMPLETION_DIR/ab"

if [[ -L "$COMPLETION_FILE" || -f "$COMPLETION_FILE" ]]; then
    echo -e "  Bash completion already configured"
else
    if [[ "$SKIP_CONFIRM" == "yes" ]]; then
        REPLY="y"
    else
        read -p "  Enable bash autocompletion? [Y/n] " -r REPLY || REPLY=""
    fi
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        mkdir -p "$COMPLETION_DIR"
        ln -s "$INSTALL_DIR/completions/ab.bash-completion" "$COMPLETION_FILE"
        echo -e "  ${GREEN}Bash completion enabled${NC}"
        echo -e "  ${YELLOW}Note:${NC} Restart your shell or run: source ~/.bashrc"
    else
        echo -e "  Skipped bash completion setup"
    fi
fi

# Setup environment variable reminder
echo -e "\n${BLUE}============================================${NC}"
echo -e "${GREEN}  Installation complete!${NC}"
echo -e "${BLUE}============================================${NC}"
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
