#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

GREEN='\033[0;32m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $*"; }

usage() {
    cat <<EOF
Usage: $(basename "$0")

Set up the RenderFarm project:
  1. Copy users config if not already present
  2. Install server dependencies (uv sync)
  3. Install worker dependencies (uv sync)
  4. Build the Blender addon .zip

Run this first when cloning the project on a new machine.
EOF
    exit 0
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && usage

log "Checking for uv ..."
if ! command -v uv &>/dev/null; then
    echo "ERROR: 'uv' is required. Install from https://github.com/astral-sh/uv"
    exit 1
fi

log "=== Step 1: User config ==="
if [[ ! -f "$PROJECT_DIR/config/users.yaml" ]]; then
    cp "$PROJECT_DIR/config/users.example.yaml" "$PROJECT_DIR/config/users.yaml"
    log "  Created config/users.yaml from example. Edit it to set your passwords."
else
    log "  config/users.yaml already exists, skipping."
fi

log "=== Step 2: Server dependencies ==="
cd "$PROJECT_DIR/server"
uv sync
log "  Server dependencies installed."

log "=== Step 3: Worker dependencies ==="
cd "$PROJECT_DIR/worker"
uv sync
log "  Worker dependencies installed."

log "=== Step 4: Build addon ==="
bash "$SCRIPT_DIR/build-addon.sh"

cd "$PROJECT_DIR"
log ""
log "Setup complete."
log ""
log "Next steps:"
log "  1. Edit config/users.yaml with real passwords"
log "  2. Install systemd services: sudo script/install-services.sh"
log "  3. Or run manually:"
log "     - Server: cd server && uv run python main.py"
log "     - Worker: cd worker && uv run python main.py"
