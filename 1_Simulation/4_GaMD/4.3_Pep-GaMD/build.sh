#!/usr/bin/env bash
set -euo pipefail

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi
if [[ $# -ne 1 ]]; then
    echo "사용법: $0 [--dry-run] SH3-PEPTIDE.pdb" >&2
    exit 2
fi

die() {
    echo "오류: $*" >&2
    exit 1
}

input_pdb=$1
metadata=$(dirname "$input_pdb")/system_metadata.tsv
tleap=${TLEAP:-tleap}
python=${PYTHON:-python3}
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
work_dir=${WORK_DIR:-"$script_dir/work"}

if (( dry_run )); then
    printf 'mkdir -p %q\n' "$work_dir"
    printf 'cp %q %q\n' "$input_pdb" "$work_dir/input.pdb"
    printf '%q -f %q\n' "$tleap" "$script_dir/inputs/tleap.in"
    printf '%q %q %q %q %q\n' "$python" "$script_dir/render_inputs.py" "$metadata" "$script_dir/inputs" "$work_dir/inputs"
    exit 0
fi

for input in "$input_pdb" "$metadata"; do
    if [[ ! -s "$input" ]]; then
        die "build input을 찾을 수 없습니다: $input"
    fi
done
for executable in "$tleap" "$python"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "실행 파일을 찾을 수 없습니다: $executable"
    fi
done

mkdir -p "$work_dir"
cp "$input_pdb" "$work_dir/input.pdb"
cp "$metadata" "$work_dir/system_metadata.tsv"

echo "ff19SB/TIP3P SH3–peptide topology를 생성합니다."
if ! (
    cd "$work_dir"
    "$tleap" -f "$script_dir/inputs/tleap.in" > leap.log 2>&1
); then
    die "tleap 실행에 실패했습니다: $work_dir/leap.log"
fi
for output in system.parm7 system.rst7 system.pdb; do
    if [[ ! -s "$work_dir/$output" ]]; then
        die "build output이 생성되지 않았습니다: $work_dir/$output"
    fi
done
if ! "$python" "$script_dir/render_inputs.py" "$metadata" "$script_dir/inputs" "$work_dir/inputs"; then
    die "Pep-GaMD input 생성에 실패했습니다."
fi

echo "Pep-GaMD topology, restart와 generated input: $work_dir"
