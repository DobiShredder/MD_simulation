#!/usr/bin/env bash
set -euo pipefail

simulation_dir="../../../1_Simulation/2_US/us"
windows="$simulation_dir/work"
output=output
python=python3

if [[ ! -d "$windows" ]]; then
    echo "Error: umbrella window output not found: $windows" >&2
    exit 1
fi

if ! command -v "$python" >/dev/null 2>&1; then
    echo "Error: Python executable not found: $python" >&2
    exit 1
fi

"$python" prepare.py

echo "Created WHAM inputs: $output"
