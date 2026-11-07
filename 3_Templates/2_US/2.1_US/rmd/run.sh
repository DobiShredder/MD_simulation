#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

dry_run=0
preparation_only=0
production_only=0

show_help() {
    cat <<'EOF'
Usage: ./run.sh [--preparation-only | --production-only] [--dry-run]

Generate the ratchet-MD inputs and run the pathway simulation.

Options:
  --preparation-only  Stop after minimization, heating, and equilibration.
  --production-only   Start ratchet MD from completed equilibration output.
  --dry-run           Print the planned generator and AMBER commands.
  -h, --help          Show this help message and exit.
EOF
}

while (( $# > 0 )); do
    case "$1" in
        --preparation-only)
            preparation_only=1
            shift
            ;;
        --production-only)
            production_only=1
            shift
            ;;
        --dry-run)
            dry_run=1
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            show_help >&2
            exit 2
            ;;
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

show_engine_output() {
    local output=$1
    if [[ -s "$output" ]]; then
        echo "Last 20 lines of $output:" >&2
        tail -n 20 "$output" >&2
    fi
}

# Keep engine stdout/stderr in engine.<stage>.log beside <stage>.out.
# Each attempt appends a header, so earlier attempts stay readable.
run_engine() {
    local engine_log=$1
    shift
    echo "== $(date '+%Y-%m-%d %H:%M:%S') $*" >> "$engine_log"
    "$@" >> "$engine_log" 2>&1
}

# Partial output is never removed or overwritten; the user moves it out of work.
die_partial() {
    local reason=$1
    local label=$2
    shift 2
    local leftover_files=()
    local path
    for path in "$@"; do
        if [[ -e "$path" ]]; then
            leftover_files+=("$path")
        fi
    done
    if (( ${#leftover_files[@]} == 0 )); then
        die "${reason}No rMD $label output was written. Fix the cause and rerun $rerun_command."
    fi
    die "${reason}Partial rMD $label output is retained: ${leftover_files[*]}. Move these files out of work (for example: mkdir -p work.failed && mv ${leftover_files[*]} work.failed/) and rerun $rerun_command."
}

stage_state() {
    local marker=$1
    shift
    local existing=0
    local complete=0
    local path
    for path in "$@"; do
        if [[ -e "$path" ]]; then
            existing=$((existing + 1))
        fi
        if [[ -s "$path" ]]; then
            complete=$((complete + 1))
        fi
    done
    if [[ -f "$marker" && "$complete" -eq "$#" ]]; then
        echo complete
    elif [[ ! -f "$marker" && "$existing" -eq 0 ]]; then
        echo missing
    else
        echo partial
    fi
}

run_stage() {
    local stage=$1
    local label=$2
    local input_restart=$3
    shift 3
    local trajectory=0
    local reference_restart=""

    while (( $# > 0 )); do
        case "$1" in
            --trajectory)
                trajectory=1
                shift
                ;;
            --reference)
                reference_restart=$2
                shift 2
                ;;
            *)
                die "Unsupported run_stage option: $1"
                ;;
        esac
    done

    local prefix="work/$stage"
    local marker="work/.$stage.complete"
    local required=("$prefix.out" "$prefix.rst7")
    local stage_outputs=("$prefix.out" "$prefix.rst7" "$prefix.info" "$prefix.nc" "$marker")
    if [[ "$stage" == ratchet ]]; then
        stage_outputs+=(work/ratchet.dat)
    fi
    # Always name -inf: AMBER otherwise writes mdinfo, which has no input identity.
    local command=(
        "$engine" -O
        -i "inputs/$stage.in"
        -o "$stage.out"
        -p system.parm7
        -c "$input_restart"
        -r "$stage.rst7"
        -inf "$stage.info"
    )
    if (( trajectory )); then
        required+=("$prefix.info" "$prefix.nc")
        command+=(-x "$stage.nc")
    fi
    if [[ -n "$reference_restart" ]]; then
        command+=(-ref "$reference_restart")
    fi

    if (( ! dry_run )); then
        local identity_options=()
        if [[ "$stage" == ratchet ]]; then
            identity_options+=(--input work/plumed.dat)
        fi
        "$python" ../helpers/input_identity.py \
            --record "$marker.identity.json" --stage "$label" --marker "$marker" \
            --directory work "${identity_options[@]}" -- "${command[@]}"
        local state
        state=$(stage_state "$marker" "${required[@]}")
        if [[ "$state" == complete ]]; then
            echo "Skipping completed stage: rMD - $label ($prefix)"
            return
        fi
        if [[ "$state" == partial ]]; then
            die_partial "" "$label" "${stage_outputs[@]}"
        fi
    fi

    if (( dry_run )); then
        echo "Dry run: rMD - $label ($prefix)"
        printf '+ (cd work &&'
        printf ' %q' "${command[@]}"
        printf ')\n'
        return
    fi
    echo "Running: rMD - $label"
    if ! (
        cd work
        run_engine "engine.$stage.log" "${command[@]}"
    ); then
        show_engine_output "$prefix.out"
        show_engine_output "work/engine.$stage.log"
        die_partial "rMD $label failed. " "$label" "${stage_outputs[@]}"
    fi
    local output
    for output in "${required[@]}"; do
        if [[ ! -s "$output" ]]; then
            die_partial "rMD $label output is incomplete: $output. " "$label" "${stage_outputs[@]}"
        fi
    done
    touch "$marker"
    echo "Completed: rMD - $label ($prefix)"
}

if (( ! ${dry_run:-0} )) && [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" ../helpers/writer_guard.py \
        --registry "../work" --read "../work" --write work -- "$0" "${original_args[@]}"
fi
config=../work/resolved_config.toml
if [[ ! -s "$config" ]]; then
    die "Run ../build.sh first: $config"
fi
engine=$("${PYTHON:-python3}" ../helpers/config_utils.py "$config" engine AMBER_ENGINE pmemd.cuda)
python=${PYTHON:-python3}
topology=../work/system.parm7
coordinates=../work/system.rst7
rerun_command="./run.sh"
if (( ${#original_args[@]} > 0 )); then
    rerun_command+=" ${original_args[*]}"
fi

if (( dry_run )); then
    echo '+ (cd .. && python3 helpers/generate_inputs.py rmd work/resolved_config.toml rmd/work --topology work/system.parm7)'
else
    if ! command -v "$engine" >/dev/null 2>&1; then
        die "AMBER engine not found: $engine"
    fi
    if ! command -v "$python" >/dev/null 2>&1; then
        die "Python not found: $python"
    fi
    for input in "$topology" "$coordinates" "$config"; do
        if [[ ! -s "$input" ]]; then
            die "Shared build input is missing: $input"
        fi
    done
    "$python" ../helpers/input_identity.py --verify work
    identity_options=(--input "$topology" --input "$coordinates" --input "$config" --value "$engine")
    for stage in min-solvent min-all heat equil ratchet; do
        identity_options+=(--output "work/$stage.out" --output "work/.$stage.complete")
    done
    # An existing source identity must match before generated inputs are replaced.
    # On the first run it is recorded only after generate_inputs.py has resolved the
    # atom masks, so a corrected mask is not rejected as a changed input.
    source_identity_recorded=0
    if [[ -e work/.source.identity.json ]]; then
        "$python" ../helpers/input_identity.py --record work/.source.identity.json \
            --stage "rMD source configuration" "${identity_options[@]}"
        source_identity_recorded=1
    fi

    if [[ -e work/ratchet.out && ! -f work/.ratchet.complete ]]; then
        die_partial "" "ratchet MD" work/ratchet.out work/ratchet.rst7 \
            work/ratchet.info work/ratchet.nc work/ratchet.dat
    fi
    if ! (
        cd ..
        "$python" -B helpers/generate_inputs.py rmd work/resolved_config.toml rmd/work \
            --topology work/system.parm7
    ); then
        die "rMD input generation failed; see the Config error above. Atom masks are checked against $topology. Fix config.toml, move ../work aside (for example: mv ../work ../work.old), rerun ../build.sh, and then rerun $rerun_command."
    fi
    if (( ! source_identity_recorded )); then
        "$python" ../helpers/input_identity.py --record work/.source.identity.json \
            --stage "rMD source configuration" "${identity_options[@]}"
    fi
    cp "$topology" work/system.parm7
    cp "$coordinates" work/system.rst7
fi

if (( ! production_only )); then
    run_stage min-solvent "solvent minimization" system.rst7 \
        --reference system.rst7
    run_stage min-all "whole-system minimization" min-solvent.rst7
    run_stage heat "heating" min-all.rst7 --trajectory --reference min-all.rst7
    run_stage equil "equilibration" heat.rst7 --trajectory --reference heat.rst7
fi

if (( ! preparation_only )); then
    if (( ! dry_run )) && [[ ! -s work/equil.rst7 || ! -f work/.equil.complete ]]; then
        die "Completed equilibration output is required: work/equil.rst7"
    fi
    if (( ! dry_run )); then
        # config_utils provides the tomli fallback for Python 3.10.
        density_settings=$("$python" -B - "$config" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "../helpers")
from config_utils import load_config

config = load_config(Path(sys.argv[1]))
ratchet = config["ratchet_md"]
print(str(config["run"]["equilibration_ensemble"]).upper(),
      ratchet["minimum_density"], ratchet["maximum_density"])
PY
        )
        read -r equilibration_ensemble density_minimum density_maximum <<< "$density_settings"

        # AMBER prints Density only under constant pressure.
        if [[ "$equilibration_ensemble" == NVT ]]; then
            echo "Equilibration ensemble is NVT; density check skipped."
        else
            final_density=$(awk '
                /A V E R A G E S/ { exit }
                /Density/ { density = $3 }
                END { print density }
            ' work/equil.out)
            if [[ -z "$final_density" ]] || ! awk \
                -v density="$final_density" \
                -v minimum="$density_minimum" \
                -v maximum="$density_maximum" \
                'BEGIN { exit !(density >= minimum && density <= maximum) }'; then
                die "Equilibration density is outside ${density_minimum}-${density_maximum} g/cm^3: ${final_density:-missing}; check work/equil.out"
            fi
            echo "Equilibration final density: ${final_density} g/cm^3"
        fi
    fi
    run_stage ratchet "ratchet MD" equil.rst7 --trajectory
fi

if (( ! dry_run && ! preparation_only )); then
    echo "Ratchet-MD trajectory: work/ratchet.nc"
fi
