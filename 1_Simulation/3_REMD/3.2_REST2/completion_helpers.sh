#!/usr/bin/env bash

# These helpers keep completion-marker bookkeeping separate from the GROMACS commands.
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
