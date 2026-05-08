#!/usr/bin/env bash
# macOS double-clickable wrapper around start_mvp.sh.
# Make sure this file has the executable bit set:
#   chmod +x Start_TRIBE_Review.command

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec /usr/bin/env bash "$DIR/start_mvp.sh" "$@"
