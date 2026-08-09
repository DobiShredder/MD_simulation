#!/usr/bin/env bash
set -euo pipefail

tutorial_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
analysis_root=$(cd "$tutorial_dir/../.." && pwd -P)

export TUTORIAL_DIR="$tutorial_dir"
export EXPECTED_OUTPUTS="contact_count.dat contact_residue_series.dat"

exec "$analysis_root/_run_cpptraj.sh" "$@"
