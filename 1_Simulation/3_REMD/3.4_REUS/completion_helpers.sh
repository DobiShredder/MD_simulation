#!/usr/bin/env bash

# Completion markers are created only after every window has all stage outputs.
stage_state() {
    local stage=$1
    local marker="$work_dir/.$stage.complete"
    local existing=0
    local expected=$((replica_count * 4))
    local replica
    local suffix

    while IFS=$'\t' read -r replica _; do
        [[ "$replica" != replica ]] || continue
        for suffix in out rst7 info nc; do
            [[ ! -s "$work_dir/$replica/$stage.$suffix" ]] || existing=$((existing + 1))
        done
    done < "$states_file"

    if [[ -f "$marker" && "$existing" -eq "$expected" ]]; then
        echo complete
    elif [[ ! -f "$marker" && "$existing" -eq 0 ]]; then
        echo missing
    else
        echo partial
    fi
}

remove_stage_outputs() {
    local stage=$1
    local replica
    rm -f -- "$work_dir/.$stage.complete"
    while IFS=$'\t' read -r replica _; do
        [[ "$replica" != replica ]] || continue
        rm -f -- "$work_dir/$replica/$stage.out" "$work_dir/$replica/$stage.rst7" \
            "$work_dir/$replica/$stage.info" "$work_dir/$replica/$stage.nc"
    done < "$states_file"
}

mark_stage_complete() {
    local stage=$1
    local replica
    local suffix
    while IFS=$'\t' read -r replica _; do
        [[ "$replica" != replica ]] || continue
        for suffix in out rst7 info nc; do
            if [[ ! -s "$work_dir/$replica/$stage.$suffix" ]]; then
                die "$stage output is incomplete: $work_dir/$replica/$stage.$suffix"
            fi
        done
    done < "$states_file"
    touch "$work_dir/.$stage.complete"
}
