#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 0 ]]; then
    echo "Usage: $0" >&2
    exit 2
fi

# Edit the two paths below to analyze a different system.
simulation_dir="../../../1_Simulation/1_MD/1.1_Soluble_Protein"
topology="$simulation_dir/work/system.parm7"
trajectory="$simulation_dir/work/production.nc"

cpptraj=cpptraj
input_file=inputs/cpptraj.in
output_dir=output

if ! command -v "$cpptraj" >/dev/null 2>&1; then
    echo "Error: cpptraj not found." >&2
    exit 1
fi
if [[ ! -f "$input_file" ]]; then
    echo "Error: cpptraj input not found: $input_file" >&2
    exit 1
fi
if [[ ! -s "$topology" ]]; then
    echo "Error: Chignolin topology not found: $topology" >&2
    exit 1
fi
if [[ ! -s "$trajectory" ]]; then
    echo "Error: Chignolin trajectory not found: $trajectory" >&2
    exit 1
fi

mkdir -p "$output_dir"
echo "Analyzing the Chignolin trajectory with cpptraj."

cd "$output_dir"
topology="../$topology"
trajectory="../$trajectory"
input_file="../$input_file"
if ! "$cpptraj" \
    -p "$topology" \
    -y "$trajectory" \
    -i "$input_file" \
    > cpptraj.log 2>&1; then
    echo "Error: cpptraj failed: $output_dir/cpptraj.log" >&2
    exit 1
fi

echo "Analysis results: $output_dir"
