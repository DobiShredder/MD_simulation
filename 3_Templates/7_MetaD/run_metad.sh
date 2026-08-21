#!/usr/bin/env bash
set -euo pipefail

dry_run=0
selected_segment=""
segment_range=""
preparation_only=0
production_only=0

show_help() {
    cat <<'EOF'
Usage: ../run_metad.sh METHOD [--preparation-only | --production-only] [--segment N | --segments START-END] [--dry-run]

Run restart-safe AMBER preparation and segmented MetaD or OPES production.

Arguments:
  METHOD       wt-metad, funnel-metad, opes-metad, or opes-expanded.

Options:
  --segment N  Run only one 1-based production segment after preparation.
  --segments RANGE  Run an inclusive 1-based production segment range.
  --preparation-only  Run through equilibration without biased production.
  --production-only   Run biased production from completed equilibration.
  --dry-run    Print the planned stage and production commands.
  -h, --help   Show this help message and exit.

Environment:
  AMBER_ENGINE  AMBER executable override; otherwise use resolved config.
  AMBER_OPTIONS Additional engine options separated by spaces.
  PLUMED        PLUMED executable used for action and parse checks.
  PYTHON        Python executable (default: python3).
  WORK_DIR      Generated simulation directory (default: work).
EOF
}

if [[ $# -lt 1 ]]; then
    show_help >&2
    exit 2
fi
method=$1
shift
case "$method" in
    wt-metad|funnel-metad|opes-metad|opes-expanded) ;;
    -h|--help) show_help; exit 0 ;;
    *) echo "Error: unknown method: $method" >&2; exit 2 ;;
esac

while [[ $# -gt 0 ]]; do
    case "$1" in
        --segment)
            if [[ $# -lt 2 ]]; then
                echo "Error: --segment requires an index." >&2
                exit 2
            fi
            selected_segment=$2
            shift 2
            ;;
        --segments)
            if [[ $# -lt 2 ]]; then
                echo "Error: --segments requires START-END." >&2
                exit 2
            fi
            segment_range=$2
            shift 2
            ;;
        --preparation-only) preparation_only=1; shift ;;
        --production-only) production_only=1; shift ;;
        --dry-run) dry_run=1; shift ;;
        -h|--help) show_help; exit 0 ;;
        *) show_help >&2; exit 2 ;;
    esac
done

die() {
    echo "Error: $*" >&2
    exit 1
}

if [[ -n "$selected_segment" && ! "$selected_segment" =~ ^[1-9][0-9]*$ ]]; then
    die "--segment must be a positive integer: $selected_segment"
fi
if (( preparation_only && production_only )); then
    die "--preparation-only and --production-only cannot be used together"
fi
if [[ -n "$selected_segment" && -n "$segment_range" ]]; then
    die "--segment and --segments cannot be used together"
fi

work_dir=${WORK_DIR:-work}
python=${PYTHON:-python3}
plumed=${PLUMED:-plumed}
read -r -a amber_options <<< "${AMBER_OPTIONS:-}"

config_file="$work_dir/resolved_config.toml"
if (( dry_run )) && [[ ! -s "$config_file" ]]; then
    config_file=config.toml
fi
if [[ ! -s "$config_file" ]]; then
    die "Resolved config not found. Run ./build.sh first: $config_file"
fi
if ! command -v "$python" >/dev/null 2>&1; then
    die "Python not found: $python"
fi

config_values=$("$python" - "$config_file" <<'PY'
import sys
sys.path.insert(0, "../../common")
from pathlib import Path
from config_utils import load_config

run = load_config(Path(sys.argv[1]))["run"]
print(run["engine"], run["production_segments"], run["random_seed"], sep="\t")
PY
)
IFS=$'\t' read -r configured_engine segments seed_setting <<< "$config_values"
engine=${AMBER_ENGINE:-$configured_engine}
if [[ ! "$segments" =~ ^[1-9][0-9]*$ ]]; then
    die "production_segments must be a positive integer: $segments"
fi
if [[ -n "$selected_segment" && "$selected_segment" -gt "$segments" ]]; then
    die "--segment exceeds production_segments=$segments: $selected_segment"
fi
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
if [[ "$seed_setting" != random && ! "$seed_setting" =~ ^[1-9][0-9]*$ ]]; then
    die "random_seed must be random or a positive integer: $seed_setting"
fi

stage_state() {
    local marker=$1
    shift
    local present=0
    local path
    for path in "$@"; do
        if [[ -s "$path" ]]; then
            present=$((present + 1))
        fi
    done
    if [[ -f "$marker" && "$present" -eq "$#" ]]; then
        echo complete
    elif [[ ! -f "$marker" && "$present" -eq 0 ]]; then
        echo missing
    else
        echo partial
    fi
}

run_command() {
    local label=$1
    local directory=$2
    shift 2
    if (( dry_run )); then
        printf '+ (cd %q &&' "$directory"
        printf ' %q' "$@"
        printf ')\n'
        return
    fi
    echo "Running: $label"
    if ! (cd "$directory"; "$@"); then
        die "$label failed: $directory"
    fi
}

run_preproduction_stage() {
    local stage=$1
    local input_restart=$2
    local reference_restart=${3:-}
    local marker="$work_dir/.$stage.complete"
    local required=(
        "$work_dir/$stage.out" "$work_dir/$stage.info" "$work_dir/$stage.rst7"
    )
    local command=(
        "$engine" "${amber_options[@]}" -O
        -i "inputs/$stage.in" -o "$stage.out"
        -p system.parm7 -c "$input_restart"
        -r "$stage.rst7" -inf "$stage.info"
    )
    local state
    if [[ "$stage" != min-solvent && "$stage" != min-all && "$stage" != minimize ]]; then
        required+=("$work_dir/$stage.nc")
        command+=(-x "$stage.nc")
    fi
    if [[ -n "$reference_restart" ]]; then
        command+=(-ref "$reference_restart")
    fi
    if (( ! dry_run )); then
        state=$(stage_state "$marker" "${required[@]}")
        if [[ "$state" == complete ]]; then
            return
        fi
        if [[ "$state" == partial ]]; then
            echo "Warning: restarting partial $stage stage." >&2
            rm -f -- "$marker" "${required[@]}"
        fi
    fi
    run_command "$stage" "$work_dir" "${command[@]}"
    if (( ! dry_run )); then
        for output in "${required[@]}"; do
            if [[ ! -s "$output" ]]; then
                die "$stage output was not created: $output"
            fi
        done
        touch "$marker"
    fi
}

check_plumed() {
    local action
    local actions=(METAD)
    case "$method" in
        funnel-metad) actions=(FUNNEL_PS FUNNEL METAD) ;;
        opes-metad) actions=(OPES_METAD) ;;
        opes-expanded) actions=(ECV_MULTITHERMAL OPES_EXPANDED) ;;
    esac
    for action in "${actions[@]}"; do
        if ! "$plumed" manual --action "$action" >/dev/null 2>&1; then
            die "PLUMED action is unavailable: $action"
        fi
    done

    parse_input="$work_dir/plumed.parse.dat"
    generate=(
        "$python" ../generate_plumed.py "$method" "$config_file" "$parse_input"
        --parse-only
    )
    if [[ "$method" == wt-metad || "$method" == opes-metad ]]; then
        generate+=(--cv-file "$work_dir/cv.dat")
    elif [[ "$method" == funnel-metad ]]; then
        generate+=(--funnel-context "$work_dir/funnel_context.toml")
    fi
    "${generate[@]}"
    atom_count=$(<"$work_dir/atom_count.txt")
    if ! (cd "$work_dir"; "$plumed" driver --plumed plumed.parse.dat --parse-only --natoms "$atom_count"); then
        find "$work_dir" -maxdepth 1 -type f -name 'plumed.parse.*' -delete
        die "PLUMED parse-only check failed: $parse_input"
    fi
    find "$work_dir" -maxdepth 1 -type f -name 'plumed.parse.*' -delete
}

production_state_files() {
    case "$method" in
        wt-metad) echo HILLS COLVAR ;;
        funnel-metad) echo HILLS COLVAR FUNNEL_GRID ;;
        opes-metad) echo KERNELS opes.state COLVAR ;;
        opes-expanded) echo DELTAFS opes.state COLVAR ;;
    esac
}

run_production_segment() {
    local segment_index=$1
    local segment_name
    local segment_dir
    local prefix
    local topology_path
    local input_restart
    local marker
    local state
    local seed
    local generated_plumed
    local output

    printf -v segment_name '%03d' "$segment_index"
    if [[ "$segments" -eq 1 ]]; then
        segment_dir=$work_dir
        prefix=""
        topology_path=system.parm7
        input_restart=equilibrate.rst7
    else
        segment_dir="$work_dir/$segment_name"
        prefix="../"
        topology_path=../system.parm7
        if [[ "$segment_index" -eq 1 ]]; then
            input_restart=../equilibrate.rst7
        else
            previous=$((segment_index - 1))
            printf -v previous_name '%03d' "$previous"
            input_restart="../$previous_name/production.rst7"
        fi
    fi
    marker="$segment_dir/.production.complete"
    required=(
        "$segment_dir/production.out" "$segment_dir/production.info"
        "$segment_dir/production.rst7" "$segment_dir/production.nc"
    )

    if (( ! dry_run )); then
        mkdir -p "$segment_dir"
        state=$(stage_state "$marker" "${required[@]}")
        if [[ "$state" == complete ]]; then
            return
        fi
        if [[ "$state" == partial ]]; then
            die "Partial production segment detected: $segment_dir"
        fi
        if [[ "$segment_index" -gt 1 && ! -f "$work_dir/$previous_name/.production.complete" ]]; then
            die "Previous production segment is incomplete: $work_dir/$previous_name"
        fi
        if [[ "$segment_index" -gt 1 && ! -s "$work_dir/$previous_name/production.rst7" ]]; then
            die "Previous production restart not found: $work_dir/$previous_name/production.rst7"
        fi
        if [[ "$segment_index" -gt 1 ]]; then
            for output in $(production_state_files); do
                if [[ ! -s "$work_dir/$output" ]]; then
                    die "Bias state required for continuation was not found: $work_dir/$output"
                fi
            done
        elif [[ -e "$work_dir/HILLS" || -e "$work_dir/KERNELS" || -e "$work_dir/DELTAFS" || -e "$work_dir/opes.state" || -e "$work_dir/COLVAR" || -e "$work_dir/FUNNEL_GRID" ]]; then
            die "Bias output exists before the first production segment: $work_dir"
        fi

        if [[ "$seed_setting" == random ]]; then
            seed=-1
        else
            seed=$((seed_setting + 100 + segment_index))
        fi
        sed "s/@RANDOM_SEED@/$seed/g" \
            "$work_dir/inputs/production.in.template" > "$segment_dir/production.in"
        generated_plumed=(
            "$python" ../generate_plumed.py "$method" "$config_file"
            "$segment_dir/plumed.dat" --file-prefix "$prefix"
        )
        if [[ "$method" == wt-metad || "$method" == opes-metad ]]; then
            generated_plumed+=(--cv-file "$work_dir/cv.dat")
        elif [[ "$method" == funnel-metad ]]; then
            generated_plumed+=(--funnel-context "$work_dir/funnel_context.toml")
        fi
        if [[ "$segment_index" -gt 1 ]]; then
            generated_plumed+=(--restart)
        fi
        "${generated_plumed[@]}"
    fi

    run_command "production segment $segment_name/$segments" "$segment_dir" \
        "$engine" "${amber_options[@]}" -O \
        -i production.in -o production.out \
        -p "$topology_path" -c "$input_restart" \
        -r production.rst7 -x production.nc -inf production.info

    if (( ! dry_run )); then
        for output in "${required[@]}"; do
            if [[ ! -s "$output" ]]; then
                die "Production output was not created: $output"
            fi
        done
        for output in $(production_state_files); do
            if [[ ! -s "$work_dir/$output" ]]; then
                die "Bias output was not created: $work_dir/$output"
            fi
        done
        touch "$marker"
    fi
}

if (( ! dry_run )); then
    for executable in "$engine" "$plumed"; do
        if ! command -v "$executable" >/dev/null 2>&1; then
            die "Executable not found: $executable"
        fi
    done
    for required in "$work_dir/system.parm7" "$work_dir/system.rst7" "$work_dir/atom_count.txt" "$work_dir/inputs/production.in.template"; do
        if [[ ! -s "$required" ]]; then
            die "Build output not found. Run ./build.sh first: $required"
        fi
    done
    check_plumed
fi

if (( ! production_only )) && [[ "$method" == funnel-metad ]]; then
    run_preproduction_stage min-solvent system.rst7 system.rst7
    run_preproduction_stage min-all min-solvent.rst7
    run_preproduction_stage heat min-all.rst7 min-all.rst7
    run_preproduction_stage equilibrate heat.rst7 heat.rst7
elif (( ! production_only )); then
    run_preproduction_stage minimize system.rst7
    run_preproduction_stage heat minimize.rst7 minimize.rst7
    run_preproduction_stage equilibrate heat.rst7
fi

if (( preparation_only )); then
    exit 0
fi
if (( ! dry_run )) && [[ ! -s "$work_dir/equilibrate.rst7" || ! -f "$work_dir/.equilibrate.complete" ]]; then
    die "Completed equilibration output is required for production."
fi

for ((segment_index = segment_start; segment_index <= segment_end; segment_index++)); do
    if [[ -n "$selected_segment" && "$segment_index" -ne "$selected_segment" ]]; then
        continue
    fi
    run_production_segment "$segment_index"
done

if (( ! dry_run )); then
    echo "MetaD production segments completed: $work_dir"
fi
