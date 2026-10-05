#!/usr/bin/env bash
set -euo pipefail

python=python3

if ! command -v "$python" >/dev/null 2>&1; then
    echo "Error: Python executable not found: $python" >&2
    exit 1
fi

if [[ "${MD_WRITER_PARENT:-}" != "$PPID" || "${MD_WRITER_ENTRY:-}" != "$0" ]]; then
    exec "$python" writer_guard.py \
        --registry output --write "output" \
        -- "$0" "$@"
fi

"$python" prepare.py
