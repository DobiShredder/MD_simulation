#!/usr/bin/env bash
set -euo pipefail

python=python3

if ! command -v "$python" >/dev/null 2>&1; then
    echo "Error: Python executable not found: $python" >&2
    exit 1
fi

"$python" prepare.py
