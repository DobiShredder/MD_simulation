#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
    cat <<'EOF'
Usage: ./run.sh [--preparation-only | --production-only] [--segment N | --segments START-END] [--dry-run]

Run preparation and restart-safe segmented OPES_METAD production.

Options:
  --segment N  Run only one 1-based production segment.
  --segments RANGE  Run an inclusive 1-based production segment range.
  --preparation-only  Run through equilibration and stop.
  --production-only   Run production from completed equilibration.
  --dry-run    Print planned commands without running them.
  -h, --help   Show this help message and exit.
EOF
    exit 0
fi
exec ../run_metad.sh opes-metad "$@"
