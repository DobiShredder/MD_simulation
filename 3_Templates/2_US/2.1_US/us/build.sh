#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

dry_run=0
if [[ "${1:-}" == --dry-run && $# -eq 1 ]]; then
    dry_run=1
elif [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
    cat <<'EOF'
Usage: ./build.sh [--dry-run]

Create umbrella-window directories from the rMD seed restarts.

Options:
  --dry-run   Validate the window table and print the planned generator.
  -h, --help  Show this help message and exit.
EOF
    exit 0
elif (( $# != 0 )); then
    echo "Usage: ./build.sh [--dry-run]" >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

python=${PYTHON:-python3}
seed_dir=../rmd/work/seeds
seed_metadata="$seed_dir/seeds.tsv"
topology=../work/system.parm7
config=../work/resolved_config.toml
window_root=work
if [[ ! -s "$config" ]]; then
    die "Resolved config not found: $config. Run the root build.sh first."
fi
window_file=$("$python" - "$config" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "../helpers")
from config_utils import load_config, section, string_value

config = load_config(Path(sys.argv[1]))
print(Path("..") / string_value(section(config, "umbrella"), "windows_file"))
PY
)
seed_windows="$seed_dir/windows.tsv"
if (( ! ${dry_run:-0} )) && [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" ../helpers/writer_guard.py \
        --registry "../work" --read "../work" --read "$seed_dir" --read "$window_file" --write "$window_root" -- "$0" "${original_args[@]}"
fi

if [[ ! -s "$window_file" ]]; then
    die "Window settings not found: $window_file"
fi

window_rows=()
previous_center=""
while read -r center force extra_field; do
    if [[ -z "${center:-}" || "$center" == \#* ]]; then
        continue
    fi
    if [[ -n "${extra_field:-}" ]]; then
        die "$window_file must contain exactly two columns: CENTER_A and FORCE."
    fi
    if [[ ! "$center" =~ ^[0-9]+([.][0-9]+)?$ ]] || \
       [[ ! "$force" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
        die "Window center and force must be numeric: $center $force"
    fi
    if ! awk -v center="$center" -v force="$force" \
        'BEGIN { exit !(center > 0 && force > 0) }'; then
        die "Window center and force must be positive: $center $force"
    fi
    if [[ -n "$previous_center" ]] && ! awk \
        -v previous="$previous_center" -v center="$center" \
        'BEGIN { exit !(center > previous) }'; then
        die "Window centers must be unique and increasing: $previous_center -> $center"
    fi
    window_rows+=("$center $force")
    previous_center=$center
done < "$window_file"

if (( ${#window_rows[@]} == 0 )); then
    die "No windows found in $window_file"
fi

if (( dry_run )); then
    echo "Dry run: umbrella-window build from $window_file"
    echo '+ (cd .. && python3 helpers/generate_inputs.py us work/resolved_config.toml us/work --topology work/system.parm7)'
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
if ! cmp -s "$window_file" "$seed_windows"; then
    die "Window table changed since seed extraction: $window_file (seed table: $seed_windows). Extract a new seed generation."
fi
metadata_count=$(awk 'NR > 1 && NF {count++} END {print count+0}' "$seed_metadata")
if (( metadata_count != ${#window_rows[@]} )); then
    die "Window count differs from seed metadata: $window_file ($metadata_count seeds)."
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
(
    cd ..
    "$python" -B helpers/generate_inputs.py us work/resolved_config.toml us/work \
        --topology work/system.parm7
)

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
