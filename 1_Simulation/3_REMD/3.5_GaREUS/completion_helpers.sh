#!/usr/bin/env bash

completed_stage_count() {
    local stage=$1
    shift
    local require_gamd_log=0
    local allow_partial=0
    local completed=0
    local existing
    local replica
    local replica_dir
    local required

    while (( $# > 0 )); do
        case "$1" in
            --require-gamd-log)
                require_gamd_log=1
                ;;
            --allow-partial)
                allow_partial=1
                ;;
            *)
                die "Unknown completed_stage_count option: $1"
                ;;
        esac
        shift
    done

    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == "replica" ]]; then
            continue
        fi

        replica_dir="$work_dir/$replica"
        required=(
            "$replica_dir/$stage.out"
            "$replica_dir/$stage.rst7"
            "$replica_dir/$stage.nc"
            "$replica_dir/$stage.info"
        )
        if (( require_gamd_log )); then
            required+=("$replica_dir/gamd.$stage.log")
        fi

        existing=0
        for output in "${required[@]}"; do
            [[ ! -s "$output" ]] || existing=$((existing + 1))
        done

        if [[ "$existing" -eq "${#required[@]}" ]]; then
            completed=$((completed + 1))
        elif [[ "$existing" -ne 0 ]] && (( ! allow_partial )); then
            die "$stage output is only partially present: $replica_dir"
        fi
    done < "$states_file"

    echo "$completed"
}

remove_stage_outputs() {
    local stage=$1
    local replica
    rm -f -- "$work_dir/.$stage.complete"
    while IFS=$'\t' read -r replica _; do
        [[ "$replica" != replica ]] || continue
        rm -f -- "$work_dir/$replica/$stage.out" "$work_dir/$replica/$stage.rst7" \
            "$work_dir/$replica/$stage.nc" "$work_dir/$replica/$stage.info"
    done < "$states_file"
}
