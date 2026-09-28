#!/usr/bin/env bash

# Accept only the small residual charge warning caused by topology conversion.
grompp_has_only_charge_roundoff_warning() {
    local log_file=$1
    local warning_count
    local total_charge

    warning_count=$(awk '/^WARNING [0-9]+ \[/ {count++} END {print count + 0}' "$log_file")
    if [[ "$warning_count" -ne 1 ]]; then
        return 1
    fi

    total_charge=$(awk '/System has non-zero total charge:/ {print $NF; exit}' "$log_file")
    if [[ ! "$total_charge" =~ ^[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?$ ]]; then
        return 1
    fi

    awk -v charge="$total_charge" \
        'BEGIN {exit !(charge >= -0.01 && charge <= 0.01)}'
}

run_grompp() {
    local log_file=$1
    shift

    if LC_ALL=C "$@" > "$log_file" 2>&1; then
        return 0
    fi

    if ! grompp_has_only_charge_roundoff_warning "$log_file"; then
        return 1
    fi

    echo "Warning: retrying grompp for one charge-rounding warning: $log_file" >&2
    if ! LC_ALL=C "$@" -maxwarn 1 > "$log_file" 2>&1; then
        return 1
    fi

    grompp_has_only_charge_roundoff_warning "$log_file"
}
