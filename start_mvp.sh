#!/usr/bin/env bash
# Cross-platform launcher for TRIBE Review MVP on macOS / Linux.
# Mirrors start_mvp.ps1: detect Python 3.11, create .venv, install
# requirements.txt, optionally bootstrap models, then start uvicorn.

set -euo pipefail

NO_BROWSER=0
for arg in "$@"; do
    case "$arg" in
        --no-browser) NO_BROWSER=1 ;;
        *) ;;
    esac
done

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

VENV_DIR="$APP_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
REQUIREMENTS_FILE="$APP_DIR/requirements.txt"
BOOTSTRAP_SCRIPT="$APP_DIR/bootstrap_models.py"
BOOTSTRAP_READY_FILE="$APP_DIR/.bootstrap/models-ready.json"
HOST_ADDRESS="127.0.0.1"
PREFERRED_PORT="${TRIBE_PORT:-8000}"

stop_with_message() {
    printf '\n\033[31m%s\033[0m\n\n' "$1" >&2
    exit 1
}

find_python311() {
    for cmd in python3.11 python3 python; do
        if command -v "$cmd" >/dev/null 2>&1; then
            ver="$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "")"
            if [ "$ver" = "3.11" ]; then
                printf '%s\n' "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

create_venv() {
    local py
    if ! py="$(find_python311)"; then
        stop_with_message "Python 3.11 not found. Install it (brew install python@3.11 or apt/pacman/dnf equivalent) and run start_mvp.sh again."
    fi
    "$py" -m venv "$VENV_DIR"
}

if [ ! -x "$VENV_PYTHON" ]; then
    printf '\n\033[36mCreating local Python environment: .venv\033[0m\n'
    create_venv
    if [ ! -x "$VENV_PYTHON" ]; then
        stop_with_message "Could not create .venv. Install Python 3.11 and run start_mvp.sh again."
    fi
fi

PY="$VENV_PYTHON"

deps_ok() {
    "$PY" -c "import re, sys; import fastapi, uvicorn, torch; m = re.match(r'(\d+)\.(\d+)\.(\d+)', torch.__version__); v = tuple(map(int, m.groups())) if m else (0, 0, 0); sys.exit(0 if (2, 5, 1) <= v < (2, 7, 0) else 1); import tribev2" >/dev/null 2>&1
}

if ! deps_ok; then
    if [ ! -f "$REQUIREMENTS_FILE" ]; then
        stop_with_message "requirements.txt not found. Re-clone or re-download the repository."
    fi
    printf '\n\033[36mInstalling Python dependencies. First run can take several minutes.\033[0m\n'
    "$PY" -m pip install --upgrade pip
    "$PY" -m pip install -r "$REQUIREMENTS_FILE"
fi

if [ ! -f "$BOOTSTRAP_READY_FILE" ]; then
    if [ ! -f "$BOOTSTRAP_SCRIPT" ]; then
        stop_with_message "bootstrap_models.py not found. Re-clone or re-download the repository."
    fi
    "$PY" "$BOOTSTRAP_SCRIPT"
    printf '\n\033[32mInitial setup finished successfully. Run ./start_mvp.sh once more to start the app.\033[0m\n'
    exit 0
fi

# Pick an available port (preferred first, then 8001-8010).
pick_port() {
    local p
    for p in "$PREFERRED_PORT" 8001 8002 8003 8004 8005 8006 8007 8008 8009 8010; do
        if ! "$PY" -c "import socket,sys; s=socket.socket();
try: s.bind(('$HOST_ADDRESS', $p))
except OSError: sys.exit(1)
finally: s.close()" >/dev/null 2>&1; then
            continue
        fi
        printf '%s\n' "$p"
        return 0
    done
    return 1
}

PORT="$(pick_port || true)"
if [ -z "$PORT" ]; then
    stop_with_message "Could not find a free port between 8000 and 8010."
fi

URL="http://${HOST_ADDRESS}:${PORT}"
printf '\n\033[36mStarting TRIBE Review on %s\033[0m\n' "$URL"

if [ "$NO_BROWSER" = "0" ]; then
    (
        for _ in $(seq 1 240); do
            if "$PY" -c "import urllib.request; urllib.request.urlopen('$URL', timeout=2)" >/dev/null 2>&1; then
                if command -v open >/dev/null 2>&1; then
                    open "$URL"
                elif command -v xdg-open >/dev/null 2>&1; then
                    xdg-open "$URL" >/dev/null 2>&1 || true
                fi
                exit 0
            fi
            sleep 0.75
        done
    ) &
fi

exec "$PY" -m uvicorn app:app --host "$HOST_ADDRESS" --port "$PORT"
