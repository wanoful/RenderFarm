#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

ADDON_SRC="$PROJECT_DIR/RFAddon"
DIST_DIR="$PROJECT_DIR/dist"

GREEN='\033[0;32m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $*"; }

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Package the Blender addon into a distributable .zip file.

Options:
  -o, --output FILE     Output path (default: dist/RFAddon.zip)
  -h, --help            Show this help
EOF
    exit 0
}

OUTPUT=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -o|--output) OUTPUT="$2"; shift 2 ;;
        -h|--help)   usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

if [[ ! -d "$ADDON_SRC" ]]; then
    echo "ERROR: Addon source directory not found: $ADDON_SRC"
    exit 1
fi

if [[ -z "$OUTPUT" ]]; then
    mkdir -p "$DIST_DIR"
    OUTPUT="$DIST_DIR/RFAddon.zip"
fi

OUTPUT="$(cd "$(dirname "$OUTPUT")" && pwd)/$(basename "$OUTPUT")"
mkdir -p "$(dirname "$OUTPUT")"

log "Packaging addon from $ADDON_SRC"

cd "$ADDON_SRC"
if command -v zip &>/dev/null; then
    zip -r "$OUTPUT" . -x "__pycache__/*" "*.pyc" ".DS_Store"
else
    echo "ERROR: 'zip' command not found. Install it with your package manager."
    exit 1
fi
cd "$PROJECT_DIR"

log "Addon packaged: $OUTPUT"
