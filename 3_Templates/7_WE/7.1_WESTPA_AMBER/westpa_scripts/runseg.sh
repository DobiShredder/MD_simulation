#!/usr/bin/env bash
set -euo pipefail

original_args=("$@")

show_help() {
    cat <<'EOF'
Usage: ./westpa_scripts/runseg.sh

WESTPA callback that propagates one AMBER segment from its parent restart and
returns the start and end progress coordinates.

Options:
  -h, --help  Show this help message and exit.
EOF
}

if [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
    show_help
    exit 0
fi
if [[ $# -ne 0 ]]; then
    show_help >&2
    exit 2
fi

AMBER_ENGINE=$("${PYTHON:-python3}" "$WEST_SIM_ROOT/helpers/config_utils.py" "$WORK_DIR/resolved_config.toml" engine AMBER_ENGINE pmemd.cuda pmemd sander)

if [[ ${MD_WRITER_PARENT:-} != "$PPID" || ${MD_WRITER_ENTRY:-} != "$0" ]]; then
    exec "${PYTHON:-python3}" "$WEST_SIM_ROOT/helpers/writer_guard.py" --callback-entry \
        --registry "$WORK_DIR" --read "$WORK_DIR/common_files" --read "$WORK_DIR/inputs" --read "$WORK_DIR/progress_coordinate.mask" --read "$WEST_PARENT_DATA_REF" --write "$WEST_CURRENT_SEG_DATA_REF" --write "$WEST_PCOORD_RETURN" -- "$0" "${original_args[@]}"
fi

mkdir -p "$WEST_CURRENT_SEG_DATA_REF"
cd "$WEST_CURRENT_SEG_DATA_REF"

# WESTPA 2022.15 w_run removes and recreates an incomplete segment directory
# before calling this script. Leftover output therefore means a standalone
# callback or a WESTPA version that keeps partial segments; keep it for review.
for output in segment.in segment.out segment.info seg.rst7 seg.nc pcoord.start.cpptraj.log pcoord.end.cpptraj.log; do
    if [[ -e "$output" ]]; then
        echo "Error: Segment output from an earlier propagation attempt was kept: $WEST_CURRENT_SEG_DATA_REF/$output" >&2
        echo "Inspect the partial segment, move its directory aside, and rerun ./run.sh:" >&2
        printf '  mv %q %q.failed.<timestamp>\n' "$WEST_CURRENT_SEG_DATA_REF" "$WEST_CURRENT_SEG_DATA_REF" >&2
        exit 1
    fi
done
if [[ -s "$WEST_PCOORD_RETURN" ]]; then
    echo "Error: Progress-coordinate return file is not empty and was kept: $WEST_PCOORD_RETURN" >&2
    exit 1
fi

case "$WEST_CURRENT_SEG_INITPOINT_TYPE" in
    SEG_INITPOINT_NEWTRAJ)
        parent_restart=$WEST_PARENT_DATA_REF
        ;;
    SEG_INITPOINT_CONTINUES)
        parent_restart=$WEST_PARENT_DATA_REF/seg.rst7
        ;;
    *)
        echo "Error: unknown initial-point type: $WEST_CURRENT_SEG_INITPOINT_TYPE" >&2
        exit 2
        ;;
esac

if [[ ! -s "$parent_restart" ]]; then
    echo "Error: parent restart not found: $parent_restart" >&2
    exit 1
fi

seed=$((WEST_RAND32 % 2147483646 + 1))
sed "s/WEST_SEED/$seed/g" "$WORK_DIR/inputs/segment.in.template" \
    > segment.in

if ! start_pcoord=$("$WEST_SIM_ROOT/westpa_scripts/calc_pcoord.sh" "$parent_restart" pcoord.start.cpptraj.log); then
    echo "Error: start progress coordinate failed for $parent_restart; cpptraj log: $WEST_CURRENT_SEG_DATA_REF/pcoord.start.cpptraj.log" >&2
    exit 1
fi

# Optional per-worker GPU. WESTPA's processes work manager exports the 0-based
# worker index as WM_PROCESS_INDEX; run.sh has checked the WE_GPU_IDS list.
if [[ -n "${WE_GPU_IDS:-}" ]]; then
    if [[ ! "${WM_PROCESS_INDEX:-}" =~ ^[0-9]+$ ]]; then
        echo "Error: WE_GPU_IDS is set but WM_PROCESS_INDEX is not; use the WESTPA processes work manager." >&2
        exit 1
    fi
    IFS=, read -r -a gpu_id_list <<< "$WE_GPU_IDS"
    if (( WM_PROCESS_INDEX >= ${#gpu_id_list[@]} )); then
        echo "Error: WESTPA worker $WM_PROCESS_INDEX has no entry in WE_GPU_IDS=$WE_GPU_IDS" >&2
        exit 1
    fi
    export CUDA_VISIBLE_DEVICES=${gpu_id_list[$WM_PROCESS_INDEX]}
fi

engine_status=0
"$AMBER_ENGINE" \
    -O \
    -i segment.in \
    -o segment.out \
    -p "$WORK_DIR/common_files/system.parm7" \
    -c "$parent_restart" \
    -r seg.rst7 \
    -x seg.nc \
    -inf segment.info || engine_status=$?
if (( engine_status != 0 )); then
    if [[ -s segment.out ]]; then
        echo "Last 20 lines of $WEST_CURRENT_SEG_DATA_REF/segment.out:" >&2
        tail -n 20 segment.out >&2
    fi
    echo "Error: AMBER propagation failed with exit status $engine_status: $WEST_CURRENT_SEG_DATA_REF/segment.out" >&2
    exit 1
fi
for output in seg.rst7 seg.nc segment.out segment.info; do
    if [[ ! -s "$output" ]]; then
        echo "Error: Segment output is incomplete: $WEST_CURRENT_SEG_DATA_REF/$output" >&2
        exit 1
    fi
done
if ! end_pcoord=$("$WEST_SIM_ROOT/westpa_scripts/calc_pcoord.sh" seg.rst7 pcoord.end.cpptraj.log); then
    echo "Error: end progress coordinate failed for $WEST_CURRENT_SEG_DATA_REF/seg.rst7; cpptraj log: $WEST_CURRENT_SEG_DATA_REF/pcoord.end.cpptraj.log" >&2
    exit 1
fi
printf '%s\n%s\n' "$start_pcoord" "$end_pcoord" > "$WEST_PCOORD_RETURN"
