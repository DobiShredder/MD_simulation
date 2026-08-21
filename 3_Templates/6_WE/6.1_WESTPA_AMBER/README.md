# WESTPA–AMBER weighted ensemble template

## 한국어

AMBER가 각 walker를 unbiased MD로 전파하고 WESTPA가 매 iteration에 walker를
bin으로 나누어 split 또는 merge합니다. Split과 merge는 statistical weight를
보존하므로 일반 MD처럼 frame 수를 population으로 세면 안 됩니다.

기본 설정은 one-dimensional RMSD progress coordinate를 사용하는 steady-state
recycling 계산입니다. `progress_coordinate_mask`, basis state, target state와 bin은
system마다 다시 정의해야 합니다. 기본 Chignolin 값은 script 동작을 보여주기
위한 예시이며 임의의 protein에 그대로 적용하는 값이 아닙니다.

### 필요한 input과 실행

`build.sh`는 사용자가 검토한 protein PDB를 자동 수정하지 않습니다. PDB 1UAO를
예시로 내려받을 수 있지만 NMR model, alternate location, protonation과 missing
atom은 build 전에 직접 처리합니다.

```bash
./download.sh 1UAO
./build.sh prepared.pdb
./init.sh
./run.sh --dry-run
./run.sh
python3 anal.py
```

WESTPA 2 command와 Python `h5py`가 같은 execution environment에 있어야 합니다.

| 파일 | 실행 방식 | 역할 |
| --- | --- | --- |
| `config.toml` | 수정 | force field, MD 길이, progress coordinate, bin과 walker 설정 |
| `build.sh` | 직접 실행 | topology, RMSD reference, equilibrated basis restart와 WESTPA config 생성 |
| `configure_we.py` | `build.sh`가 호출 | block config와 AMBER segment input 생성 |
| `init.sh` | 직접 실행 | basis/target state에서 `work/west.h5` 초기화 |
| `run.sh` | 직접 실행 | 선택한 block 또는 남은 block을 이어서 실행 |
| `westpa_scripts/*.sh` | WESTPA가 호출 | segment 전파와 start/end progress coordinate 계산 |
| `anal.py` | 직접 실행 | weight, effective walker, bin occupancy와 target arrival 요약 |

`config.toml`의 기본 `tau_steps=5000`은 2 fs timestep에서 iteration당 10 ps입니다.
총 10,000 iterations를 1,000 iterations씩 10 blocks로 실행합니다. 각 block
config의 `max_total_iterations`는 1000, 2000, …, 10000처럼 누적됩니다.
`walkers_per_bin=4`는 occupied bin의 목표 walker 수이고 `initial_walkers=4`는
basis state에서 시작하는 walker 수입니다.

`bstates/bstates.txt`는 basis restart의 label, probability와 filename을 기록합니다.
`tstate.file`의 값은 target bin 안의 representative progress coordinate입니다.
WESTPA는 그 값이 속한 bin을 target으로 사용합니다. 따라서 target boundary는
`bin_boundaries`와 함께 설계해야 합니다.

### Restart와 resource

`build.sh`는 topology와 각 basis-state MD stage가 정상 종료되면 marker를
생성합니다. 실패한 minimization, heating 또는 equilibration은 다음 호출에서 그
stage부터 다시 실행합니다. `west.h5`가 만들어진 뒤에는 build를 덮어쓰지
않습니다.
Basis-state MD는 tutorial과 같은 whole-system minimization, 20 K부터 시작하는
restrained NVT heating과 NPT equilibration 순서입니다.

`run.sh`는 완료된 block을 건너뛰며 `--block N`으로 한 block만 선택할 수
있습니다. `init.sh --reset`은 기존 `west.h5`, segment와 iteration state를 지우고
새 run을 시작할 때만 사용합니다.

기본값은 한 GPU에서 `pmemd.cuda`를 serial로 실행합니다. CPU engine에서는
process work manager를 선택할 수 있습니다.

```bash
AMBER_ENGINE=sander \
WESTPA_WORK_MANAGER=processes \
WESTPA_WORKERS=8 \
./run.sh
```

여러 process가 하나의 기본 `pmemd.cuda`를 동시에 공유하는 실행은 거부합니다.
GPU 병렬 실행은 GPU별 worker 배치와 scheduler isolation을 외부 환경에서
구성해야 합니다.

`anal.py`는 `work/resolved_config.toml`의 bin과 `work/tstate.file`의 target을
읽습니다. `iteration_summary.tsv`의 total weight는 수치 오차 범위에서 보존되어야
합니다. `target_events.tsv`의 event count와 weight만으로 rate를 계산하지 않습니다.

## English

AMBER propagates each walker with unbiased MD, while WESTPA bins, splits, and
merges walkers after every iteration. Split and merge operations conserve
statistical weight, so raw frame counts are not populations.

The default is a steady-state recycling calculation with a one-dimensional
RMSD progress coordinate. The progress-coordinate mask, basis and target
states, and bin boundaries are system-specific inputs. The Chignolin defaults
only demonstrate the interface.

Run `build.sh` with a reviewed PDB, initialize `west.h5` with `init.sh`, and use
`run.sh` to continue unfinished blocks. At 2 fs, `tau_steps=5000` gives 10 ps per
iteration. The default 10,000 iterations are divided into ten cumulative
1,000-iteration block configs. The default target count is four walkers per
occupied bin, with four initial walkers at the basis state.
WESTPA 2 commands and Python `h5py` must be available in the execution
environment.

The basis-state file maps a label and probability to the generated basis
restart. A target-state value is a representative point inside its target bin;
the matching boundary comes from `bin_boundaries`. Design both together.

Successful topology and basis-state stages receive completion markers.
Interrupted minimization, heating, or equilibration is rerun from that stage.
Basis-state MD follows whole-system minimization, restrained NVT heating from
20 K, and NPT equilibration.
Once `west.h5` exists, `build.sh` refuses to overwrite production state.
Completed WESTPA blocks are skipped; `--block N` selects one block, and
`init.sh --reset` explicitly discards an initialized run.

The default is serial `pmemd.cuda` on one GPU. A CPU engine may use the
`processes` work manager and multiple workers. GPU worker placement remains an
external scheduler decision. Analysis reads the resolved bins and target file,
then reports total weight, effective walker count, bin occupancy, and target
arrivals. Target counts alone are not a rate estimate.
