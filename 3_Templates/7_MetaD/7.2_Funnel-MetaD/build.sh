#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
    cat <<'EOF'
Usage: ./build.sh [--config FILE] [--dry-run] COMPLEX.pdb

Build a protein-ligand AMBER system and resolve the configured funnel geometry.

Options:
  --config FILE  Read settings from FILE instead of config.toml.
  --dry-run      Print the planned build without running external programs.
  -h, --help     Show this help message and exit.
EOF
    exit 0
fi
exec ../build_metad.sh funnel-metad "$@"
