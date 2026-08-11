#!/usr/bin/env bash
set -euo pipefail

die() {
    echo "Error: $*" >&2
    exit 1
}

work_dir=${WORK_DIR:-"work"}
tleap=${TLEAP:-tleap}

if [[ "$work_dir" != /* ]]; then
    work_dir="$(pwd)/$work_dir"
fi

command -v "$tleap" >/dev/null 2>&1 || die "tleap not found: $tleap"
command -v python3 >/dev/null 2>&1 || die "python3 not found."
mkdir -p "$work_dir"
cp inputs/tleap.in "$work_dir/tleap.in"

if ! (
    cd "$work_dir"
    "$tleap" -f tleap.in > leap.log 2>&1
); then
    die "tleap failed: $work_dir/leap.log"
fi
for output in system.parm7 system.rst7 system.pdb; do
    [[ -s "$work_dir/$output" ]] || die "build Output not found: $work_dir/$output"
done
python3 "check_topology.py" "$work_dir/system.parm7" "$work_dir/cv_atoms.tsv"
echo "Topology build Completed: $work_dir"
