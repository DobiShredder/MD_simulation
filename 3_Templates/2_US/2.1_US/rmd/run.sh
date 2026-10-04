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
    local command=(
        "$engine" -O
        -i "inputs/$stage.in"
        -o "$stage.out"
        -p system.parm7
        -c "$input_restart"
        -r "$stage.rst7"
    )
    if (( trajectory )); then
        required+=("$prefix.info" "$prefix.nc")
        command+=(-x "$stage.nc" -inf "$stage.info")
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
            die "Partial $label output detected and retained: $prefix"
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
        "${command[@]}"
    ); then
        die "$label failed: $prefix.out"
    fi
    local output
    for output in "${required[@]}"; do
        if [[ ! -s "$output" ]]; then
            die "$label output is incomplete: $output"
        fi
    done
    touch "$marker"
    echo "Completed: rMD - $label ($prefix)"
}

if (( ! ${dry_run:-0} )) && [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" ../helpers/writer_guard.py \
        --registry "../work" --read "../work" --write work -- "$0" "${original_args[@]}"
fi
engine=$("${PYTHON:-python3}" ../helpers/config_utils.py "../work/resolved_config.toml" engine AMBER_ENGINE pmemd.cuda)
python=${PYTHON:-python3}
topology=../work/system.parm7
coordinates=../work/system.rst7
config=../work/resolved_config.toml

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
    "$python" ../helpers/input_identity.py --record work/.source.identity.json \
        --stage "rMD source configuration" "${identity_options[@]}"

    if [[ -e work/ratchet.out && ! -f work/.ratchet.complete ]]; then
        die "Partial ratchet-MD output detected: work/ratchet"
    fi
    (
        cd ..
        "$python" -B helpers/generate_inputs.py rmd work/resolved_config.toml rmd/work \
            --topology work/system.parm7
    )
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
        read -r density_minimum density_maximum < <(
            "$python" -B - "$config" <<'PY'
import sys
import tomllib
with open(sys.argv[1], "rb") as handle:
    values = tomllib.load(handle)["ratchet_md"]
print(values["minimum_density"], values["maximum_density"])
PY
        )
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
    run_stage ratchet "ratchet MD" equil.rst7 --trajectory
fi

if (( ! dry_run )); then
    echo "Ratchet-MD trajectory: work/ratchet.nc"
fi
