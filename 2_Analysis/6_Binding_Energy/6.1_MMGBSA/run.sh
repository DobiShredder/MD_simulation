#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 0 ]]; then
    echo "Usage: $0" >&2
    exit 2
fi

# Edit the paths and ligand mask below for a different protein-ligand system.
simulation_dir="../../../1_Simulation/1_MD/1.2_Protein_Ligand"
solvated_topology="$simulation_dir/work/system.parm7"
trajectory="$simulation_dir/work/production.nc"
ligand_mask=:JZ4

ante_mmpbsa=ante-MMPBSA.py
mmpbsa=MMPBSA.py
input_file=inputs/mmpbsa.in
output_dir=output

if [[ "${MD_WRITER_PARENT:-}" != "$PPID" || "${MD_WRITER_ENTRY:-}" != "$0" ]]; then
    exec "python3" writer_guard.py \
        --registry output --write "$output_dir" \
        -- "$0" "$@"
fi


for executable in "$ante_mmpbsa" "$mmpbsa"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        echo "Error: Executable not found: $executable" >&2
        exit 1
    fi
done
if [[ ! -s "$input_file" ]]; then
    echo "Error: MMPBSA.py input is missing: $input_file" >&2
    exit 1
fi
if [[ ! -s "$solvated_topology" ]]; then
    echo "Error: T4 lysozyme–JZ4 topology not found: $solvated_topology" >&2
    exit 1
fi
if [[ ! -s "$trajectory" ]]; then
    echo "Error: T4 lysozyme–JZ4 trajectory not found: $trajectory" >&2
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
(
cd "$output_dir"
solvated_topology="../$solvated_topology"
trajectory="../$trajectory"
input_file="../$input_file"

echo "Generating complex, receptor, and ligand topologies; log: $output_dir/topology.log"
if ! "$ante_mmpbsa" \
    -p "$solvated_topology" \
    -c complex.parm7 \
    -r receptor.parm7 \
    -l ligand.parm7 \
    -s ':WAT,Na+,Cl-' \
    -n "$ligand_mask" \
    --radii mbondi2 \
    > topology.log 2>&1; then
    echo "Error: MMPBSA topology generation failed: $output_dir/topology.log" >&2
    exit 1
fi

for topology_file in complex.parm7 receptor.parm7 ligand.parm7; do
    if [[ ! -s "$topology_file" ]]; then
        echo "Error: MMPBSA topology was not created: $output_dir/$topology_file; log: $output_dir/topology.log" >&2
        exit 1
    fi
done
echo "Completed: MMPBSA topology generation ($output_dir)"
printf '\n'

echo "Calculating MM/GBSA for 100 frames."
if ! "$mmpbsa" \
    -O \
    -i "$input_file" \
    -sp "$solvated_topology" \
    -cp complex.parm7 \
    -rp receptor.parm7 \
    -lp ligand.parm7 \
    -y "$trajectory" \
    -o final_results.dat \
    -do final_decomposition.dat \
    -eo energy.csv \
    -deo decomposition.csv \
    > mmpbsa.log 2>&1; then
    echo "Error: MM/GBSA Calculation failed: $output_dir/mmpbsa.log" >&2
    exit 1
fi

for output_file in final_results.dat final_decomposition.dat energy.csv decomposition.csv; do
    if [[ ! -s "$output_file" ]]; then
        echo "Error: MMPBSA output was not created: $output_dir/$output_file; log: $output_dir/mmpbsa.log" >&2
        exit 1
    fi
done

)

python3 result_generation.py "$generation_dir" output
output_dir=output
echo "MM/GBSA results: $output_dir"
