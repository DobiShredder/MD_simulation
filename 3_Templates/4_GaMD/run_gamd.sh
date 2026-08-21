#!/usr/bin/env bash
set -euo pipefail

show_help() {
    cat <<'EOF'
Usage: bash ../run_gamd.sh METHOD [--preparation-only | --production-only] [--segments START-END] [--dry-run]

Run minimization, heating, NPT equilibration, GaMD parameter preparation,
and configured production segments. METHOD is gamd, ligamd3, or pepgamd.

Options:
  --preparation-only  Run through GaMD parameter preparation and stop.
  --production-only   Run production from completed GaMD preparation state.
  --segments RANGE    Run the inclusive 1-based production segment range.
  --dry-run      Print engine commands without running them.
  -h, --help     Show this help message and exit.
EOF
}

if [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
    show_help
    exit 0
fi
if [[ $# -lt 1 ]]; then
    show_help >&2
    exit 2
fi
method=$1
shift
dry_run=0
preparation_only=0
production_only=0
segment_range=""
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
if [[ ! "$method" =~ ^(gamd|ligamd3|pepgamd)$ ]]; then
    show_help >&2
    exit 2
fi
if (( preparation_only && production_only )); then
    echo "Error: incompatible run modes." >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

work_dir=${WORK_DIR:-work}
resolved="$work_dir/resolved_config.toml"
engine=${AMBER_ENGINE:-pmemd.cuda}
read -r -a amber_options <<< "${AMBER_OPTIONS:-}"

read_value() {
    local key=$1
    awk -F' = ' -v key="$key" '$1 == key {gsub(/"/, "", $2); value=$2} END {print value}' "$resolved"
}

if (( ! dry_run )); then
    if [[ ! -s "$work_dir/system.parm7" || ! -s "$work_dir/system.rst7" || ! -s "$resolved" ]]; then
        die "Build output not found. Run ./build.sh first."
    fi
    if ! command -v "$engine" >/dev/null 2>&1; then
        die "AMBER engine not found: $engine"
    fi
    if [[ "$method" != gamd && "$(basename "$engine")" != pmemd.cuda ]]; then
        die "LiGaMD3 and Pep-GaMD require the serial pmemd.cuda engine: $engine"
    fi
fi

segments=$(read_value production_segments 2>/dev/null || true)
segments=${segments:-10}
segment_start=1
segment_end=$segments
if [[ -n "$segment_range" ]]; then
    if [[ ! "$segment_range" =~ ^([1-9][0-9]*)-([1-9][0-9]*)$ ]]; then
        die "--segments must use START-END with 1-based indices: $segment_range"
    fi
    segment_start=${BASH_REMATCH[1]}
    segment_end=${BASH_REMATCH[2]}
    if (( segment_start > segment_end || segment_end > segments )); then
        die "Segment range is outside 1-$segments: $segment_range"
    fi
fi

stage_state() {
    local marker=$1
    shift
    local existing=0
    local path
    for path in "$@"; do
        if [[ -s "$path" ]]; then
            existing=$((existing + 1))
        fi
    done
    if [[ -f "$marker" && "$existing" -eq "$#" ]]; then
        echo complete
    elif [[ ! -f "$marker" && "$existing" -eq 0 ]]; then
        echo missing
    else
        echo partial
    fi
}

run_stage() {
    local stage=$1
    local stage_type=$2
    local directory=$3
    local input_file=$4
    local input_restart=$5
    local reference_restart=${6:-}
    local use_gamd=${7:-no}
    local previous_gamd_state=${8:-}
    local marker="$directory/.$stage.complete"
    local prefix="$directory/$stage"
    local required=("$prefix.out" "$prefix.rst7" "$prefix.info")
    local command=("$engine" "${amber_options[@]}" -O -i "$input_file" -o "$stage.out" -p "$topology_path" -c "$input_restart" -r "$stage.rst7" -inf "$stage.info")

    if [[ "$stage" != minimize ]]; then
        required+=("$prefix.nc")
        command+=(-x "$stage.nc")
    fi
    if [[ -n "$reference_restart" ]]; then
        command+=(-ref "$reference_restart")
    fi
    if [[ "$use_gamd" == yes ]]; then
        required+=("$prefix.gamd.log" "$prefix.gamd.rst")
        command+=(-gamd "$stage.gamd.log")
    fi

    if (( dry_run )); then
        printf '+ (cd %q;' "$directory"
        printf ' %q' "${command[@]}"
        printf ')\n'
        return
    fi

    mkdir -p "$directory"
    local state
    state=$(stage_state "$marker" "${required[@]}")
    if [[ "$state" == complete ]]; then
        return
    fi
    if [[ "$state" == partial ]]; then
        if [[ "$stage_type" == production ]]; then
            die "Partial production or GaMD-state output detected: $directory"
        fi
        echo "Warning: removing partial $stage output and restarting the stage." >&2
        rm -f -- "$marker" "${required[@]}"
    fi
    if [[ -n "$previous_gamd_state" ]]; then
        cp "$previous_gamd_state" "$directory/gamd-restart.dat"
    fi

    echo "Running: $stage"
    if ! (cd "$directory"; "${command[@]}"); then
        die "$stage calculation failed: $directory"
    fi
    if [[ "$use_gamd" == yes ]]; then
        if [[ ! -s "$directory/gamd-restart.dat" ]]; then
            die "$stage GaMD state was not created: $directory/gamd-restart.dat"
        fi
        cp "$directory/gamd-restart.dat" "$prefix.gamd.rst"
    fi
    local output
    for output in "${required[@]}"; do
        if [[ ! -s "$output" ]]; then
            die "$stage output was not created: $output"
        fi
    done
    touch "$marker"
}

topology_path=system.parm7
input_prefix=inputs
if (( ! production_only )); then
run_stage minimize preproduction "$work_dir" "$input_prefix/minimize.in" system.rst7
run_stage heat preproduction "$work_dir" "$input_prefix/heat.in" minimize.rst7 minimize.rst7
run_stage equilibrate preproduction "$work_dir" "$input_prefix/equilibrate.in" heat.rst7
run_stage gamd_prepare production "$work_dir" "$input_prefix/gamd_prepare.in" equilibrate.rst7 "" yes
fi

if (( preparation_only )); then
    exit 0
fi
if (( ! dry_run )) && [[ ! -s "$work_dir/gamd_prepare.rst7" || ! -s "$work_dir/gamd_prepare.gamd.rst" || ! -f "$work_dir/.gamd_prepare.complete" ]]; then
    die "Completed GaMD parameter preparation is required for production."
fi

previous_restart="$work_dir/gamd_prepare.rst7"
previous_gamd_state="$work_dir/gamd_prepare.gamd.rst"
if (( segment_start > 1 )); then
    printf -v previous_id '%03d' "$((segment_start - 1))"
    previous_restart="$work_dir/$previous_id/production.rst7"
    previous_gamd_state="$work_dir/$previous_id/production.gamd.rst"
    if (( ! dry_run )) && [[ ! -s "$previous_restart" || ! -s "$previous_gamd_state" || ! -f "$work_dir/$previous_id/.production.complete" ]]; then
        die "Previous production segment is incomplete: $work_dir/$previous_id"
    fi
fi
for ((segment_number = segment_start; segment_number <= segment_end; segment_number++)); do
    if (( segments == 1 )); then
        segment_dir=$work_dir
        topology_path=system.parm7
        input_prefix=inputs
        restart_path=${previous_restart#"$work_dir/"}
        state_path=$previous_gamd_state
    else
        printf -v segment_id '%03d' "$segment_number"
        segment_dir="$work_dir/$segment_id"
        topology_path=../system.parm7
        input_prefix=../inputs
        if (( segment_number == 1 )); then
            restart_path=../gamd_prepare.rst7
        else
            restart_path=../$(printf '%03d' "$((segment_number - 1))")/production.rst7
        fi
        state_path=$previous_gamd_state
    fi
    run_stage production production "$segment_dir" "$input_prefix/production.in" "$restart_path" "" yes "$state_path"
    previous_restart="$segment_dir/production.rst7"
    previous_gamd_state="$segment_dir/production.gamd.rst"
done

if (( ! dry_run )); then
    echo "GaMD production completed: $work_dir"
fi
