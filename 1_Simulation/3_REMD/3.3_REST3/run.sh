#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

source ./grompp_utils.bash

dry_run=0
cpu_count=""
gpu_count=""
while (( $# > 0 )); do
    case "$1" in
        --cpus|--gpus)
            option=$1
            if [[ $# -lt 2 ]]; then
                echo "Usage: $0 --cpus N --gpus N [--dry-run]" >&2
                exit 2
            fi
            if [[ "$option" == "--cpus" ]]; then
                cpu_count=$2
            else
                gpu_count=$2
            fi
            shift 2
            ;;
        --dry-run)
            dry_run=1
            shift
            ;;
        *)
            echo "Usage: $0 --cpus N --gpus N [--dry-run]" >&2
            exit 2
            ;;
    esac
done
if [[ -z "$cpu_count" || -z "$gpu_count" ]]; then
    echo "Usage: $0 --cpus N --gpus N [--dry-run]" >&2
    exit 2
fi

if (( ! ${dry_run:-0} )) &&
        [[ ${original_args[0]:-} != -h && ${original_args[0]:-} != --help && ${original_args[0]:-} != --dry-run ]] &&
        [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" helpers/writer_guard.py \
        --registry "work" --read "inputs" --write "work" -- "$0" "${original_args[@]}"
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

stage_status() {
    local stage=$1
    local complete=0
    local existing=0
    local stage_complete
    local replica

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        stage_complete=0
        if [[ -s "work/$replica/$stage.gro" ]]; then
            stage_complete=1
        fi
        if [[ "$stage" == equilibrate && ! -s "work/$replica/$stage.cpt" ]]; then
            stage_complete=0
        fi
        if (( stage_complete )); then
            complete=$((complete + 1))
        fi
        if [[ -e "work/$replica/$stage.gro" || -e "work/$replica/$stage.cpt" || -e "work/$replica/$stage.log" ]]; then
            existing=$((existing + 1))
        fi
    done < work/states.tsv

    if (( complete == replica_count )); then
        echo complete
    elif (( existing == 0 )); then
        echo missing
    else
        echo partial
    fi
}

wait_for_batch() {
    local stage=$1
    shift
    local job
    local failed=0

    for job in "$@"; do
        if ! wait "${job%%:*}"; then
            echo "Error: $stage failed: work/${job#*:}/$stage.mdrun.log" >&2
            failed=1
        fi
    done
    if (( failed )); then
        exit 1
    fi
}

check_stage_identity() {
    local stage=$1
    local input_coordinates=$2
    local replica
    local replica_dir
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        replica_dir="work/$replica"
        local identity_options=(
            --input work/states.tsv --input "$replica_dir/$stage.mdp"
            --input "$replica_dir/topol.top" --input "$replica_dir/$input_coordinates.gro"
        )
        if [[ "$stage" == production ]]; then
            identity_options+=(--input "$replica_dir/equilibrate.cpt" --input "$replica_dir/plumed.dat")
        fi
        local suffix
        for suffix in gro log tpr edr cpt grompp.log mdrun.log; do
            identity_options+=(--output "$replica_dir/$stage.$suffix")
        done
        "${PYTHON:-python3}" helpers/input_identity.py \
            --record "$replica_dir/.$stage.identity.json" --stage "replica $replica - $stage" \
            "${identity_options[@]}" --value="$gmx" --value="$gmx_mpi" --value="replex=1000"
    done < work/states.tsv
}

run_preproduction_stage() {
    local stage=$1
    local input_coordinates=$2
    local status
    local replica
    local replica_index=0
    local -a batch=()

    check_stage_identity "$stage" "$input_coordinates"
    status=$(stage_status "$stage")
    if [[ "$status" == complete ]]; then
        echo "Skipping completed stage: $stage"
        return
    fi
    if [[ "$status" == partial ]]; then
        echo "Warning: restarting incomplete stage for all replicas: $stage" >&2
    fi

    echo "Running: $stage"
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        replica_dir="work/$replica"

        if ! run_grompp "$replica_dir/$stage.grompp.log" \
            "$gmx" grompp \
            -f "$replica_dir/$stage.mdp" \
            -p "$replica_dir/topol.top" \
            -c "$replica_dir/$input_coordinates.gro" \
            -o "$replica_dir/$stage.tpr"; then
            echo "Error: $stage tpr generation failed: $replica_dir/$stage.grompp.log" >&2
            wait_for_batch "$stage" "${batch[@]}"
            exit 1
        fi

        gpu_id=$((replica_index % gpu_count))
        "$gmx" mdrun \
            -deffnm "$replica_dir/$stage" \
            -ntmpi 1 \
            -ntomp "$threads_per_replica" \
            -gpu_id "$gpu_id" \
            > "$replica_dir/$stage.mdrun.log" 2>&1 &
        batch+=("$!:$replica")
        replica_index=$((replica_index + 1))

        if (( ${#batch[@]} == gpu_count )); then
            wait_for_batch "$stage" "${batch[@]}"
            batch=()
        fi
    done < work/states.tsv

    if (( ${#batch[@]} > 0 )); then
        wait_for_batch "$stage" "${batch[@]}"
    fi
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        if [[ ! -s "work/$replica/$stage.gro" ]]; then
            die "$stage output was not created: work/$replica/$stage.gro"
        fi
        if [[ "$stage" == equilibrate && ! -s "work/$replica/$stage.cpt" ]]; then
            die "$stage checkpoint was not created: work/$replica/$stage.cpt"
        fi
    done < work/states.tsv
    echo "Completed: $stage (work)"
}

gmx=${GROMACS:-gmx}
gmx_mpi=${GROMACS_MPI:-gmx_mpi}
mpi_launcher=${MPI_LAUNCHER:-mpirun}

if [[ ! -s work/states.tsv ]]; then
    die "Run ./build.sh first."
fi
replica_count=$(awk 'NR > 1 {count++} END {print count + 0}' work/states.tsv)

if [[ ! "$cpu_count" =~ ^[1-9][0-9]*$ ]] || (( cpu_count % replica_count != 0 )); then
    die "--cpus must be a positive multiple of $replica_count."
fi
if [[ ! "$gpu_count" =~ ^[1-9][0-9]*$ ]] || (( gpu_count > replica_count )); then
    die "--gpus must be between 1 and $replica_count."
fi
threads_per_replica=$((cpu_count / replica_count))

gpu_ids=0
for ((gpu_index = 1; gpu_index < gpu_count; gpu_index++)); do
    gpu_ids+=",$gpu_index"
done

if (( dry_run )); then
    echo "Dry run: planned REST3 commands; no engine execution"
    printf '+ %q mdrun -deffnm %q -ntmpi 1 -ntomp %q -gpu_id 0\n' \
        "$gmx" work/000/equilibrate "$threads_per_replica"
    printf '+ %q -np %q %q mdrun -ntomp %q -gpu_id %q -multidir %q ... -deffnm production -hrex -replex 1000 -plumed plumed.dat\n' \
        "$mpi_launcher" "$replica_count" "$gmx_mpi" "$threads_per_replica" \
        "$gpu_ids" work/000
    exit 0
fi

"${PYTHON:-python3}" helpers/input_identity.py --verify work
source_options=(--input work/states.tsv)
for source_input in work/[0-9][0-9][0-9]/{system.gro,*.mdp,*.top,*.itp,plumed.dat}; do
    if [[ -f "$source_input" ]]; then
        source_options+=(--input "$source_input")
    fi
done
"${PYTHON:-python3}" helpers/input_identity.py \
    --record work/.source.identity.json --stage "REST build inputs" "${source_options[@]}"

for executable in "$gmx" "$gmx_mpi" "$mpi_launcher"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "Executable not found: $executable"
    fi
done

option_log=work/mdrun_option_check.log
if ! "$gmx_mpi" mdrun -h -hrex > "$option_log" 2>&1; then
    die "GROMACS does not recognize -hrex: $option_log"
fi
if ! grep -Fq HREX_WORKLOAD_FIX_1 "$option_log"; then
    die "GROMACS lacks the REST HREX swapped-energy fix: $option_log"
fi
if ! "$gmx_mpi" mdrun -h -plumed work/000/plumed.dat >> "$option_log" 2>&1; then
    die "GROMACS does not recognize -plumed: $option_log"
fi

if find work/[0-9][0-9][0-9] -maxdepth 1 \
    \( -name 'production.gro' -o -name 'production.cpt' -o -name 'production.log' \) \
    -print -quit 2>/dev/null | grep -q .; then
    die "Production output already exists in work."
fi

run_preproduction_stage minimize system
run_preproduction_stage equilibrate minimize

check_stage_identity production equilibrate

replica_dirs=()
while IFS=$'\t' read -r replica _; do
    if [[ "$replica" == replica ]]; then
        continue
    fi
    replica_dir="work/$replica"
    replica_dirs+=("$replica_dir")

        if ! run_grompp "$replica_dir/production.grompp.log" \
            "$gmx" grompp \
            -f "$replica_dir/production.mdp" \
            -p "$replica_dir/topol.top" \
            -c "$replica_dir/equilibrate.gro" \
            -t "$replica_dir/equilibrate.cpt" \
            -o "$replica_dir/production.tpr"; then
        die "Production tpr generation failed: $replica_dir/production.grompp.log"
    fi
done < work/states.tsv

echo "Running: 1 ns REST3 production"
if ! "$mpi_launcher" \
    -np "$replica_count" \
    "$gmx_mpi" mdrun \
    -ntomp "$threads_per_replica" \
    -gpu_id "$gpu_ids" \
    -multidir "${replica_dirs[@]}" \
    -deffnm production \
    -hrex \
    -replex 1000 \
    -plumed plumed.dat; then
    die "REST3 production failed; expected replica logs: work/<replica>/production.log (may be absent); see engine diagnostics above"
fi

for replica_dir in "${replica_dirs[@]}"; do
    if [[ ! -s "$replica_dir/production.gro" ]]; then
        die "Production output was not created: $replica_dir/production.gro"
    fi
done

echo "Completed 1 ns REST3: work"
