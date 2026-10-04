#!/usr/bin/env bash

# Completion markers are created only after every window has all stage outputs.
stage_state() {
    local stage=$1
    local marker="$work_dir/.$stage.complete"
    local existing=0
    local complete=0
    local expected=$((replica_count * 4))
    if [[ "$stage" == minimize ]]; then
        expected=$((replica_count * 3))
    fi
    local replica
    local suffix

    while IFS=$'\t' read -r replica _; do
        [[ "$replica" != replica ]] || continue
        for suffix in out rst7 info nc; do
            if [[ -e "$work_dir/$replica/$stage.$suffix" ]]; then
                existing=$((existing + 1))
            fi
            if [[ -s "$work_dir/$replica/$stage.$suffix" ]] &&
                    [[ "$stage" != minimize || "$suffix" != nc ]]; then
                complete=$((complete + 1))
            fi
        done
    done < "$states_file"

    if [[ -f "$marker" && "$complete" -eq "$expected" ]]; then
        echo complete
    elif [[ ! -f "$marker" && "$existing" -eq 0 ]]; then
        echo missing
    else
        echo partial
    fi
}


mark_stage_complete() {
    local stage=$1
    local replica
    local suffix
    local required=(out rst7 info)
    if [[ "$stage" != minimize ]]; then
        required+=(nc)
    fi
    while IFS=$'\t' read -r replica _; do
        [[ "$replica" != replica ]] || continue
        for suffix in "${required[@]}"; do
            if [[ ! -s "$work_dir/$replica/$stage.$suffix" ]]; then
                die "$stage output is incomplete: $work_dir/$replica/$stage.$suffix"
            fi
        done
    done < "$states_file"
    touch "$work_dir/.$stage.complete"
}
