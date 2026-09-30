#!/usr/bin/env bash

completed_stage_count() {
    local stage=$1
    shift
    local require_gamd_log=0
    local allow_partial=0
    local require_complete=0
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
            --require-complete)
                require_complete=1
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
            "$replica_dir/$stage.info"
        )
        if [[ "$stage" != minimize ]]; then
            required+=("$replica_dir/$stage.nc")
        fi
        if (( require_gamd_log )); then
            required+=("$replica_dir/gamd.$stage.log")
            required+=("$replica_dir/restraint.$stage.dat")
        fi

        existing=0
        for output in "${required[@]}"; do
            if (( require_complete )) && [[ ! -s "$output" ]]; then
                die "$stage output is incomplete: $output; existing files were preserved."
            fi
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

# A marker is trusted only together with every required replica output.
stage_state() {
    local stage=$1
    shift
    local completed replica output
    completed=$(completed_stage_count "$stage" "$@" --allow-partial)
    if [[ -f "$work_dir/.$stage.complete" && "$completed" -eq "$replica_count" ]]; then
        if [[ "$stage" == production.* && ! -s "$work_dir/exchange.${stage#production.}.log" ]]; then
            echo partial
            return
        fi
        echo complete
        return
    fi
    if [[ -e "$work_dir/.$stage.complete" ]]; then
        echo partial
        return
    fi
    if [[ "$stage" == production.* && -e "$work_dir/exchange.${stage#production.}.log" ]]; then
        echo partial
        return
    fi
    while IFS=$'\t' read -r replica _; do
        if [[ "$replica" == replica ]]; then
            continue
        fi
        for output in "$work_dir/$replica/$stage."{out,rst7,nc,info} \
            "$work_dir/$replica/gamd.$stage.log" "$work_dir/$replica/restraint.$stage.dat"; do
            if [[ -e "$output" ]]; then
                echo partial
                return
            fi
        done
    done < "$states_file"
    echo missing
}
