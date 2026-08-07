#!/usr/bin/env bash
set -euo pipefail

sim_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
amber_engine=${AMBER_ENGINE:-sander}
cd "$sim_root"

for command_name in tleap "$amber_engine" cpptraj; do
    command -v "$command_name" >/dev/null || {
        echo "ERROR: required command not found: $command_name" >&2
        exit 1
    }
done

mkdir -p common_files bstates
tleap -f amber/leap.in > common_files/leap.log
"$amber_engine" -O -i amber/minimize.in -o common_files/minimize.out \
    -p common_files/system.parm7 -c common_files/system.rst7 \
    -r common_files/minimized.rst7
"$amber_engine" -O -i amber/equilibrate.in -o common_files/equilibrate.out \
    -p common_files/system.parm7 -c common_files/minimized.rst7 \
    -r bstates/basis.rst7

echo "Prepared bstates/basis.rst7 with $amber_engine."
