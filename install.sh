#!/usr/bin/env bash
# acme-speedtest installer
# Usage: curl -fsSL https://raw.githubusercontent.com/acmeagentsupply/acme-speedtest/main/install.sh | bash
set -euo pipefail

INSTALL_DIR="${HOME}/.local/bin"
SCRIPT_URL="https://raw.githubusercontent.com/acmeagentsupply/acme-speedtest/main/speedtest.py"
INSTALL_PATH="${INSTALL_DIR}/acme-speedtest"

printf '\n\033[1m⚡ acme-speedtest installer\033[0m\n\n'

# Check Python
if ! command -v python3 &>/dev/null; then
  printf '\033[31m✗ Python 3 is required. Install it from python.org.\033[0m\n'
  exit 1
fi

# Create install dir
mkdir -p "${INSTALL_DIR}"

# Download
printf '  Downloading acme-speedtest...\n'
curl -fsSL "${SCRIPT_URL}" -o "${INSTALL_PATH}"
chmod +x "${INSTALL_PATH}"

# Add shebang wrapper so it runs as a command
cat > "${INSTALL_PATH}" << 'WRAPPER'
#!/usr/bin/env python3
WRAPPER
curl -fsSL "${SCRIPT_URL}" >> "${INSTALL_PATH}"
chmod +x "${INSTALL_PATH}"

# Check PATH
if [[ ":${PATH}:" != *":${INSTALL_DIR}:"* ]]; then
  printf '\n  \033[33m⚠\033[0m  Add %s to your PATH:\n' "${INSTALL_DIR}"
  printf '     echo '\''export PATH="$HOME/.local/bin:$PATH"'\'' >> ~/.zshrc && source ~/.zshrc\n\n'
fi

printf '\n\033[32m✓\033[0m  Installed to %s\n' "${INSTALL_PATH}"
printf '\n  Run it:\n'
printf '     \033[1macme-speedtest\033[0m\n\n'
printf '  Or:\n'
printf '     \033[1macme-speedtest --help\033[0m\n\n'
