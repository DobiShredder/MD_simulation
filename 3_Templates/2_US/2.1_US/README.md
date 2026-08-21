# Umbrella sampling template

## 한국어

사용자가 정의한 두 atom 사이 거리를 reaction coordinate로 사용합니다.
`windows.tsv`에는 증가하는 center를 Å 단위로 한 줄에 하나씩 적고,
`config.toml`에는 두 AMBER mask와 공통 force constant를 지정합니다.

```bash
./build.sh prepared.pdb
python3 prepare_windows.py directed.nc
./run.sh --dry-run
./run.sh
```

`prepare_windows.py`는 directed trajectory에서 각 center를 처음 통과하는 순서로
frame을 고르고, center와의 차이가 0.75 Å 이하인지 검사합니다. 각 mask는 정확히
한 atom을 선택해야 합니다. 생성된 window는 `work/windows/001`, `002`, ...에
저장됩니다.

`download.sh PDB_ID`는 선택한 source PDB를 수정하지 않고 내려받습니다.
`build.sh`는 공통 topology를 만들고, `run.sh`는 생성된
window 전체 또는 `--window N`으로 고른 하나를 실행합니다.

`run.sh --window 3`은 세 번째 window만 실행합니다. Minimization, heating과
equilibration의 partial output은 다시 계산하지만 partial production은 보존하고
중단합니다. Window production은 tutorial과 같은 단일 run 구조이므로
`production_segments=1`만 지원합니다.

## English

The reaction coordinate is the distance between two explicitly configured
AMBER atom masks. List increasing centers, one per line in `windows.tsv`.
After building the common topology, `prepare_windows.py` selects ordered first
crossings from a directed trajectory and creates `work/windows/001`, `002`,
and so on. `download.sh` retrieves an unmodified source PDB, `build.sh` creates
the common system, and `run.sh` propagates all windows
or one selected with `--window N`. Partial production is never overwritten
automatically. Window production follows the tutorial's single-run layout and
therefore requires `production_segments=1`.
