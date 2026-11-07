#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

dry_run=0
window_config=../config.toml
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) dry_run=1; shift ;;
        --config)
            if [[ $# -lt 2 ]]; then
                echo "Error: --config requires a file." >&2
                exit 2
            fi
            window_config=$2
            shift 2
            ;;
        -h|--help)
            cat <<'EOF'
Usage: ./build.sh [--config FILE] [--dry-run]

Create umbrella-window directories from the rMD seed restarts.

Options:
  --config FILE  Read [umbrella] centers/force_constants from FILE
                 (default: ../config.toml; use the file given to rmd/anal.py).
  --dry-run      Validate the umbrella windows and print the planned generator.
  -h, --help     Show this help message and exit.
EOF
            exit 0
            ;;
        *)
            echo "Usage: ./build.sh [--config FILE] [--dry-run]" >&2
            exit 2
            ;;
    esac
done

die() {
    echo "Error: $*" >&2
    exit 1
}

python=${PYTHON:-python3}
seed_dir=../rmd/work/seeds
seed_metadata="$seed_dir/seeds.tsv"
topology=../work/system.parm7
config=../work/resolved_config.toml
window_root=${WORK_DIR:-work}
if [[ ! -s "$config" ]]; then
    die "Resolved config not found: $config. Run the root build.sh first."
fi
if [[ ! -s "$window_config" ]]; then
    die "Window config not found: $window_config"
fi
seed_windows="$seed_dir/windows.tsv"
if (( ! ${dry_run:-0} )) && [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" ../helpers/writer_guard.py \
        --registry "../work" --read "../work" --read "$seed_dir" --read "$window_config" \
        --write "$window_root" -- "$0" "${original_args[@]}"
fi

# umbrella.centers and force_constants come from the editable config, as in
# rmd/anal.py, so windows can be chosen after the ratchet MD. generate_inputs.py
# checks count, order, sign and plain-decimal format, and prints the same
# "CENTER FORCE" table that rmd/anal.py saved with the seeds.
if ! window_table=$("$python" - "$window_config" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "../helpers")
from config_utils import load_config, section
from generate_inputs import umbrella_windows, window_table

try:
    windows = umbrella_windows(section(load_config(Path(sys.argv[1])), "umbrella"))
except ValueError as error:
    raise SystemExit(f"Config error: {error}") from None
print(window_table(windows), end="")
PY
); then
    die "Invalid umbrella windows in $window_config"
fi

window_rows=()
while read -r center force; do
    if [[ "$center" == \#* ]]; then
        continue
    fi
    window_rows+=("$center $force")
done <<< "$window_table"

if (( dry_run )); then
    echo "Dry run: umbrella-window build from umbrella.centers in $window_config"
    echo "+ $python -B ../helpers/generate_inputs.py us $config $window_root --topology $topology"
    echo "Umbrella windows: ${#window_rows[@]}"
    exit 0
fi

if ! command -v "$python" >/dev/null 2>&1; then
    die "Python not found: $python"
fi
for input in "$topology" "$config" "$seed_metadata" "$seed_windows"; do
    if [[ ! -s "$input" ]]; then
        die "Required input not found: $input"
    fi
done
seed_table=$(< "$seed_windows")
if [[ "$window_table" != "$seed_table" ]]; then
    die "Window table changed since seed extraction: umbrella.centers/force_constants in $window_config (seed table: $seed_windows). Extract a new seed generation."
fi
metadata_count=$(awk 'NR > 1 && NF {count++} END {print count+0}' "$seed_metadata")
if (( metadata_count != ${#window_rows[@]} )); then
    die "Window count differs from seed metadata: $window_config has ${#window_rows[@]} windows ($metadata_count seeds)."
fi
if [[ -e "$window_root" ]]; then
    die "Window output already exists: $window_root"
fi

for row_index in "${!window_rows[@]}"; do
    window_number=$((row_index + 1))
    printf -v window_id '%03d' "$window_number"
    metadata_line_number=$((row_index + 2))
    metadata_row=$(awk -v line="$metadata_line_number" \
        'NR == line { print $1, $2 }' "$seed_metadata")
    if [[ -z "$metadata_row" ]]; then
        die "$window_id is missing from $seed_metadata"
    fi
    read -r metadata_window metadata_center <<< "$metadata_row"
    read -r configured_center _ <<< "${window_rows[$row_index]}"
    if [[ "$metadata_window" != "$window_number" ]]; then
        die "Window order differs in $seed_metadata: $window_id"
    fi
    if ! awk -v configured="$configured_center" -v observed="$metadata_center" \
        'BEGIN { difference=configured-observed; if (difference<0) difference=-difference; exit !(difference<1e-6) }'; then
        die "$window_id center differs from seed metadata: $configured_center vs $metadata_center"
    fi
    if [[ ! -s "$seed_dir/seed_${window_id}.rst7" ]]; then
        die "Seed restart not found: $seed_dir/seed_${window_id}.rst7"
    fi
done

echo "Generating umbrella inputs from: $config"
"$python" -B ../helpers/generate_inputs.py us "$config" "$window_root" \
    --topology "$topology"

for row_index in "${!window_rows[@]}"; do
    read -r center force <<< "${window_rows[$row_index]}"
    window_number=$((row_index + 1))
    printf -v window_id '%03d' "$window_number"
    window_dir="$window_root/$window_id"
    mkdir -p "$window_dir"
    cp "$topology" "$window_dir/system.parm7"
    cp "$seed_dir/seed_${window_id}.rst7" "$window_dir/seed.rst7"
    sed -e "s/CENTER/$center/g" -e "s/FORCE/$force/g" \
        "$window_root/restraint.RST.template" > "$window_dir/restraint.RST"
    printf 'window\tcenter_A\tforce_kcal_mol_A2\n%s\t%s\t%s\n' \
        "$window_id" "$center" "$force" > "$window_dir/window.tsv"
done

echo "Created ${#window_rows[@]} umbrella windows: $window_root"
