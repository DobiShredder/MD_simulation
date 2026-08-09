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

die() {
    echo "오류: $*" >&2
    exit 1
}

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/env.sh"
tleap=${TLEAP:-tleap}
build_dir="$WORK_DIR/common_files"
structure_file="$WORK_DIR/structure/system.mol2"
basis_dir="$WORK_DIR/bstates"

if (( dry_run )); then
    echo "Build: Na+/Cl- implicit-solvent basis state"
    printf '%q -f %q\n' "$tleap" "$WEST_SIM_ROOT/inputs/leap.in"
    printf '%q -O -i %q -p %q -c %q -r %q\n' "$AMBER_ENGINE" "$WEST_SIM_ROOT/inputs/minimize.in" "$build_dir/system.parm7" "$build_dir/system.rst7" "$build_dir/minimize.rst7"
    exit 0
fi

if [[ ! -s "$structure_file" ]]; then
    die "prepare.py를 먼저 실행해야 합니다: $structure_file"
fi
for executable in "$tleap" "$AMBER_ENGINE" "$CPPTRAJ"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "실행 파일을 찾을 수 없습니다: $executable"
    fi
done

mkdir -p "$build_dir" "$basis_dir"
cp "$structure_file" "$build_dir/system.mol2"
cp "$WEST_SIM_ROOT/inputs/leap.in" "$build_dir/leap.in"

echo "Na+/Cl- topology와 basis state를 생성합니다."
if ! (cd "$build_dir" && "$tleap" -f leap.in > leap.log 2>&1); then
    die "tleap 실행에 실패했습니다: $build_dir/leap.log"
fi

if ! "$AMBER_ENGINE" \
    -O \
    -i "$WEST_SIM_ROOT/inputs/minimize.in" \
    -o "$build_dir/minimize.out" \
    -p "$build_dir/system.parm7" \
    -c "$build_dir/system.rst7" \
    -r "$build_dir/minimize.rst7" \
    -inf "$build_dir/minimize.info"; then
    die "Basis-state minimization에 실패했습니다: $build_dir/minimize.out"
fi

if ! "$AMBER_ENGINE" \
    -O \
    -i "$WEST_SIM_ROOT/inputs/equilibrate.in" \
    -o "$build_dir/equilibrate.out" \
    -p "$build_dir/system.parm7" \
    -c "$build_dir/minimize.rst7" \
    -r "$basis_dir/basis.rst7" \
    -x "$build_dir/equilibrate.nc" \
    -inf "$build_dir/equilibrate.info"; then
    die "Basis-state equilibration에 실패했습니다: $build_dir/equilibrate.out"
fi

if [[ ! -s "$basis_dir/basis.rst7" ]]; then
    die "Basis restart가 생성되지 않았습니다: $basis_dir/basis.rst7"
fi
echo "WESTPA basis state: $basis_dir/basis.rst7"
