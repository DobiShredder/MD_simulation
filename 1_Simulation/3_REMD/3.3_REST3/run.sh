#!/usr/bin/env bash
set -euo pipefail

dry_run=0

if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi

if [[ $# -ne 0 ]]; then
    echo "Usage: $0 [--dry-run]" >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

work_dir=${WORK_DIR:-work}
states_file="$work_dir/states.tsv"
gmx=${GROMACS:-gmx}
gmx_mpi=${GROMACS_MPI:-gmx_mpi}
mpi_launcher=${MPI_LAUNCHER:-mpirun}
production_segments=1
exchange_steps=1000

read -r -a mpi_options <<< "${MPI_OPTIONS:-}"
read -r -a gromacs_options <<< "${GROMACS_OPTIONS:-}"

if [[ ! -s "$states_file" ]]; then
    die "Run build.sh first: $states_file"
fi

replica_count=$(awk 'NR > 1 {count++} END {print count + 0}' "$states_file")
mpi_processes=${MPI_PROCESSES:-$replica_count}
temperature_min=$(awk 'NR == 2 {print $2}' "$states_file")
temperature_max=$(awk 'END {print $2}' "$states_file")
last_replica=$(awk 'END {print $1}' "$states_file")

if [[ "$mpi_processes" -ne "$replica_count" ]]; then
    die "MPI_PROCESSES must equal the replica count: $replica_count"
fi

if (( ! dry_run )); then
    for executable in "$gmx" "$gmx_mpi" "$mpi_launcher"; do
        if ! command -v "$executable" >/dev/null 2>&1; then
            die "Executable not found: $executable"
        fi
    done

    option_check_log="$work_dir/mdrun_option_check.log"
    if ! "$gmx_mpi" mdrun -h -hrex > "$option_check_log" 2>&1; then
        die "GROMACS MPI build does not recognize the -hrex option: $option_check_log"
    fi
    if ! "$gmx_mpi" mdrun \
        -h \
        -plumed "$work_dir/000/plumed.dat" \
        >> "$option_check_log" 2>&1; then
        die "GROMACS MPI build does not recognize the -plumed option: $option_check_log"
    fi
fi

stage_status() {
    local filename=$1
    local completed=0
    local replica

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == "replica" ]]; then
            continue
        fi
        if [[ -s "$work_dir/$replica/$filename" ]]; then
            completed=$((completed + 1))
        fi
    done < "$states_file"

    echo "$completed"
}

run_preproduction() {
    local replica
    local replica_dir

    echo "Running minimization and 100 ps equilibration."

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == "replica" ]]; then
            continue
        fi
        replica_dir="$work_dir/$replica"

        if ! "$gmx" grompp \
            -f "$replica_dir/minimize.mdp" \
            -p "$replica_dir/topol.top" \
            -c "$replica_dir/system.gro" \
            -o "$replica_dir/minimize.tpr" \
            -maxwarn 1 \
            > "$replica_dir/minimize.grompp.log" 2>&1; then
            die "minimization tpr generation failed: $replica_dir/minimize.grompp.log"
        fi

        if ! "$gmx" mdrun \
            -deffnm "$replica_dir/minimize" \
            "${gromacs_options[@]}" \
            > "$replica_dir/minimize.mdrun.log" 2>&1; then
            die "minimization failed: $replica_dir/minimize.mdrun.log"
        fi

        if ! "$gmx" grompp \
            -f "$replica_dir/equilibrate.mdp" \
            -p "$replica_dir/topol.top" \
            -c "$replica_dir/minimize.gro" \
            -o "$replica_dir/equilibrate.tpr" \
            -maxwarn 1 \
            > "$replica_dir/equilibrate.grompp.log" 2>&1; then
            die "equilibration tpr generation failed: $replica_dir/equilibrate.grompp.log"
        fi

        if ! "$gmx" mdrun \
            -deffnm "$replica_dir/equilibrate" \
            "${gromacs_options[@]}" \
            > "$replica_dir/equilibrate.mdrun.log" 2>&1; then
            die "equilibration failed: $replica_dir/equilibrate.mdrun.log"
        fi
    done < "$states_file"
}

if (( dry_run )); then
    echo "GROMACS: $gmx"
    echo "HREX engine: $gmx_mpi"
    echo "$replica_count replicas, effective ${temperature_min}–${temperature_max} K, 2 ps exchange interval"
    echo "100 ps equilibration + 1 ns production"
    printf '%q ' "$mpi_launcher" "${mpi_options[@]}" -np "$mpi_processes" "$gmx_mpi" mdrun -multidir "$work_dir/000" ... "$work_dir/$last_replica" -deffnm production.001 -hrex -replex "$exchange_steps" -plumed plumed.dat
    printf '\n'
    exit 0
fi

equilibrated=$(stage_status equilibrate.cpt)
if [[ "$equilibrated" -eq 0 ]]; then
    run_preproduction
elif [[ "$equilibrated" -ne "$replica_count" ]]; then
    die "Only some replicas completed equilibration ($equilibrated/$replica_count)."
fi

replica_dirs=()
while IFS=$'\t' read -r replica _; do
    if [[ "$replica" == "replica" ]]; then
        continue
    fi
    replica_dirs+=("$work_dir/$replica")
done < "$states_file"

for segment in $(seq 1 "$production_segments"); do
    segment_name=$(printf 'production.%03d' "$segment")
    completed=$(stage_status "$segment_name.cpt")

    if [[ "$completed" -eq "$replica_count" ]]; then
        continue
    fi

    if [[ "$completed" -ne 0 ]]; then
        die "Only some replicas completed $segment_name ($completed/$replica_count)."
    fi

    if [[ "$segment" -eq 1 ]]; then
        previous_name=equilibrate
    else
        previous_name=$(printf 'production.%03d' "$((segment - 1))")
    fi

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == "replica" ]]; then
            continue
        fi
        replica_dir="$work_dir/$replica"

        if ! "$gmx" grompp \
            -f "$replica_dir/production.mdp" \
            -p "$replica_dir/topol.top" \
            -c "$replica_dir/$previous_name.gro" \
            -t "$replica_dir/$previous_name.cpt" \
            -o "$replica_dir/$segment_name.tpr" \
            -maxwarn 1 \
            > "$replica_dir/$segment_name.grompp.log" 2>&1; then
            die "production tpr generation failed: $replica_dir/$segment_name.grompp.log"
        fi
    done < "$states_file"

    echo "Running REST3 production segment $segment/$production_segments."

    if ! "$mpi_launcher" \
        "${mpi_options[@]}" \
        -np "$mpi_processes" \
        "$gmx_mpi" \
        mdrun \
        -multidir "${replica_dirs[@]}" \
        -deffnm "$segment_name" \
        -hrex \
        -replex "$exchange_steps" \
        -plumed plumed.dat \
        "${gromacs_options[@]}"; then
        die "REST3 segment $segment run failed."
    fi
done

echo "Completed 1 ns REST3: $work_dir"
