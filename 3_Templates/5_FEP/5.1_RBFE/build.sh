#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
    echo "Usage: ./build.sh [--config FILE] [--dry-run] PROTEIN.pdb"
    echo
    echo "Build RBFE complex/solvent systems from a reviewed protein PDB and the"
    echo "precharged ligand A/B parameters configured in config.toml."
    echo
    echo "Options:"
    echo "  --config FILE  Read settings from FILE instead of config.toml."
    echo "  --dry-run      Print the planned build without running external programs."
    echo "  -h, --help     Show this help message and exit."
    exit 0
fi
bash ../build_fep.sh rbfe "$@"
