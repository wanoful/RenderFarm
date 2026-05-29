#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SYSTEMD_DIR="/etc/systemd/system"
SERVICE_SRC="$PROJECT_DIR/service"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; }

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Install RenderFarm systemd services.

Options:
  --server-url URL        Server URL for worker (default: http://127.0.0.1:8000)
  --worker-user USER      Worker auth username (default: worker)
  --worker-pass PASS      Worker auth password (default: worker)
  --worker-name NAME      Worker name (default: worker1)
  --no-enable             Copy services but do not enable/start them
  --dry-run               Show what would be done without doing it
  -h, --help              Show this help

Service files are installed from: $SERVICE_SRC
Installation directory:      $PROJECT_DIR
EOF
    exit 0
}

SERVER_URL="http://127.0.0.1:8000"
WORKER_USER="worker"
WORKER_PASS="worker"
WORKER_NAME="worker1"
ENABLE=true
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --server-url)   SERVER_URL="$2"; shift 2 ;;
        --worker-user)  WORKER_USER="$2"; shift 2 ;;
        --worker-pass)  WORKER_PASS="$2"; shift 2 ;;
        --worker-name)  WORKER_NAME="$2"; shift 2 ;;
        --no-enable)    ENABLE=false; shift ;;
        --dry-run)      DRY_RUN=false; shift ;;
        --real)         DRY_RUN=false; shift ;;
        -h|--help)      usage ;;
        *) err "Unknown option: $1"; usage ;;
    esac
done

if [[ $EUID -ne 0 ]]; then
    err "This script must be run as root (use sudo)."
    exit 1
fi

if [[ ! -d "$SERVICE_SRC" ]]; then
    err "Service directory not found: $SERVICE_SRC"
    exit 1
fi

install_service() {
    local src="$1"
    local name
    name="$(basename "$src")"
    local dst="$SYSTEMD_DIR/$name"

    log "Installing $name ..."

    if $DRY_RUN; then
        log "  [dry-run] Would copy $src -> $dst with substitutions"
        return
    fi

    sed \
        -e "s|{{INSTALL_DIR}}|$PROJECT_DIR|g" \
        -e "s|http://127.0.0.1:8000|$SERVER_URL|" \
        -e "s|Environment=RENDERFARM_USER=.*|Environment=RENDERFARM_USER=$WORKER_USER|" \
        -e "s|Environment=RENDERFARM_PASS=.*|Environment=RENDERFARM_PASS=$WORKER_PASS|" \
        -e "s|Environment=RENDERFARM_WORKER=.*|Environment=RENDERFARM_WORKER=$WORKER_NAME|" \
        "$src" > "$dst"

    chmod 644 "$dst"
    log "  -> $dst"
}

for svc in "$SERVICE_SRC"/*.service; do
    [[ -f "$svc" ]] || continue
    install_service "$svc"
done

if $DRY_RUN; then
    log "[dry-run] Would run: systemctl daemon-reload"
    if $ENABLE; then
        log "[dry-run] Would run: systemctl enable --now renderfarm-server renderfarm-worker"
    fi
    exit 0
fi

log "Reloading systemd ..."
systemctl daemon-reload

if $ENABLE; then
    log "Enabling and starting services ..."
    systemctl enable --now renderfarm-server.service renderfarm-worker.service
    log "Done. Check status with: systemctl status renderfarm-server renderfarm-worker"
else
    log "Services copied. Enable and start manually with:"
    log "  sudo systemctl enable --now renderfarm-server renderfarm-worker"
fi
