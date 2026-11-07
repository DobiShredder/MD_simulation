# Umbrella windows

## 한국어

`build.sh`는 rMD seed, 공통 topology와 restraint를 `work/001`, `work/002`, ...에
배치하고, `run.sh`가 각 window를 실행합니다.

```bash
./build.sh
./run.sh
```

Window는 leaf `../config.toml`(`--config FILE`로 변경)의 `umbrella.centers`(distance center, Å)와
`umbrella.force_constants`(AMBER restraint force constant, kcal mol⁻¹ Å⁻²)에서
같은 위치의 값으로 만듭니다. 기본 force constant 1.0은 1 Å 간격에서 300 K window 폭
약 0.55 Å로 인접 histogram이 겹치게 합니다.

기본값에서 각 window의 `production.nc`는 2,000 frame(10 ps 간격), `distance.dat`는
1 ps 간격으로 약 20,000 row입니다. 선택한 window가 모두 끝나면 `run.sh` 마지막 줄에
`Completed umbrella-window runs: N run, M already completed (work)`가 출력됩니다.

`run.sh`는 `--window N`, `--windows START-END`, `--preparation-only`,
`--production-only`, `--dry-run`을 지원합니다. `build.sh`와 `run.sh`는
`WORK_DIR`(기본 `work`)을 같은 window root로 사용합니다. Heating input은
heavy-atom positional restraint(`ntr=1`)와 함께 AMBER manual 권장에 따라
`&ewald netfrc=0`을 씁니다.

실행 상태와 partial output 처리는 [GUIDE.md 부록](../../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

`build.sh` combines each rMD seed with the shared topology and a generated
restraint under `work/001`, `work/002`, ..., and `run.sh` runs the windows.

```bash
./build.sh
./run.sh
```

Each window takes the values at the same position in `umbrella.centers`
(distance center, Å) and `umbrella.force_constants` (AMBER restraint force
constant, kcal mol⁻¹ Å⁻²) in the leaf `../config.toml` (change with `--config FILE`). The default
force constant 1.0 gives about 0.55 Å wide 300 K windows at 1 Å spacing, so
neighboring histograms overlap.

By default, each window's `production.nc` has 2,000 frames (every 10 ps) and
`distance.dat` has about 20,000 rows (every 1 ps). When the selected windows
finish, `run.sh` ends with
`Completed umbrella-window runs: N run, M already completed (work)`.

`run.sh` supports `--window N`, `--windows START-END`, `--preparation-only`,
`--production-only`, and `--dry-run`. Both scripts use `WORK_DIR` (default
`work`) as the window root. The heating input uses heavy-atom positional
restraints (`ntr=1`) and sets `&ewald netfrc=0`, as the AMBER manual recommends.

See [GUIDE.md appendix](../../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state and partial-output
handling.
