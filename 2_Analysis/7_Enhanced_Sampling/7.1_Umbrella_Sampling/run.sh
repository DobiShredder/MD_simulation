#!/usr/bin/env bash
set -euo pipefail

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi

if [[ $# -ne 0 ]]; then
    echo "사용법: $0 [--dry-run]" >&2
    exit 2
fi

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
python=${PYTHON:-python3}
wham=${WHAM_BIN:-wham}
windows=${WINDOW_DIR:-"$script_dir/../../../1_Simulation/2_US/us/work/windows"}
output=${OUTPUT_DIR:-"$script_dir/output"}
distance_column=${DISTANCE_COLUMN:-8}
discard_ps=${DISCARD_PS:-1000}
minimum=${PMF_MIN_A:-5.0}
maximum=${PMF_MAX_A:-25.0}
bins=${PMF_BINS:-100}
tolerance=${WHAM_TOLERANCE:-1e-8}
temperature=${TEMPERATURE_K:-300}
bootstrap=${BOOTSTRAP_TRIALS:-0}
bootstrap_seed=${BOOTSTRAP_SEED:-20260807}

die() {
    echo "오류: $*" >&2
    exit 1
}

run_command() {
    if (( dry_run )); then
        printf '+'
        printf ' %q' "$@"
        printf '\n'
    elif ! "$@"; then
        return 1
    fi
}

if (( ! dry_run )); then
    command -v "$python" >/dev/null 2>&1 || die "Python을 찾을 수 없습니다: $python"
    command -v "$wham" >/dev/null 2>&1 || die "WHAM executable을 찾을 수 없습니다: $wham"
    [[ -d "$windows" ]] || die "umbrella window output을 찾을 수 없습니다: $windows"
fi

run_command "$python" "$script_dir/prepare.py" --windows "$windows" --output "$output" \
    --distance-column "$distance_column" --discard-ps "$discard_ps" \
    || die "WHAM input 준비에 실패했습니다."

wham_command=("$wham" "$minimum" "$maximum" "$bins" "$tolerance" "$temperature" 0 \
    "$output/metadata.dat" "$output/pmf.dat")
if (( bootstrap > 0 )); then
    wham_command+=("$bootstrap" "$bootstrap_seed")
fi
run_command "${wham_command[@]}" || die "WHAM 계산에 실패했습니다. executable의 CLI를 확인하십시오."

run_command "$python" "$script_dir/overlap.py" --summary "$output/summary.tsv" \
    --series "$output/series" --output "$output/overlap.tsv" \
    || die "histogram overlap 계산에 실패했습니다."

if (( ! dry_run )); then
    echo "PMF와 overlap 결과: $output"
fi
