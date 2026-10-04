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
if [[ ! -s "$input_file" ]]; then
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

if [[ -e .output.pending || -L .output.pending ]]; then
    echo "Error: analysis publication is incomplete; inspect .output.pending." >&2
    exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: Python executable not found: python3" >&2
    exit 1
fi

generation_dir=$(mktemp -d .output.generation.XXXXXX)
cleanup_generation() {
    status=$?
    if [[ -d "$generation_dir" ]]; then
        if [[ $status -ne 0 ]]; then
            echo "Error: analysis failed; previous output is unchanged. Recent generation logs:" >&2
            for log in "$generation_dir"/*.log; do
                if [[ -f "$log" ]]; then
                    echo "Log: $log" >&2
                    tail -n 20 "$log" >&2
                fi
            done
        fi
        case "$generation_dir" in
            .output.generation.*) rm -rf -- "$generation_dir" ;;
        esac
    fi
    exit "$status"
}
trap cleanup_generation EXIT
output_dir=$generation_dir
echo "Extracting dihedral features with cpptraj: $output_dir/cpptraj.log"
(
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

if [[ ! -s phi_psi.dat ]]; then
    echo "Error: feature extraction output missing or empty: $output_dir/phi_psi.dat; see $output_dir/cpptraj.log" >&2
    exit 1
fi

)

python3 result_generation.py "$generation_dir" output
output_dir=output
echo "Dihedral feature: $output_dir/phi_psi.dat"
