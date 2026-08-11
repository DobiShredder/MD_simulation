#!/usr/bin/env bash
set -euo pipefail

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi
if [[ $# -ne 1 ]]; then
    echo "사용법: $0 [--dry-run] CHIGNOLIN.pdb" >&2
    exit 2
fi

die() {
    echo "오류: $*" >&2
    exit 1
}

source ./env.sh
input_pdb=$1
tleap=${TLEAP:-tleap}
build_dir="$WORK_DIR/common_files"
basis_dir="$WORK_DIR/bstates"

if (( dry_run )); then
    echo "Build: Chignolin ff19SB/TIP3P basis state"
    printf '%q -f %q\n' "$tleap" "$WEST_SIM_ROOT/inputs/leap.in"
    printf '%q -O -i %q -p %q -c %q -r %q\n' "$AMBER_ENGINE" "$WEST_SIM_ROOT/inputs/minimize.in" "$build_dir/system.parm7" "$build_dir/system.rst7" "$build_dir/minimize.rst7"
    exit 0
fi

if [[ ! -s "$input_pdb" ]]; then
    die "Chignolin PDB를 찾을 수 없습니다: $input_pdb"
fi
for executable in "$tleap" "$AMBER_ENGINE" "$CPPTRAJ"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "실행 파일을 찾을 수 없습니다: $executable"
    fi
done

mkdir -p "$build_dir" "$basis_dir"
cp "$input_pdb" "$build_dir/input.pdb"
cp "$WEST_SIM_ROOT/inputs/leap.in" "$build_dir/leap.in"

echo "Chignolin topology와 basis state를 생성합니다."
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

cp "$build_dir/minimize.rst7" "$build_dir/reference.rst7"

if ! "$AMBER_ENGINE" \
    -O \
    -i "$WEST_SIM_ROOT/inputs/heat.in" \
    -o "$build_dir/heat.out" \
    -p "$build_dir/system.parm7" \
    -c "$build_dir/minimize.rst7" \
    -r "$build_dir/heat.rst7" \
    -ref "$build_dir/minimize.rst7" \
    -inf "$build_dir/heat.info"; then
    die "Basis-state heating에 실패했습니다: $build_dir/heat.out"
fi

if ! "$AMBER_ENGINE" \
    -O \
    -i "$WEST_SIM_ROOT/inputs/equilibrate.in" \
    -o "$build_dir/equilibrate.out" \
    -p "$build_dir/system.parm7" \
    -c "$build_dir/heat.rst7" \
    -r "$basis_dir/basis.rst7" \
    -x "$build_dir/equilibrate.nc" \
    -inf "$build_dir/equilibrate.info"; then
    die "Basis-state equilibration에 실패했습니다: $build_dir/equilibrate.out"
fi

for output in \
    "$build_dir/system.parm7" \
    "$build_dir/reference.rst7" \
    "$basis_dir/basis.rst7"; do
    if [[ ! -s "$output" ]]; then
        die "Basis-state output이 생성되지 않았습니다: $output"
    fi
done
echo "WESTPA basis state: $basis_dir/basis.rst7"
