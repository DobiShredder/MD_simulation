#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 [--dry-run] KCSA.pdb" >&2
}

die() {
    echo "Error: $*" >&2
    exit 1
}

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi

if [[ $# -ne 1 ]]; then
    usage
    exit 2
fi

# Input and output paths
protein_pdb=$1
python=${PYTHON:-python3}
composition="POPC=90,POPE=5,CHOL=5"
xy_padding=25
water_padding=20
protein_lipid_distance=2.0
structure_dir=structure
work_dir=${WORK_DIR:-work}
output_pdb="$work_dir/system-coordinates.pdb"

if (( dry_run )); then
    printf 'mkdir -p %q\n' "$work_dir"
    printf '%q %q %q %q %q %q %q \\\n' \
        "$python" \
        build_membrane.py \
        "$protein_pdb" \
        "$structure_dir/POPC.gro" \
        "$structure_dir/POPE.gro" \
        "$structure_dir/CHOL15.gro" \
        "$output_pdb"
    printf '  --composition %q \\\n' "$composition"
    printf '  --xy-padding %q \\\n' "$xy_padding"
    printf '  --water-padding %q \\\n' "$water_padding"
    printf '  --protein-lipid-distance %q\n' "$protein_lipid_distance"
    exit 0
fi

# Input and dependency checks
if [[ ! -f "$protein_pdb" ]]; then
    die "KcsA PDB not found: $protein_pdb"
fi

if ! command -v "$python" >/dev/null 2>&1; then
    die "Python executable not found: $python"
fi

for coordinate in POPC.gro POPE.gro CHOL15.gro; do
    if [[ ! -f "$structure_dir/$coordinate" ]]; then
        die "Bilayer coordinates are missing. Run ./download.sh first."
    fi
done

if ! "$python" -c "import numpy" >/dev/null 2>&1; then
    die "Cannot import NumPy. Activate the ambertools26 environment."
fi

# Replicate the equilibrated Lipid21 patch and insert KcsA.
mkdir -p "$work_dir"

"$python" \
    build_membrane.py \
    "$protein_pdb" \
    "$structure_dir/POPC.gro" \
    "$structure_dir/POPE.gro" \
    "$structure_dir/CHOL15.gro" \
    "$output_pdb" \
    --composition "$composition" \
    --xy-padding "$xy_padding" \
    --water-padding "$water_padding" \
    --protein-lipid-distance "$protein_lipid_distance"

echo "Coordinate build output: $output_pdb"
