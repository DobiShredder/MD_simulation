#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
analysis_root=$(cd "$script_dir/../.." && pwd)

export TUTORIAL_DIR="$script_dir"
export EXPECTED_OUTPUTS="rmsd_first.dat rmsd_average.dat rmsf_byres.dat rg.dat average.pdb"

exec "$analysis_root/_run_cpptraj.sh" "$@"
