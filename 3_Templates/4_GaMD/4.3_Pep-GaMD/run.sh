#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
    echo "Usage: ./run.sh [--preparation-only | --production-only] [--segments START-END] [--dry-run]"
    echo
    echo "Run dual-boost Pep-GaMD with the configured peptide mask."
    echo
    echo "Options:"
    echo "  --preparation-only  Run through GaMD parameter preparation and stop."
    echo "  --production-only   Run only configured production segments."
    echo "  --segments RANGE    Run an inclusive 1-based segment range."
    echo "  --dry-run      Print engine commands without running them."
    echo "  -h, --help     Show this help message and exit."
    exit 0
fi
bash run_gamd.sh pepgamd "$@"
