#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$(dirname "$WEST_ISTATE_DATA_REF")"
ln -s "$WEST_BSTATE_DATA_REF" "$WEST_ISTATE_DATA_REF"
