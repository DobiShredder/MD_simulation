#!/usr/bin/env bash
set -euo pipefail

tutorial_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
analysis_root=$(cd "$tutorial_dir/../.." && pwd -P)

export TUTORIAL_DIR="$tutorial_dir"
export EXPECTED_OUTPUTS="protein_hbond_count.dat protein_hbond_average.dat water_hbond_count.dat water_hbond_average.dat"

exec "$analysis_root/_run_cpptraj.sh" "$@"
