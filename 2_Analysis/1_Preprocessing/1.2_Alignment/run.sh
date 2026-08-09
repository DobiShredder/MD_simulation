#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
analysis_root=$(cd "$script_dir/../.." && pwd)

export TUTORIAL_DIR="$script_dir"
export EXPECTED_OUTPUTS="rmsd_before.dat rmsd_after.dat average.pdb stripped.parm7 aligned.nc"

exec "$analysis_root/_run_cpptraj.sh" "$@"
