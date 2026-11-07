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
        -h|--help)
            echo "Usage: $0 --cpus N --gpus N [--dry-run]"
            exit 0
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

rerun_command="./run.sh ${original_args[*]:-}"
rerun_command=${rerun_command% }

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
        local output
        for output in "work/$replica/$stage."{gro,cpt,log,tpr,edr,grompp.log,mdrun.log}; do
            if [[ -e "$output" || -L "$output" ]]; then
                existing=$((existing + 1))
                break
            fi
        done
    done < work/states.tsv

    if [[ -f "work/.$stage.complete" ]] && (( complete == replica_count )); then
        echo complete
    elif (( existing == 0 )) && [[ ! -e "work/.$stage.complete" && ! -L "work/.$stage.complete" ]]; then
        echo missing
    else
        echo partial
    fi
}

# Retained output is never moved here; print the manual recovery instead.
# All replicas of a stage rerun together, so the list spans every replica.
die_partial() {
    local stage=$1
    local replica suffix path
    local retained=()
    if [[ -e "work/.$stage.complete" || -L "work/.$stage.complete" ]]; then
        retained+=("work/.$stage.complete")
    fi
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        for suffix in gro cpt log tpr edr xtc grompp.log mdrun.log; do
            path="work/$replica/$stage.$suffix"
            if [[ -e "$path" || -L "$path" ]]; then
                retained+=("$path")
            fi
        done
    done < work/states.tsv
    die "Partial $stage output is retained for all replicas in work. Move these files out of work, keeping their replica directories, and rerun $rerun_command:
  for file in ${retained[*]:-}; do mkdir -p \"work.failed/\${file%/*}\"; mv \"\$file\" \"work.failed/\$file\"; done"
}

# Point to GROMACS replica logs after a failed multi-replica run.
report_replica_logs() {
    local replica_dir log
    local shown=0
    for replica_dir in "${replica_dirs[@]}"; do
        log="$replica_dir/production.log"
        if [[ ! -s "$log" ]]; then
            echo "Missing replica log: $log" >&2
        elif ! grep -q 'Finished mdrun' "$log"; then
            echo "Unfinished replica log: $log" >&2
            if (( ! shown )); then
                echo "Last 20 lines of $log:" >&2
                tail -n 20 "$log" >&2
                shown=1
            fi
        fi
    done
}

# Print the last 20 lines of a GROMACS stdout/stderr log after a failed call.
show_log_tail() {
    local log=$1
    if [[ -s "$log" ]]; then
        echo "Last 20 lines of $log:" >&2
        tail -n 20 "$log" >&2
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
            if (( ! failed )); then
                show_log_tail "work/${job#*:}/$stage.mdrun.log"
            fi
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
        identity_options+=(--output "work/.$stage.complete")
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
        die_partial "$stage"
    fi

    echo "Running: $stage"
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        replica_dir="work/$replica"
        expected_charge=$(replica_expected_charge "$charge_table" "$replica")

        if ! run_grompp "replica $replica" "$replica_dir/$stage.grompp.log" "$expected_charge" \
            "$gmx" grompp \
            -f "$replica_dir/$stage.mdp" \
            -p "$replica_dir/topol.top" \
            -c "$replica_dir/$input_coordinates.gro" \
            -o "$replica_dir/$stage.tpr"; then
            echo "Error: $stage tpr generation failed: $replica_dir/$stage.grompp.log" >&2
            show_log_tail "$replica_dir/$stage.grompp.log"
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
    touch "work/.$stage.complete"
    echo "Completed: $stage (work)"
}

gmx=${GROMACS:-gmx}
gmx_mpi=${GROMACS_MPI:-gmx_mpi}
mpi_launcher=${MPI_LAUNCHER:-mpirun}

if [[ ! -s work/states.tsv ]]; then
    die "Run ./build.sh first: work/states.tsv"
fi
# build.sh writes build.done only after every topology and energy check passes.
if [[ ! -f work/build.done ]]; then
    die "Build did not complete: work/build.done is missing. Check the ./build.sh error output, move work aside (for example: mv work work.old), and rerun ./build.sh."
fi
replica_count=$(awk 'NR > 1 {count++} END {print count + 0}' work/states.tsv)
if (( replica_count < 2 || replica_count % 2 != 0 )); then
    die "Replica exchange requires at least two and an even number of states: work/states.tsv ($replica_count states)"
fi

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

# build.sh writes the net charge GROMACS should report for each replica.
charge_table=work/net_charge.tsv
if [[ ! -s "$charge_table" ]]; then
    die "Expected net-charge table not found: $charge_table. Rebuild with ./build.sh."
fi
while IFS=$'\t' read -r replica _; do
    if [[ "$replica" == replica ]]; then
        continue
    fi
    if ! replica_expected_charge "$charge_table" "$replica" > /dev/null; then
        die "Expected net charge missing for replica $replica: $charge_table"
    fi
done < work/states.tsv

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

# Reuse a completed production before any GROMACS call; partial production
# output stops the run.
production_status=$(stage_status production)
if [[ "$production_status" == complete ]]; then
    echo "Skipping completed production: work"
    echo "Next: python3 anal.py"
    exit 0
fi
if [[ "$production_status" == partial ]]; then
    die_partial production
fi

option_log=work/mdrun_option_check.log
if ! "$gmx_mpi" mdrun -h -hrex > "$option_log" 2>&1; then
    die "GROMACS does not recognize -hrex: $option_log"
fi
# The PLUMED patch appends "plumed_X.Y.Z" to the GROMACS version. The GROMACS
# 2024 patch computes the HREX swapped-coordinate energy correctly only from
# PLUMED 2.10.2 (PLUMED issue #1326, fixed by PR #1505); older builds give
# near-zero acceptance.
version_log=work/gromacs_version.log
if ! "$gmx_mpi" --version > "$version_log" 2>&1; then
    die "Cannot read the GROMACS version: $version_log"
fi
if [[ ! "$(< "$version_log")" =~ plumed_([0-9]+)\.([0-9]+)\.([0-9]+) ]]; then
    die "GROMACS is not patched with PLUMED: $version_log"
fi
plumed_version="${BASH_REMATCH[1]}.${BASH_REMATCH[2]}.${BASH_REMATCH[3]}"
if (( BASH_REMATCH[1] * 10000 + BASH_REMATCH[2] * 100 + BASH_REMATCH[3] < 21002 )); then
    die "GROMACS was patched with PLUMED $plumed_version; REST HREX needs PLUMED 2.10.2 or later: $version_log"
fi
if ! "$gmx_mpi" mdrun -h -plumed work/000/plumed.dat >> "$option_log" 2>&1; then
    die "GROMACS does not recognize -plumed: $option_log"
fi

run_preproduction_stage minimize system
run_preproduction_stage equilibrate minimize

check_stage_identity production equilibrate
if [[ "$(stage_status production)" != missing ]]; then
    die_partial production
fi

replica_dirs=()
while IFS=$'\t' read -r replica _; do
    if [[ "$replica" == replica ]]; then
        continue
    fi
    replica_dir="work/$replica"
    replica_dirs+=("$replica_dir")
    expected_charge=$(replica_expected_charge "$charge_table" "$replica")

    if ! run_grompp "replica $replica" "$replica_dir/production.grompp.log" "$expected_charge" \
        "$gmx" grompp \
        -f "$replica_dir/production.mdp" \
        -p "$replica_dir/topol.top" \
        -c "$replica_dir/equilibrate.gro" \
        -t "$replica_dir/equilibrate.cpt" \
        -o "$replica_dir/production.tpr"; then
        show_log_tail "$replica_dir/production.grompp.log"
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
    report_replica_logs
    die "REST3 production failed; replica logs: work/<replica>/production.log"
fi

for replica_dir in "${replica_dirs[@]}"; do
    if [[ ! -s "$replica_dir/production.gro" ]]; then
        die "Production output was not created: $replica_dir/production.gro"
    fi
done

touch work/.production.complete

echo "Completed 1 ns REST3: work"
