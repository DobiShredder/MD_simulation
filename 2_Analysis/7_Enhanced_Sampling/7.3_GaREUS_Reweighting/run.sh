#!/usr/bin/env bash
set -euo pipefail

simulation_dir="../../../1_Simulation/3_REMD/3.5_GaREUS"
simulation_work="$simulation_dir/work"
output=output
python=python3

if [[ ! -s "$simulation_work/states.tsv" ]]; then
    echo "Error: Run the GaREUS simulation first: $simulation_work/states.tsv" >&2
    exit 1
fi

if ! command -v "$python" >/dev/null 2>&1; then
    echo "Error: Python executable not found: $python" >&2
    exit 1
fi

"$python" prepare.py

echo "Created GaREUS reweighting inputs: $output"
