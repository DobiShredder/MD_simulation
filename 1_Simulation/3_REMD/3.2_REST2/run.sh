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

stage_state() {
    local stage=$1
    local marker="$work_dir/.$stage.complete"
    local existing=0
    local any_existing=0
    local replica
    local candidate

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == "replica" ]]; then
            continue
        fi
        if [[ "$stage" == preproduction ]]; then
            [[ ! -s "$work_dir/$replica/minimize.gro" ]] || existing=$((existing + 1))
            [[ ! -s "$work_dir/$replica/equilibrate.gro" ]] || existing=$((existing + 1))
            [[ ! -s "$work_dir/$replica/equilibrate.cpt" ]] || existing=$((existing + 1))
            for candidate in \
                "$work_dir/$replica"/minimize.{tpr,gro,log,edr,trr,cpt} \
                "$work_dir/$replica"/equilibrate.{tpr,gro,log,edr,trr,cpt} \
                "$work_dir/$replica"/{minimize,equilibrate}.{grompp,mdrun}.log; do
                [[ ! -e "$candidate" ]] || any_existing=1
            done
        else
            [[ ! -s "$work_dir/$replica/$stage.gro" ]] || existing=$((existing + 1))
            [[ ! -s "$work_dir/$replica/$stage.cpt" ]] || existing=$((existing + 1))
            for candidate in "$work_dir/$replica/$stage".{tpr,gro,cpt,log,edr,trr,xtc} \
                "$work_dir/$replica/$stage".{grompp,mdrun}.log; do
                [[ ! -e "$candidate" ]] || any_existing=1
            done
        fi
    done < "$states_file"
    local expected=$((replica_count * 2))
    [[ "$stage" != preproduction ]] || expected=$((replica_count * 3))
    if [[ -f "$marker" && "$existing" -eq "$expected" ]]; then
        echo complete
    elif [[ ! -f "$marker" && "$any_existing" -eq 0 ]]; then
        echo missing
    else
        echo partial
    fi
}

remove_preproduction_outputs() {
    local replica
    rm -f -- "$work_dir/.preproduction.complete"
    while IFS=$'\t' read -r replica _; do
        [[ "$replica" != replica ]] || continue
        rm -f -- "$work_dir/$replica"/minimize.{tpr,gro,log,edr,trr,cpt} \
            "$work_dir/$replica"/equilibrate.{tpr,gro,log,edr,trr,cpt} \
            "$work_dir/$replica"/{minimize,equilibrate}.{grompp,mdrun}.log
    done < "$states_file"
}

mark_gromacs_stage_complete() {
    local stage=$1
    local replica
    while IFS=$'\t' read -r replica _; do
        [[ "$replica" != replica ]] || continue
        if [[ "$stage" == preproduction ]]; then
            [[ -s "$work_dir/$replica/minimize.gro" &&
               -s "$work_dir/$replica/equilibrate.gro" &&
               -s "$work_dir/$replica/equilibrate.cpt" ]] || \
                die "preproduction output is incomplete: $work_dir/$replica"
        else
            [[ -s "$work_dir/$replica/$stage.gro" && -s "$work_dir/$replica/$stage.cpt" ]] || \
                die "$stage output is incomplete: $work_dir/$replica"
        fi
    done < "$states_file"
    touch "$work_dir/.$stage.complete"
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
    mark_gromacs_stage_complete preproduction
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

preproduction_state=$(stage_state preproduction)
if [[ "$preproduction_state" == missing ]]; then
    run_preproduction
elif [[ "$preproduction_state" == partial ]]; then
    echo "Warning: removing partial preproduction output from all replicas and restarting." >&2
    remove_preproduction_outputs
    run_preproduction
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
    production_state=$(stage_state "$segment_name")
    if [[ "$production_state" == complete ]]; then
        continue
    fi
    if [[ "$production_state" == partial ]]; then
        die "Partial production output detected: $segment_name"
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

    echo "Running REST2 production segment $segment/$production_segments."

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
        die "REST2 segment $segment run failed."
    fi
    mark_gromacs_stage_complete "$segment_name"
done

echo "Completed 1 ns REST2: $work_dir"
