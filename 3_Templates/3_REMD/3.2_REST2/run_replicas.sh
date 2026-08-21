#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
    cat <<'EOF'
Usage: ./run_replicas.sh METHOD [--cpus N] [--gpus N] [--preparation-only | --production-only] [--segments START-END] [--dry-run]

Shared internal runner used by the REST2 and REST3 run.sh wrappers.
METHOD must be rest2 or rest3.

Options:
  --cpus N       Override the total CPU count.
  --gpus N       Override the number of GPU devices.
  --preparation-only  Run through equilibration and stop.
  --production-only   Run production from completed equilibration.
  --segments RANGE    Run an inclusive 1-based production segment range.
  --dry-run      Print the resolved command without running it.
  -h, --help     Show this help message and exit.
EOF
    exit 0
fi
if [[ $# -lt 1 ]]; then
    echo "Error: METHOD is required." >&2
    exit 2
fi
method=$1
shift
if [[ "$method" != rest2 && "$method" != rest3 ]]; then
    echo "Error: METHOD must be rest2 or rest3." >&2
    exit 2
fi
dry_run=0
cpu_count=""
gpu_count=""
preparation_only=0
production_only=0
segment_range=""

show_help() {
    cat <<EOF
Usage: ./run.sh [--cpus N] [--gpus N] [--preparation-only | --production-only] [--segments START-END] [--dry-run]

Run $method preproduction and replica-exchange production. The CPU count must
be divisible by the generated replica count.

Options:
  --cpus N       Override the total CPU count.
  --gpus N       Override the number of GPU devices.
  --preparation-only  Run through equilibration and stop.
  --production-only   Run production from completed equilibration.
  --segments RANGE    Run an inclusive 1-based production segment range.
  --dry-run      Print the resolved multi-replica command without running it.
  -h, --help     Show this help message and exit.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --cpus)
            if [[ $# -lt 2 ]]; then
                echo "Error: --cpus requires a value." >&2
                exit 2
            fi
            cpu_count=$2
            shift 2
            ;;
        --gpus)
            if [[ $# -lt 2 ]]; then
                echo "Error: --gpus requires a value." >&2
                exit 2
            fi
            gpu_count=$2
            shift 2
            ;;
        --dry-run)
            dry_run=1
            shift
            ;;
        --preparation-only)
            preparation_only=1
            shift
            ;;
        --production-only)
            production_only=1
            shift
            ;;
        --segments)
            if [[ $# -lt 2 ]]; then
                echo "Error: --segments requires START-END." >&2
                exit 2
            fi
            segment_range=$2
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            break
            ;;
    esac
done
if [[ $# -ne 0 ]]; then
    show_help >&2
    exit 2
fi
if (( preparation_only && production_only )); then
    echo "Error: --preparation-only and --production-only cannot be used together." >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

work_dir=${WORK_DIR:-work}
states="$work_dir/states.tsv"
resolved="$work_dir/resolved_config.toml"
gmx=${GROMACS:-gmx}
gmx_mpi=${GROMACS_MPI:-gmx_mpi}
mpi_launcher=${MPI_LAUNCHER:-mpirun}
if [[ ! -s "$states" || ! -s "$resolved" ]]; then
    die "Run ./build.sh first."
fi

replica_count=$(awk 'NR > 1 {count++} END {print count + 0}' "$states")
default_threads=$(awk -F' = ' '$1=="cpu_threads_per_replica" {print $2}' "$resolved")
default_gpus=$(awk -F' = ' '$1=="gpu_count" {print $2}' "$resolved")
segments=$(awk -F' = ' '$1=="production_segments" {print $2}' "$resolved")
exchange_interval=$(awk -F' = ' '$1=="exchange_interval_steps" {print $2}' "$resolved")
cpu_count=${cpu_count:-$((replica_count * default_threads))}
gpu_count=${gpu_count:-$default_gpus}
segment_start=1
segment_end=$segments
if [[ -n "$segment_range" ]]; then
    if [[ ! "$segment_range" =~ ^([1-9][0-9]*)-([1-9][0-9]*)$ ]]; then
        die "--segments must use START-END with 1-based indices"
    fi
    segment_start=${BASH_REMATCH[1]}
    segment_end=${BASH_REMATCH[2]}
    if (( segment_start > segment_end || segment_end > segments )); then
        die "Segment range is outside 1-$segments: $segment_range"
    fi
fi

if [[ ! "$cpu_count" =~ ^[1-9][0-9]*$ ]]; then
    die "--cpus must be a positive integer."
fi
if [[ ! "$gpu_count" =~ ^[1-9][0-9]*$ ]]; then
    die "--gpus must be a positive integer."
fi
if (( cpu_count % replica_count != 0 )); then
    die "--cpus must be divisible by the replica count ($replica_count)."
fi
if (( gpu_count > replica_count )); then
    die "--gpus cannot exceed the replica count ($replica_count)."
fi
threads_per_replica=$((cpu_count / replica_count))

gpu_ids=0
for ((gpu_index = 1; gpu_index < gpu_count; gpu_index++)); do
    gpu_ids+=",$gpu_index"
done
read -r -a mpi_options <<< "${MPI_OPTIONS:-}"
read -r -a gromacs_options <<< "${GROMACS_OPTIONS:-}"

if (( ! dry_run )); then
    for executable in "$gmx" "$gmx_mpi" "$mpi_launcher"; do
        if ! command -v "$executable" >/dev/null 2>&1; then
            die "Executable not found: $executable"
        fi
    done
    option_log="$work_dir/mdrun_option_check.log"
    if ! "$gmx_mpi" mdrun -h -hrex > "$option_log" 2>&1; then
        die "The GROMACS MPI build does not recognize -hrex: $option_log"
    fi
    if ! grep -Fq HREX_WORKLOAD_FIX_1 "$option_log"; then
        die "The GROMACS build lacks the required HREX swapped-energy fix: $option_log"
    fi
fi

replica_dirs=()
while IFS=$'\t' read -r replica _; do
    if [[ "$replica" == replica ]]; then
        continue
    fi
    replica_dirs+=("$work_dir/$replica")
done < "$states"

if (( dry_run )); then
    echo "$method: $replica_count replicas, $segments production segments"
    echo "Resources: $cpu_count CPUs, $gpu_count GPUs, $threads_per_replica threads per replica"
    if (( ! production_only )); then
        printf '+ %q grompp -f %q -p %q -c %q -o %q\n' \
            "$gmx" "$work_dir/000/minimize.mdp" "$work_dir/000/topol.top" \
            "$work_dir/000/system.gro" "$work_dir/000/minimize.tpr"
    fi
    if (( ! preparation_only )); then
        for ((segment = segment_start; segment <= segment_end; segment++)); do
            printf -v segment_name 'production.%03d' "$segment"
            printf '+'
            printf ' %q' "$mpi_launcher" "${mpi_options[@]}" -np "$replica_count" "$gmx_mpi" mdrun -ntomp "$threads_per_replica" -gpu_id "$gpu_ids" -multidir
            printf ' %q' "${replica_dirs[@]}"
            printf ' %q' -deffnm "$segment_name" -hrex -replex "$exchange_interval" -plumed plumed.dat
            printf '\n'
        done
    fi
    exit 0
fi

run_preproduction_stage() {
    local stage=$1
    local previous=$2
    local marker="$work_dir/.$stage.complete"
    local partial_output=""
    local requires_checkpoint=1
    if [[ "$stage" == minimize ]]; then
        requires_checkpoint=0
    fi
    for replica_dir in "${replica_dirs[@]}"; do
        if [[ -f "$marker" && ! -s "$replica_dir/$stage.gro" ]]; then
            partial_output=$replica_dir
            break
        fi
        if [[ -f "$marker" && "$requires_checkpoint" -eq 1 && ! -s "$replica_dir/$stage.cpt" ]]; then
            partial_output=$replica_dir
            break
        fi
        if [[ ! -f "$marker" && ( -e "$replica_dir/$stage.log" || -e "$replica_dir/$stage.gro" || -e "$replica_dir/$stage.cpt" ) ]]; then
            partial_output=$replica_dir
            break
        fi
    done
    if [[ -f "$marker" && -z "$partial_output" ]]; then
        return
    fi
    if [[ -n "$partial_output" ]]; then
        echo "Warning: removing partial $stage output from all replicas and restarting the stage." >&2
        for replica_dir in "${replica_dirs[@]}"; do
            rm -f -- "$replica_dir/$stage."{tpr,log,edr,gro,cpt,trr,xtc} "$replica_dir/$stage.grompp.log" "$replica_dir/$stage.mdrun.log"
        done
    fi
    local replica replica_dir gpu_id process_id
    local replica_index=0
    local -a jobs=()
    echo "Running: $method $stage"
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        replica_dir="$work_dir/$replica"
        grompp_command=("$gmx" grompp -f "$replica_dir/$stage.mdp" -p "$replica_dir/topol.top"
            -c "$replica_dir/$previous.gro" -o "$replica_dir/$stage.tpr")
        if [[ "$previous" != system && "$previous" != minimize ]]; then
            grompp_command+=(-t "$replica_dir/$previous.cpt")
        fi
        if ! "${grompp_command[@]}" > "$replica_dir/$stage.grompp.log" 2>&1; then
            die "$stage tpr generation failed: $replica_dir/$stage.grompp.log"
        fi
        gpu_id=$((replica_index % gpu_count))
        "$gmx" mdrun -deffnm "$replica_dir/$stage" -ntmpi 1 \
            -ntomp "$threads_per_replica" -gpu_id "$gpu_id" "${gromacs_options[@]}" \
            > "$replica_dir/$stage.mdrun.log" 2>&1 &
        jobs+=("$!:$replica")
        replica_index=$((replica_index + 1))
        if (( ${#jobs[@]} == gpu_count )); then
            for process_id in "${jobs[@]}"; do
                if ! wait "${process_id%%:*}"; then
                    die "$stage failed: $work_dir/${process_id#*:}/$stage.mdrun.log"
                fi
            done
            jobs=()
        fi
    done < "$states"
    for process_id in "${jobs[@]}"; do
        if ! wait "${process_id%%:*}"; then
            die "$stage failed: $work_dir/${process_id#*:}/$stage.mdrun.log"
        fi
    done
    for replica_dir in "${replica_dirs[@]}"; do
        if [[ ! -s "$replica_dir/$stage.gro" ]]; then
            die "$stage output was not created: $replica_dir/$stage.gro"
        fi
        if (( requires_checkpoint )); then
            if [[ ! -s "$replica_dir/$stage.cpt" ]]; then
                die "$stage checkpoint was not created: $replica_dir/$stage.cpt"
            fi
        fi
    done
    touch "$marker"
}

if (( ! production_only )); then
    run_preproduction_stage minimize system
    run_preproduction_stage equilibrate minimize
fi
if (( preparation_only )); then
    exit 0
fi
if [[ ! -f "$work_dir/.equilibrate.complete" ]]; then
    die "Completed equilibration output is required for production."
fi
if (( segment_start > 1 )); then
    printf -v previous_segment 'production.%03d' "$((segment_start - 1))"
    if [[ ! -f "$work_dir/.$previous_segment.complete" ]]; then
        die "Previous production segment is incomplete: $previous_segment"
    fi
    for replica_dir in "${replica_dirs[@]}"; do
        if [[ ! -s "$replica_dir/$previous_segment.gro" || ! -s "$replica_dir/$previous_segment.cpt" ]]; then
            die "Previous production segment is incomplete: $replica_dir/$previous_segment"
        fi
    done
fi

for ((segment = segment_start; segment <= segment_end; segment++)); do
    printf -v segment_name 'production.%03d' "$segment"
    marker="$work_dir/.$segment_name.complete"
    production_state=missing
    for replica_dir in "${replica_dirs[@]}"; do
        if [[ -f "$marker" && ( ! -s "$replica_dir/$segment_name.gro" || ! -s "$replica_dir/$segment_name.cpt" ) ]]; then
            production_state=partial
            break
        fi
        if [[ ! -f "$marker" && ( -e "$replica_dir/$segment_name.log" || -e "$replica_dir/$segment_name.gro" || -e "$replica_dir/$segment_name.cpt" ) ]]; then
            production_state=partial
            break
        fi
    done
    if [[ -f "$marker" && "$production_state" == missing ]]; then
        continue
    fi
    if [[ "$production_state" == partial ]]; then
        die "Partial production output detected: $segment_name"
    fi
    if (( segment == 1 )); then
        previous=equilibrate
    else
        printf -v previous 'production.%03d' "$((segment - 1))"
    fi
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        replica_dir="$work_dir/$replica"
        if ! "$gmx" grompp -f "$replica_dir/production.mdp" -p "$replica_dir/topol.top" \
            -c "$replica_dir/$previous.gro" -t "$replica_dir/$previous.cpt" \
            -o "$replica_dir/$segment_name.tpr" > "$replica_dir/$segment_name.grompp.log" 2>&1; then
            die "Production tpr generation failed: $replica_dir/$segment_name.grompp.log"
        fi
    done < "$states"
    echo "Running: $method production segment $segment/$segments"
    command=("$mpi_launcher" "${mpi_options[@]}" -np "$replica_count" "$gmx_mpi" mdrun
        -ntomp "$threads_per_replica" -gpu_id "$gpu_ids" -multidir "${replica_dirs[@]}"
        -deffnm "$segment_name" -replex "$exchange_interval")
    command+=(-hrex -plumed plumed.dat)
    command+=("${gromacs_options[@]}")
    if ! "${command[@]}"; then
        die "$method production segment $segment failed."
    fi
    for replica_dir in "${replica_dirs[@]}"; do
        if [[ ! -s "$replica_dir/$segment_name.gro" ]]; then
            die "Production output was not created: $replica_dir/$segment_name.gro"
        fi
        if [[ ! -s "$replica_dir/$segment_name.cpt" ]]; then
            die "Production checkpoint was not created: $replica_dir/$segment_name.cpt"
        fi
    done
    touch "$marker"
done

echo "Completed $method production: $work_dir"
