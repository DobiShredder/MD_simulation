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

mkdir -p "$output_dir"
cd "$output_dir"
solvated_topology="../$solvated_topology"
trajectory="../$trajectory"
input_file="../$input_file"

echo "Generating complex, receptor, and ligand topologies."
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

echo "MM/GBSA results: $output_dir"
