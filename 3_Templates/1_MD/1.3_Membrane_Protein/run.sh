#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

dry_run=0
preparation_only=0
production_only=0
segment_range=""

show_help() {
    cat <<'EOF'
Usage: ./run.sh [--preparation-only | --production-only] [--segments START-END] [--dry-run]

Relax solvent, lipids, and protein in order, then run production segments.
Protein restraints progress from heavy atoms to backbone to none.

Options:
  --preparation-only  Run through equilibration and stop before production.
  --production-only   Run only production from completed preparation output.
  --segments RANGE    Run the inclusive 1-based production segment range.
  --dry-run      Print engine commands without running them.
  -h, --help     Show this help message and exit.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --preparation-only) preparation_only=1; shift ;;
        --production-only) production_only=1; shift ;;
        --segments)
            if [[ $# -lt 2 ]]; then
                echo "Error: --segments requires START-END." >&2
                exit 2
            fi
            segment_range=$2
            shift 2
            ;;
        --dry-run) dry_run=1; shift ;;
        -h|--help) show_help; exit 0 ;;
        *) show_help >&2; exit 2 ;;
    esac
done
if (( preparation_only && production_only )); then
    echo "Error: --preparation-only and --production-only cannot be used together." >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

run_stage() {
    local stage=$1
    local label=$2
    local directory=$3
    shift 3
    local marker="$directory/.$stage.complete"
    local required=()
    local index

    for ((index = 1; index <= $#; index++)); do
        case "${!index}" in
            -o|-r|-x|-inf)
                index=$((index + 1))
                required+=("${!index}")
                ;;
        esac
    done

    if (( dry_run )); then
        echo "Dry run: $label ($directory)"
        printf '+'
        printf ' %q' "$@"
        printf '\n'
        return
    fi

    local identity_label=$label
    if [[ "$stage" == production ]]; then
        identity_label="production segment $segment_number"
    fi
    "${PYTHON:-python3}" helpers/input_identity.py \
        --record "$marker.identity.json" --stage "$identity_label" --marker "$marker" -- "$@"

    local existing=0
    local complete=0
    local output
    for output in "${required[@]}"; do
        if [[ -e "$output" ]]; then
            existing=$((existing + 1))
        fi
        if [[ -s "$output" ]]; then
            complete=$((complete + 1))
        fi
    done
    if [[ -f "$marker" && "$complete" -eq "${#required[@]}" ]]; then
        echo "Skipping completed stage: $label ($directory)"
        return
    fi
    if [[ -f "$marker" || "$existing" -ne 0 ]]; then
        die "Partial $stage output detected and retained: $directory"
    fi

    echo "Running: $label"
    if ! "$@"; then
        die "$label failed in $directory; expected engine output: ${required[0]} (may be absent); see engine diagnostics above"
    fi
    for output in "${required[@]}"; do
        if [[ ! -s "$output" ]]; then
            die "$label output was not created: $output"
        fi
    done
    touch "$marker"
    echo "Completed: $label ($directory)"
}

work_dir=${WORK_DIR:-work}
if (( ! ${dry_run:-0} )) && [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "$work_dir" --write "$work_dir" -- "$0" "${original_args[@]}"
fi
topology="$work_dir/system.parm7"
coordinates="$work_dir/system.rst7"
resolved="$work_dir/resolved_config.toml"

if (( ! dry_run )); then
    if [[ ! -s "$topology" ]]; then
        die "Run preflight: topology missing or empty: $topology. Run ./build.sh first."
    fi
    if [[ ! -s "$coordinates" ]]; then
        die "Run preflight: restart missing or empty: $coordinates. Run ./build.sh first."
    fi
    if [[ ! -s "$resolved" ]]; then
        die "Run preflight: resolved config missing or empty: $resolved. Run ./build.sh first."
    fi
    for input_name in min-solvent min-lipid heat equilibrate-heavy equilibrate-backbone equilibrate production; do
        if [[ ! -s "$work_dir/inputs/$input_name.in" ]]; then
            die "Run preflight: staged membrane input missing: $work_dir/inputs/$input_name.in. Build in a new WORK_DIR."
        fi
    done
fi

engine=$("${PYTHON:-python3}" helpers/config_utils.py "$resolved" engine AMBER_ENGINE pmemd.cuda pmemd sander)

segments=$(awk -F' = ' '$1=="production_segments" {print $2}' "$resolved" 2>/dev/null || true)
segments=${segments:-10}
segment_start=1; segment_end=$segments
if [[ -n "$segment_range" ]]; then
    if [[ ! "$segment_range" =~ ^([1-9][0-9]*)-([1-9][0-9]*)$ ]]; then
        die "--segments must use START-END"
    fi
    segment_start=${BASH_REMATCH[1]}; segment_end=${BASH_REMATCH[2]}
    if (( segment_start > segment_end || segment_end > segments )); then
        die "Segment range is outside 1-$segments: $segment_range"
    fi
fi

if (( ! dry_run )); then
    if ! command -v "$engine" >/dev/null 2>&1; then
        die "AMBER engine not found: $engine"
    fi
fi

if (( ! dry_run )); then
    "${PYTHON:-python3}" helpers/input_identity.py --verify "$work_dir"
fi

if (( ! production_only )); then
    # Lipids remain restrained while water and bulk ions relax.
    run_stage min-solvent "solvent minimization" "$work_dir" \
        "$engine" \
        -O \
        -i "$work_dir/inputs/min-solvent.in" \
        -o "$work_dir/min-solvent.out" \
        -p "$topology" \
        -c "$coordinates" \
        -r "$work_dir/min-solvent.rst7" \
        -inf "$work_dir/min-solvent.info" \
        -ref "$coordinates"

    # Release lipids while keeping the protein near the initial structure.
    run_stage min-lipid "lipid minimization" "$work_dir" \
        "$engine" \
        -O \
        -i "$work_dir/inputs/min-lipid.in" \
        -o "$work_dir/min-lipid.out" \
        -p "$topology" \
        -c "$work_dir/min-solvent.rst7" \
        -r "$work_dir/min-lipid.rst7" \
        -inf "$work_dir/min-lipid.info" \
        -ref "$coordinates"

    run_stage heat "NVT heating" "$work_dir" \
        "$engine" \
        -O \
        -i "$work_dir/inputs/heat.in" \
        -o "$work_dir/heat.out" \
        -p "$topology" \
        -c "$work_dir/min-lipid.rst7" \
        -r "$work_dir/heat.rst7" \
        -x "$work_dir/heat.nc" \
        -inf "$work_dir/heat.info" \
        -ref "$work_dir/min-lipid.rst7"

    # Both restrained equilibration stages use the same heated reference.
    run_stage equilibrate-heavy "heavy-atom NPT equilibration" "$work_dir" \
        "$engine" \
        -O \
        -i "$work_dir/inputs/equilibrate-heavy.in" \
        -o "$work_dir/equilibrate-heavy.out" \
        -p "$topology" \
        -c "$work_dir/heat.rst7" \
        -r "$work_dir/equilibrate-heavy.rst7" \
        -x "$work_dir/equilibrate-heavy.nc" \
        -inf "$work_dir/equilibrate-heavy.info" \
        -ref "$work_dir/heat.rst7"

    run_stage equilibrate-backbone "backbone NPT equilibration" "$work_dir" \
        "$engine" \
        -O \
        -i "$work_dir/inputs/equilibrate-backbone.in" \
        -o "$work_dir/equilibrate-backbone.out" \
        -p "$topology" \
        -c "$work_dir/equilibrate-heavy.rst7" \
        -r "$work_dir/equilibrate-backbone.rst7" \
        -x "$work_dir/equilibrate-backbone.nc" \
        -inf "$work_dir/equilibrate-backbone.info" \
        -ref "$work_dir/heat.rst7"

    run_stage equilibrate "unrestrained NPT equilibration" "$work_dir" \
        "$engine" \
        -O \
        -i "$work_dir/inputs/equilibrate.in" \
        -o "$work_dir/equilibrate.out" \
        -p "$topology" \
        -c "$work_dir/equilibrate-backbone.rst7" \
        -r "$work_dir/equilibrate.rst7" \
        -x "$work_dir/equilibrate.nc" \
        -inf "$work_dir/equilibrate.info"
fi
if (( preparation_only )); then
    if (( ! dry_run )); then
        echo "Preparation output: $work_dir/equilibrate.rst7"
    fi
    exit 0
fi
if (( ! dry_run )); then
    for stage in equilibrate-heavy equilibrate-backbone equilibrate; do
        if [[ ! -s "$work_dir/$stage.rst7" || ! -f "$work_dir/.$stage.complete" ]]; then
            die "Production preflight: completed staged equilibration required: $work_dir/$stage.rst7"
        fi
    done
fi

previous_restart="$work_dir/equilibrate.rst7"
if (( segment_start > 1 )); then
    printf -v previous_id '%03d' "$((segment_start - 1))"
    previous_restart="$work_dir/$previous_id/production.rst7"
    previous_marker="$work_dir/$previous_id/.production.complete"
    if (( segment_start == 2 )) && [[ -f "$work_dir/.production.complete.identity.json" ]]; then
        previous_restart="$work_dir/production.rst7"
        previous_marker="$work_dir/.production.complete"
    fi
    if (( ! dry_run )) && [[ ! -s "$previous_restart" || ! -f "$previous_marker" ]]; then
        die "Previous production segment is incomplete: $work_dir/$previous_id"
    fi
fi
for ((segment_number = segment_start; segment_number <= segment_end; segment_number++)); do
    single_segment_layout=0
    if (( segments == 1 )) && [[ ! -f "$work_dir/001/.production.complete.identity.json" ]]; then
        single_segment_layout=1
    elif (( segment_number == 1 )) && [[ -f "$work_dir/.production.complete.identity.json" ]]; then
        single_segment_layout=1
    fi
    if (( single_segment_layout )); then
        segment_dir=$work_dir
    else
        printf -v segment_id '%03d' "$segment_number"
        segment_dir="$work_dir/$segment_id"
    fi
    if (( ! dry_run )); then
        mkdir -p "$segment_dir"
    fi
    run_stage production \
        "production segment $segment_number/$segments" "$segment_dir" \
        "$engine" -O -i "$work_dir/inputs/production.in" \
        -o "$segment_dir/production.out" -p "$topology" -c "$previous_restart" \
        -r "$segment_dir/production.rst7" -x "$segment_dir/production.nc" \
        -inf "$segment_dir/production.info"
    previous_restart="$segment_dir/production.rst7"
done

if (( ! dry_run )); then
    if (( segments == 1 )); then
        echo "Production output: $segment_dir/production.out"
    else
        echo "Production segments: $work_dir/$(printf '%03d' "$segment_start") through $work_dir/$(printf '%03d' "$segment_end")"
    fi
fi
