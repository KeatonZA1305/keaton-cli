#!/bin/bash
# Keaton CLI Installer
# Supports macOS, Linux, and Windows (via WSL or Git Bash)

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Installing Keaton CLI...${NC}"

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed.${NC}" >&2
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
REQUIRED_VERSION="3.12"
if (( $(echo "$PYTHON_VERSION < $REQUIRED_VERSION" | bc -l) )); then
    echo -e "${RED}Error: Python $REQUIRED_VERSION or higher is required. You have $PYTHON_VERSION.${NC}" >&2
    exit 1
fi

# Check if pip is available
if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
    echo -e "${RED}Error: pip is required but not installed.${NC}" >&2
    exit 1
fi

# Determine pip command
if command -v pip3 &> /dev/null; then
    PIP=pip3
else
    PIP=pip
fi

# Install the package in development mode
echo -e "${YELLOW}Installing Keaton CLI via pip...${NC}"
$PIP install -e .

# Check if Base44 CLI is installed
if ! command -v base44 &> /dev/null; then
    echo -e "${YELLOW}Base44 CLI not found. Installing Base44 CLI...${NC}"
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}Error: npm is required to install Base44 CLI. Please install Node.js and npm.${NC}" >&2
        echo -e "You can install Node.js from: https://nodejs.org/${NC}" >&2
        exit 1
    fi
    npm install -g base44@latest
    echo -e "${GREEN}Base44 CLI installed successfully.${NC}"
else
    echo -e "${GREEN}Base44 CLI is already installed.${NC}"
fi

# Create configuration directory
KEATON_DIR="$HOME/.keaton"
if [ ! -d "$KEATON_DIR" ]; then
    mkdir -p "$KEATON_DIR"
    echo -e "${GREEN}Created configuration directory: $KEATON_DIR${NC}"
fi

# Create default config if it doesn't exist
CONFIG_FILE="$KEATON_DIR/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    cat > "$CONFIG_FILE" << EOF
{
  "theme": "cyan",
  "default_agent": null,
  "app_id": null,
  "agent_name": null,
  "stream_enabled": true,
  "markdown_enabled": true,
  "history_enabled": true
}
EOF
    echo -e "${GREEN}Created default configuration: $CONFIG_FILE${NC}"
fi

# Add shell completion instructions
SHELL_NAME=$(basename "$SHELL")
case "$SHELL_NAME" in
    bash)
        echo -e "${YELLOW}To enable bash completion, add this to your ~/.bashrc:${NC}"
        echo "  eval \"\$(register-python-argcomplete keaton)\""
        ;;
    zsh)
        echo -e "${YELLOW}To enable zsh completion, add this to your ~/.zshrc:${NC}"
        echo "  autoload -U compinit && compinit"
        echo "  eval \"\$(register-python-argcomplete keaton)\""
        ;;
    fish)
        echo -e "${YELLOW}To enable fish completion, run:${NC}"
        echo "  register-python-argcomplete keaton | source"
        ;;
    *)
        echo -e "${YELLOW}For shell completion, consult your shell's documentation for argcomplete.${NC}"
        ;;
esac

echo -e "${GREEN}Keaton CLI installed successfully!${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Login to Base44: ${GREEN}keaton login${NC}"
echo -e "  2. Start chatting: ${GREEN}keaton chat${NC}"
echo -e "  3. Get help: ${GREEN}keaton --help${NC}"
