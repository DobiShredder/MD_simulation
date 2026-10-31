#!/usr/bin/env bash

# REST scales hot solute charges by sqrt(lambda_pp) while ions stay cold, so a
# scaled replica has the net charge Q_ref + q_hot * (sqrt(lambda_pp) - 1).
# build.sh writes that value to work/net_charge.tsv. GROMACS reports a net
# charge with one Ewald warning and adds a uniform neutralizing background.
# run_grompp accepts only that warning, and only at the expected charge.

net_charge_tolerance_e=0.01

# Print the last column (expected_charge_e) of one replica row.
replica_expected_charge() {
    local charge_table=$1
    local replica=$2

    awk -F '\t' -v replica="$replica" \
        '$1 == replica {print $NF; found = 1; exit} END {exit !found}' \
        "$charge_table"
}

# Succeed only when the log has exactly one WARNING and it is the GROMACS
# topio.cpp message "You are using Ewald electrostatics in a system with net
# charge. ..." The message is line-wrapped, so its lines are joined first.
grompp_has_only_net_charge_warning() {
    local log_file=$1

    awk '
        /^WARNING [0-9]+( \[|:)/ {count++; in_warning = 1; next}
        in_warning && NF == 0 {in_warning = 0}
        in_warning {text = text " " $0}
        END {
            gsub(/[[:space:]]+/, " ", text)
            found = index(text, "Ewald electrostatics in a system with net charge")
            exit !(count == 1 && found > 0)
        }' "$log_file"
}

# Check the warning and the reported total charge. Print the reported charge.
grompp_net_charge_matches() {
    local log_file=$1
    local expected_charge=$2
    local total_charge

    if ! grompp_has_only_net_charge_warning "$log_file"; then
        return 1
    fi

    total_charge=$(awk '/System has non-zero total charge:/ {print $NF; exit}' "$log_file")
    if [[ ! "$total_charge" =~ ^[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?$ ]]; then
        return 1
    fi
    echo "$total_charge"

    awk -v charge="$total_charge" -v expected="$expected_charge" -v tolerance="$net_charge_tolerance_e" \
        'BEGIN {difference = charge - expected; exit !(difference >= -tolerance && difference <= tolerance)}'
}

# Usage: run_grompp LABEL LOG_FILE EXPECTED_CHARGE_E gmx grompp ...
run_grompp() {
    local label=$1
    local log_file=$2
    local expected_charge=$3
    local total_charge
    shift 3

    if [[ ! "$expected_charge" =~ ^[-+]?[0-9]*\.?[0-9]+$ ]]; then
        echo "Error: $label: invalid expected net charge '$expected_charge' for $log_file" >&2
        return 1
    fi

    if LC_ALL=C "$@" > "$log_file" 2>&1; then
        return 0
    fi

    # The first run failed. Retry with -maxwarn 1 only for the expected net charge.
    if ! total_charge=$(grompp_net_charge_matches "$log_file" "$expected_charge"); then
        if [[ -n "$total_charge" ]]; then
            echo "Error: $label: grompp reported net charge $total_charge e; expected $expected_charge +/- $net_charge_tolerance_e e: $log_file" >&2
        fi
        return 1
    fi

    if ! LC_ALL=C "$@" -maxwarn 1 > "$log_file" 2>&1; then
        return 1
    fi

    if ! total_charge=$(grompp_net_charge_matches "$log_file" "$expected_charge"); then
        echo "Error: $label: grompp -maxwarn 1 retry did not report only the expected net charge $expected_charge e (reported: ${total_charge:-none}): $log_file" >&2
        return 1
    fi
}
