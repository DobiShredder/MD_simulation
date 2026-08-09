#!/usr/bin/env bash
set -euo pipefail

tutorial_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
analysis_root=$(cd "$tutorial_dir/../.." && pwd -P)

export TUTORIAL_DIR="$tutorial_dir"
export EXPECTED_OUTPUTS="sasa_total.dat sasa_byres.dat"

exec "$analysis_root/_run_cpptraj.sh" "$@"
