#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 {chignolin|ligamd3|pepgamd} SIMULATION_WORK_DIR" >&2
    exit 2
fi

die() {
    echo "Error: $*" >&2
    exit 1
}

profile=$1
simulation_work=$2
cpptraj=${CPPTRAJ:-cpptraj}
python=${PYTHON:-python3}
output_dir=${OUTPUT_DIR:-"output/$profile"}

case "$profile" in
    chignolin | ligamd3 | pepgamd)
        components=2
        ;;
    *)
        die "Unsupported profile: $profile"
        ;;
esac

for executable in "$cpptraj" "$python"; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        die "Executable not found: $executable"
    fi
done
if ! "$python" -c 'import numpy' >/dev/null 2>&1; then
    die "Cannot import NumPy."
fi

mkdir -p "$output_dir"

if ! "$python" \
    prepare.py \
    "$profile" \
    "$simulation_work" \
    "$output_dir/cpptraj.in"; then
    die "cpptraj input generation failed: $simulation_work -> $output_dir/cpptraj.in"
fi

if [[ ! -s "$output_dir/cpptraj.in" ]]; then
    die "cpptraj input was not created: $output_dir/cpptraj.in"
fi

echo "Calculating $profile CV; log: $output_dir/cpptraj.log"
if ! "$cpptraj" \
    -i "$output_dir/cpptraj.in" \
    > "$output_dir/cpptraj.log" 2>&1; then
    die "cpptraj CV Calculation failed: $output_dir/cpptraj.log"
fi
if [[ ! -s "$output_dir/cv.dat" ]]; then
    die "CV Output was not created: $output_dir/cv.dat"
fi

echo "Completed: CV calculation ($output_dir/cv.dat)"
printf '\n'
echo "Reweighting $profile: $output_dir/cv.dat; GaMD logs: $simulation_work"
if ! "$python" \
    reweight.py \
    --cv "$output_dir/cv.dat" \
    --log-directory "$simulation_work" \
    --components "$components" \
    --temperature 300 \
    --bin-width 0.25 \
    --output "$output_dir/pmf.tsv"; then
    die "GaMD reweighting failed: $output_dir/cv.dat; GaMD logs: $simulation_work"
fi

if [[ ! -s "$output_dir/pmf.tsv" ]]; then
    die "GaMD reweighting output was not created: $output_dir/pmf.tsv"
fi

echo "GaMD reweighting results: $output_dir"
