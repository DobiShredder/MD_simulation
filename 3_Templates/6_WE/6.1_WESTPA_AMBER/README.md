# WESTPA–AMBER weighted ensemble template

## 한국어

AMBER가 각 walker를 unbiased MD로 전파하고 WESTPA가 매 iteration에 walker를
bin으로 나누어 split 또는 merge합니다. Split과 merge는 statistical weight를
보존하므로 일반 MD처럼 frame 수를 population으로 세면 안 됩니다.

기본 설정은 one-dimensional RMSD progress coordinate를 사용하는 steady-state
recycling 계산입니다. `progress_coordinate_mask`, basis state, target state와 bin은
system마다 다시 정의해야 합니다. 기본 Chignolin 값은 script 동작을 보여주기
위한 예시이며 임의의 protein에 그대로 적용하는 값이 아닙니다.

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`로 설치합니다. WESTPA 2 command와 Python `h5py`가
같은 execution environment에 있어야 합니다.

### 필요한 input과 실행

`build.sh`는 사용자가 검토한 protein PDB를 자동 수정하지 않습니다. PDB 1UAO를
예시로 내려받을 수 있지만 NMR model, alternate location, protonation과 missing
atom은 build 전에 직접 처리합니다. `download.sh`는 임시 파일에서 PDB atom
record를 확인한 뒤 최종 파일로 교체합니다.

```bash
./download.sh 1UAO
./build.sh prepared.pdb
./init.sh
./run.sh --dry-run
./run.sh
python3 anal.py
```

### 계산량

| 단계 | 기본 길이 | 실행 횟수 |
| --- | --- | --- |
| Basis state 준비(`build.sh`) | Minimization 5000 cycles, heating 250,000 steps(500 ps), NPT equilibration 500,000 steps(1 ns) | 1회 |
| WE segment | `tau_steps=5000`(10 ps) | 첫 iteration `initial_walkers`(4)개, 이후 occupied bin 수 × `walkers_per_bin`(최대 40개: 기본 bin 11개 중 target bin `[3.0, inf)`은 recycle되어 전파하지 않음) |
| 전체 WE run | 10,000 iterations(1,000 iterations × 10 blocks) | 최대 399,964 segments(4 + 9,999 × 40), MD 합계 최대 약 4.0 μs |

기본 serial 실행은 한 GPU에서 segment를 하나씩 전파합니다.
`WESTPA_WORK_MANAGER=processes`와 `WE_GPU_IDS`를 쓰면 worker 수만큼 segment를
동시에 전파합니다.

### 파일 역할

사용자가 직접 실행하는 파일은 이 directory의 root에 있습니다. `helpers/`는
자동 호출되는 내부 code입니다.

| 파일 | 실행 방식 | 역할 |
| --- | --- | --- |
| `config.toml` | 수정 | force field, MD 길이, progress coordinate, bin과 walker 설정 |
| `download.sh` | 직접 실행 | 예시 PDB 다운로드 |
| `build.sh` | 직접 실행 | topology, RMSD reference, equilibrated basis restart와 WESTPA config 생성 |
| `helpers/configure_we.py` | `build.sh`가 호출 | block config와 AMBER segment input 생성 |
| `helpers/check_we_states.py` | `build.sh`가 호출 | basis progress coordinate가 target bin 밖인지 확인 |
| `init.sh` | 직접 실행 | basis/target state에서 `work/west.h5` 초기화 |
| `run.sh` | 직접 실행 | 선택한 block 또는 남은 block을 이어서 실행 |
| `westpa_scripts/*.sh` | WESTPA가 호출 | segment 전파와 start/end progress coordinate 계산 |
| `anal.py` | 직접 실행 | weight, effective walker, bin occupancy와 target arrival 요약 |

### 주요 output

| 파일 | 내용 |
| --- | --- |
| `work/west.h5` | WESTPA weight, progress coordinate와 iteration state |
| `work/traj_segs/<iteration>/<segment>/` | `seg.rst7`, `seg.nc`, `segment.out` |
| `work/iteration_summary.tsv` | Iteration별 total weight와 effective walker 수 |
| `work/bin_occupancy.tsv`, `work/target_events.tsv` | Bin occupancy와 target arrival |

`anal.py`는 `work/resolved_config.toml`의 bin과 `work/tstate.file`의 target을
읽습니다. `iteration_summary.tsv`의 total weight는 수치 오차 범위에서 보존되어야
합니다. `anal.py`는 합을 1로 강제 보정하지 않고 실제 합을 출력하며, weight가
음수이거나 finite가 아니면 기존 TSV를 바꾸기 전에 중단합니다.
`target_events.tsv`의 event count와 weight만으로 rate를 계산하지 않습니다.

### 결과 확인

`run.sh`는 block마다 `Completed: WE block NNN`을, 모든 block이 끝나면
`WESTPA blocks completed: .../west.h5`를 출력합니다. 이어서 `python3 anal.py`를
실행하고 `iteration_summary.tsv`의 `total_weight`가 1에 가까운지,
`bin_occupancy.tsv`에서 target 쪽 bin까지 weight가 퍼지는지 봅니다.

### 결과 해석

아래는 안내용 절차이며 이 template에서 실행해 검증하지 않았습니다(미검증).
Steady-state recycling에서는 target에 들어간 weight가 basis state로 돌아가므로
전체 probability가 출발 state 쪽 ensemble에 남습니다. 이때 Hill relation에 따라
rate는 target flux를 출발 state population(≈ 1)으로 나눈 값입니다(Zuckerman &
Chong, *Annu. Rev. Biophys.* 46:43, 2017). Flux가 iteration에 따라 plateau에
도달한 구간만 평균합니다.

```bash
export WEST_SIM_ROOT=$PWD WORK_DIR=$PWD/work
w_assign -r work/configs/west.010.cfg -W work/west.h5 \
    --states-from-file states.yaml -o work/assign.h5
w_direct all -r work/configs/west.010.cfg -W work/west.h5 \
    -a work/assign.h5 -o work/direct.h5
```

`states.yaml`에는 출발 state와 target state의 bin에 속하는 progress coordinate
값을 적습니다. 형식은 WESTPA
[`w_assign`](https://westpa.readthedocs.io/en/latest/documentation/cli/w_assign.html)
문서를 따릅니다. `w_direct`의 flux와 rate는 τ당 값이므로 τ(기본 10 ps)로 나누어
시간 단위로 바꿉니다. `--evolution-mode`를 쓰면 `direct.h5`의
`target_flux_evolution`으로 plateau를 확인할 수 있습니다
([`w_direct`](https://westpa.readthedocs.io/en/latest/documentation/cli/w_direct.html)).

### 주요 parameter

Block config의 `max_total_iterations`는 1000, 2000, …, 10000처럼 누적됩니다.

| Key | 기본값 | Unit | 적용 stage | 효과 |
| --- | --- | --- | --- | --- |
| `solute_box_distance` | 14.0 | Å | Build | Solute와 box edge 사이 최소 거리 |
| `salt_concentration` | 150.0 | mM | Build | Neutralization 뒤 추가하는 bulk salt 농도 |
| `temperature` | 300.0 | K | Heating 이후 전체 | `temp0`와 heating 목표 온도 |
| `pressure` | 1.0 | bar | NPT stage | `pres0` |
| `timestep` | 2.0 | fs | 모든 MD | AMBER `dt`(ps로 변환) |
| `minimization_steps`, `minimization_steepest_steps` | 5000, 2500 | cycle | Minimization | `maxcyc`, `ncyc` |
| `heating_initial_temperature` | 20.0 | K | Heating | `tempi`와 `TEMP0` ramp 시작값 |
| `heating_steps`, `equilibration_steps` | 250000, 500000 | step | Heating, equilibration | 500 ps, 1 ns |
| `trajectory_interval_steps` | 5000 | step | Heating, equilibration, segment | `ntwx`. `tau_steps`를 나누어떨어지게 해야 합니다. |
| `energy_interval_steps`, `restart_interval_steps` | 5000, 5000 | step | Heating, equilibration, segment | `ntpr`, `ntwr` |
| `tau_steps` | 5000 | step | Segment | Resampling 간격 τ = 10 ps |
| `total_iterations` | 10000 | iteration | WE run | `run_blocks × iterations_per_block`와 같아야 합니다. |
| `run_blocks`, `iterations_per_block` | 10, 1000 | block, iteration | WE run | Block config 수와 block 길이 |
| `walkers_per_bin` | 4 | walker | Resampling | WESTPA `bin_target_counts` |
| `initial_walkers` | 4 | walker | `init.sh` | `w_init --segs-per-state` |
| `bin_boundaries` | 0.0, 0.5, …, 2.5, 3.0 | Å | Resampling | RMSD bin 경계. 마지막 bin은 `[3.0, inf)` |

Basis-state MD는 tutorial과 같은 whole-system minimization, 20 K부터 시작하는
restrained NVT heating과 NPT equilibration 순서입니다. Heating과 equilibration은
`trajectory_interval_steps`(기본 5000 steps)를 `ntwx`로 사용해 `heat.nc`와
`equilibrate.nc`를 씁니다. 이 값은 `heating_steps`와 `equilibration_steps`보다 클 수
없습니다.

WESTPA segment input도 `trajectory_interval_steps`를 `ntwx`로 사용해
`work/traj_segs/<iteration>/<segment>/seg.nc`를 씁니다. 이 값은 `tau_steps`를
나누어떨어지게 해야 합니다. 기본값에서는 segment마다 마지막 step의 frame 1개가
저장됩니다. Progress coordinate는 `seg.nc`가 아니라 parent restart와 `seg.rst7`에서
계산합니다.

`bstates/bstates.txt`는 basis restart의 label, probability와 filename을 기록합니다.
`tstate.file`의 값은 target bin 안의 representative progress coordinate이고,
WESTPA는 그 값이 속한 bin을 target으로 사용합니다. 따라서 target boundary는
`bin_boundaries`와 함께 설계합니다. Bin은 `[b0, b1)`, …, `[마지막 boundary, inf)`
입니다. `build.sh`는 basis MD 전에 target 값이 첫 boundary 이상인지와 모든 bin이
target이 아닌지 검사합니다. Basis MD 뒤에는 `helpers/check_we_states.py`로 basis
progress coordinate와 그 bin을 출력하고, basis가 target bin 안에 있으면
중단합니다.

| Option | 지원값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택하고 atom mask도 맞춰 갱신합니다. |
| `equilibration_ensemble` | `NPT`로 고정 | `NPT` | Generated equilibration input은 NPT입니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | WESTPA segment input의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | Basis-state MD의 velocity seed를 무작위 또는 고정값으로 설정합니다. |
| `weighted_ensemble.mode` | `steady_state`만 지원 | `steady_state` | Target 도달 walker를 basis state로 recycling합니다. |

`basis_state_file`과 `target_state_file`은 `steady_state` mode에서 모두 필요하며,
`init.sh`가 이를 읽어 `work/west.h5`를 초기화합니다.

### Engine과 worker

`AMBER_ENGINE`이 설정되어 있으면 이를 사용하고, 없으면 build가 기록한
`work/resolved_config.toml`의 `run.engine`을 읽습니다. Build는 source config의 같은
항목을 사용하며 WESTPA propagation도 같은 우선순위를 따릅니다. 허용하는
executable 이름은 `pmemd.cuda`, `pmemd`, `sander`이며 설치 경로를 지정할 수
있습니다. 빈 override, 누락된 engine 설정과 지원하지 않는 executable은 기본값으로
대체하지 않고 중단합니다. 이 설정은 자동 호출되는 `helpers/config_utils.py`가
읽습니다.

기본값은 한 GPU에서 `pmemd.cuda`를 serial로 실행합니다. CPU engine에서는
process work manager를 선택할 수 있습니다.

```bash
AMBER_ENGINE=sander \
WESTPA_WORK_MANAGER=processes \
WESTPA_WORKERS=8 \
./run.sh
```

`pmemd.cuda`를 process work manager로 실행하려면 `WE_GPU_IDS`에 worker마다 GPU
id 하나를 쉼표로 적습니다. 설정하지 않으면 여러 process가 하나의 GPU를 공유하는
실행으로 보고 거부합니다.

```bash
WESTPA_WORK_MANAGER=processes \
WESTPA_WORKERS=4 \
WE_GPU_IDS=0,1,2,3 \
./run.sh
```

WESTPA 2022.15의 process work manager는 각 worker에 0부터 시작하는
`WM_PROCESS_INDEX`를 넘깁니다. `westpa_scripts/runseg.sh`는 이 값으로
`WE_GPU_IDS`의 N번째 id를 골라 `CUDA_VISIBLE_DEVICES`에 넣습니다. 한 worker가 한
GPU를 쓰도록 round-robin 없이 1:1로 배정합니다. 그래서 `WESTPA_WORKERS`는 id 개수
이하여야 하고 id는 중복될 수 없습니다. 남는 id는 쓰지 않습니다. `WE_GPU_IDS`는
`processes`에서만 쓰며, serial 실행의 GPU는 `CUDA_VISIBLE_DEVICES`로 정합니다.
Scheduler가 GPU를 이미 제한했다면 id는 그 안에서 보이는 번호입니다. Fake engine으로
mapping만 확인했고 실제 multi-GPU `w_run`은 미검증입니다.

### Block 이어서 실행

`run.sh`는 완료된 block을 건너뛰며 `--block N`으로 한 block만 선택할 수
있습니다. `init.sh`는 기존 `west.h5`나 segment data를 삭제하지 않습니다.
새 run은 다른 `WORK_DIR`에서 초기화합니다. `west.h5`가 만들어진 뒤에는
`build.sh`가 build를 덮어쓰지 않습니다. 상대 `WORK_DIR`은 `init.sh`와 `run.sh`에서
`WEST_SIM_ROOT` 기준으로 확정하므로 callback이 segment directory로 이동해도 같은
input과 state를 사용합니다.

Kill, node 장애나 scheduler time limit로 block 도중 `w_run`이 끊기면 block
marker가 생기지 않고 `west.h5`에 미완료 segment가 남습니다. 같은 input으로
`./run.sh`를 다시 실행하면 WESTPA가 그 iteration의 미완료 segment만 다시
전파합니다. WESTPA 2022.15 executable propagator는 `runseg.sh`를 호출하기 전에
미완료 segment의 `traj_segs/<iteration>/<segment>/`를 삭제하고 다시 만듭니다.
Partial AMBER output이 진단에 필요하면 재실행 전에 다른 위치로 복사합니다.

`runseg.sh`가 `Segment output from an earlier propagation attempt was kept`로
멈추면 segment directory에 이전 시도의 output이 있습니다. Callback을 `w_run` 밖에서
실행했거나 partial segment를 지우지 않는 WESTPA version을 쓰면 발생합니다. 내용을
확인한 뒤 error에 출력된 `mv` command로 directory를 `<segment>.failed.<timestamp>`로
옮기고 `./run.sh`를 다시 실행합니다. 실제 AMBER/WESTPA run을 중단한 뒤 재개하는
과정은 검증하지 않았습니다.

### 문제 해결

`run.sh`는 block별로 `work/west.<block>.log`(예: `west.001.log`)에 이어 씁니다.

| Error message | 확인할 것 |
| --- | --- |
| `Config error: ...` (`build.sh`) | `trajectory_interval_steps`가 `tau_steps`를 나누는지, `run_blocks × iterations_per_block = total_iterations`인지, bin이 증가하는 숫자인지 봅니다. |
| `the basis progress coordinate ... lies in a target bin` | Basis state가 target 안에 있습니다. `bin_boundaries`나 `tstate.file`을 다시 정하고 새 `WORK_DIR`에서 build합니다. |
| `w_init not found. Activate the WESTPA 2 environment.` | WESTPA를 설치한 environment를 activate합니다. |
| `Existing WESTPA state retained` | 이어서 실행은 `./run.sh`, 새 run은 다른 `WORK_DIR`에서 `init.sh`를 실행합니다. |
| `Multiple process workers cannot share the default pmemd.cuda engine`, `exceeds the number of WE_GPU_IDS entries` | Worker마다 서로 다른 GPU id를 `WE_GPU_IDS`에 적습니다. |
| `AMBER propagation failed with exit status N` | `work/seg_logs/<iteration>-<segment>.log`와 segment directory의 `segment.out` |
| `start progress coordinate failed`, `end progress coordinate failed` | Segment directory의 `pcoord.start.cpptraj.log`, `pcoord.end.cpptraj.log` |
| `WESTPA stopped before block NNN completion` | `work/west.NNN.log` 마지막 부분을 보고 같은 command로 `./run.sh`를 다시 실행합니다. |

실행 상태, 실패 후 재실행, 동시 실행 보호와 log 위치는
[GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

AMBER propagates each walker with unbiased MD, while WESTPA bins, splits and
merges walkers after every iteration. Split and merge operations conserve
statistical weight, so raw frame counts are not populations.

The default is a steady-state recycling calculation with a one-dimensional
RMSD progress coordinate. `progress_coordinate_mask`, the basis and target
states and the bins must be redefined for each system. The Chignolin defaults
only demonstrate the scripts and do not transfer to an arbitrary protein.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt`. WESTPA 2 commands and Python
`h5py` must be available in the same execution environment.

### Required inputs and run

`build.sh` does not modify the reviewed protein PDB. PDB 1UAO can be downloaded
as an example, but resolve NMR models, alternate locations, protonation and
missing atoms before the build. `download.sh` checks the PDB atom records in a
temporary file before replacing the final file.

```bash
./download.sh 1UAO
./build.sh prepared.pdb
./init.sh
./run.sh --dry-run
./run.sh
python3 anal.py
```

### Expected computation

| Stage | Default length | Runs |
| --- | --- | --- |
| Basis-state preparation (`build.sh`) | 5000 minimization cycles, 250,000-step heating (500 ps), 500,000-step NPT equilibration (1 ns) | Once |
| WE segment | `tau_steps=5000` (10 ps) | `initial_walkers` (4) in the first iteration, then occupied bins × `walkers_per_bin` (at most 40: of the 11 default bins, the target bin `[3.0, inf)` is recycled and never propagated) |
| Whole WE run | 10,000 iterations (1,000 iterations × 10 blocks) | At most 399,964 segments (4 + 9,999 × 40), about 4.0 μs of MD in total at most |

The default serial run propagates one segment at a time on one GPU. With
`WESTPA_WORK_MANAGER=processes` and `WE_GPU_IDS`, as many segments as workers
run concurrently.

### File roles

User-facing entry points are in this directory root. `helpers/` contains
internal code called automatically.

| File | How it runs | Role |
| --- | --- | --- |
| `config.toml` | Edit | Force field, MD lengths, progress coordinate, bins and walkers |
| `download.sh` | Run directly | Downloads an example PDB |
| `build.sh` | Run directly | Topology, RMSD reference, equilibrated basis restart and WESTPA configs |
| `helpers/configure_we.py` | Called by `build.sh` | Block configs and AMBER segment input |
| `helpers/check_we_states.py` | Called by `build.sh` | Checks that the basis progress coordinate lies outside the target bin |
| `init.sh` | Run directly | Initializes `work/west.h5` from basis/target states |
| `run.sh` | Run directly | Runs a selected block or continues the remaining blocks |
| `westpa_scripts/*.sh` | Called by WESTPA | Segment propagation and start/end progress coordinates |
| `anal.py` | Run directly | Summarizes weights, effective walkers, bin occupancy and target arrivals |

### Main outputs

| File | Content |
| --- | --- |
| `work/west.h5` | WESTPA weights, progress coordinates and iteration state |
| `work/traj_segs/<iteration>/<segment>/` | `seg.rst7`, `seg.nc`, `segment.out` |
| `work/iteration_summary.tsv` | Total weight and effective walker count per iteration |
| `work/bin_occupancy.tsv`, `work/target_events.tsv` | Bin occupancy and target arrivals |

`anal.py` reads the bins from `work/resolved_config.toml` and the target from
`work/tstate.file`. Total weight in `iteration_summary.tsv` should be conserved
within numerical error. `anal.py` reports the actual sum without renormalizing
it to one, and negative or nonfinite weights stop it before existing TSV files
are replaced. Event counts and weights in `target_events.tsv` alone are not a
rate estimate.

### Success check

`run.sh` prints `Completed: WE block NNN` after each block and
`WESTPA blocks completed: .../west.h5` after the last one. Then run
`python3 anal.py` and check that `total_weight` in `iteration_summary.tsv` stays
close to 1 and that `bin_occupancy.tsv` shows weight spreading toward the target
bins.

### Interpretation

The steps below are guidance and were not run with this template (unverified).
With steady-state recycling, weight entering the target returns to the basis
state, so all probability stays in the ensemble that last left the initial
state. By the Hill relation, the rate is the target flux divided by that
population (≈ 1) (Zuckerman & Chong, *Annu. Rev. Biophys.* 46:43, 2017).
Average only over iterations in which the flux has reached a plateau.

```bash
export WEST_SIM_ROOT=$PWD WORK_DIR=$PWD/work
w_assign -r work/configs/west.010.cfg -W work/west.h5 \
    --states-from-file states.yaml -o work/assign.h5
w_direct all -r work/configs/west.010.cfg -W work/west.h5 \
    -a work/assign.h5 -o work/direct.h5
```

`states.yaml` lists progress-coordinate values inside the initial-state and
target bins, in the format of the WESTPA
[`w_assign`](https://westpa.readthedocs.io/en/latest/documentation/cli/w_assign.html)
documentation. `w_direct` reports fluxes and rates per τ; divide by τ (default
10 ps) to convert to time units. With `--evolution-mode`,
`target_flux_evolution` in `direct.h5` shows whether the flux has plateaued
([`w_direct`](https://westpa.readthedocs.io/en/latest/documentation/cli/w_direct.html)).

### Key parameters

Each block config's `max_total_iterations` is cumulative: 1000, 2000, …, 10000.

| Key | Default | Unit | Stage | Effect |
| --- | --- | --- | --- | --- |
| `solute_box_distance` | 14.0 | Å | Build | Minimum solute–box-edge distance |
| `salt_concentration` | 150.0 | mM | Build | Bulk salt added after neutralization |
| `temperature` | 300.0 | K | Heating onward | `temp0` and the heating target |
| `pressure` | 1.0 | bar | NPT stages | `pres0` |
| `timestep` | 2.0 | fs | All MD | AMBER `dt` (converted to ps) |
| `minimization_steps`, `minimization_steepest_steps` | 5000, 2500 | cycle | Minimization | `maxcyc`, `ncyc` |
| `heating_initial_temperature` | 20.0 | K | Heating | `tempi` and the start of the `TEMP0` ramp |
| `heating_steps`, `equilibration_steps` | 250000, 500000 | step | Heating, equilibration | 500 ps, 1 ns |
| `trajectory_interval_steps` | 5000 | step | Heating, equilibration, segment | `ntwx`; must divide `tau_steps` |
| `energy_interval_steps`, `restart_interval_steps` | 5000, 5000 | step | Heating, equilibration, segment | `ntpr`, `ntwr` |
| `tau_steps` | 5000 | step | Segment | Resampling interval τ = 10 ps |
| `total_iterations` | 10000 | iteration | WE run | Must equal `run_blocks × iterations_per_block` |
| `run_blocks`, `iterations_per_block` | 10, 1000 | block, iteration | WE run | Number and length of block configs |
| `walkers_per_bin` | 4 | walker | Resampling | WESTPA `bin_target_counts` |
| `initial_walkers` | 4 | walker | `init.sh` | `w_init --segs-per-state` |
| `bin_boundaries` | 0.0, 0.5, …, 2.5, 3.0 | Å | Resampling | RMSD bin edges; the last bin is `[3.0, inf)` |

Basis-state MD follows the tutorial: whole-system minimization, restrained NVT
heating from 20 K and NPT equilibration. Heating and equilibration write
`heat.nc` and `equilibrate.nc` with `ntwx` set to `trajectory_interval_steps`
(default 5000 steps). The interval may not exceed `heating_steps` or
`equilibration_steps`.

Segments also use `trajectory_interval_steps` as `ntwx` and write
`work/traj_segs/<iteration>/<segment>/seg.nc`. The interval must divide
`tau_steps`; the defaults store one frame, at the last step, per segment. The
progress coordinate comes from the parent restart and `seg.rst7`, not from
`seg.nc`.

`bstates/bstates.txt` records the label, probability and filename of the basis
restart. A `tstate.file` value is a representative progress coordinate inside
its target bin, and WESTPA uses the bin that contains it as the target. Design
the target together with `bin_boundaries`. Bins are `[b0, b1)`, …,
`[last boundary, inf)`. Before basis MD, `build.sh` checks that every target
value is at or above the first boundary and that at least one bin is not a
target. After basis MD, `helpers/check_we_states.py` prints the basis progress
coordinate and its bin, and stops if the basis lies in a target bin.

| Option | Supported values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt after neutralization and updates atom masks to match. |
| `equilibration_ensemble` | Fixed to `NPT` | `NPT` | Generated equilibration input is NPT. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Sets `ntb` and `ntp` in the WESTPA segment input. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | Sets a random or fixed velocity seed for basis-state MD. |
| `weighted_ensemble.mode` | `steady_state` only | `steady_state` | Recycles walkers reaching the target to the basis state. |

Both `basis_state_file` and `target_state_file` are required in `steady_state`
mode; `init.sh` reads them when initializing `work/west.h5`.

### Engine and workers

`AMBER_ENGINE` overrides `run.engine` in the build-generated
`work/resolved_config.toml`. Build reads the same key from the source config,
and WESTPA propagation follows the same precedence. Accepted executable names
are `pmemd.cuda`, `pmemd` and `sander`; installation paths are accepted. Empty
overrides, missing engine settings and unsupported executables fail instead of
falling back to a default. The automatically called `helpers/config_utils.py`
reads this setting.

The default is serial `pmemd.cuda` on one GPU. A CPU engine may use the
`processes` work manager.

```bash
AMBER_ENGINE=sander \
WESTPA_WORK_MANAGER=processes \
WESTPA_WORKERS=8 \
./run.sh
```

To run `pmemd.cuda` with the `processes` work manager, list one GPU id per
worker in `WE_GPU_IDS`. Without it, the run is treated as several workers
sharing one GPU and is rejected.

```bash
WESTPA_WORK_MANAGER=processes \
WESTPA_WORKERS=4 \
WE_GPU_IDS=0,1,2,3 \
./run.sh
```

The WESTPA 2022.15 processes work manager passes each worker a 0-based
`WM_PROCESS_INDEX`. `westpa_scripts/runseg.sh` uses it to pick the Nth id of
`WE_GPU_IDS` and sets `CUDA_VISIBLE_DEVICES`. Assignment is one GPU per worker,
without round-robin, so `WESTPA_WORKERS` must not exceed the number of ids and
ids must not repeat; extra ids stay unused. `WE_GPU_IDS` applies only to
`processes`; for serial runs choose the GPU with `CUDA_VISIBLE_DEVICES`. If a
scheduler has already restricted the visible GPUs, use the ids visible inside
that allocation. Only the mapping was checked with a fake engine; a real
multi-GPU `w_run` is unverified.

### Continuing blocks

Completed blocks are skipped; `--block N` selects one block. `init.sh` never
deletes an existing `west.h5` or segment data; initialize a new run in a
different `WORK_DIR`. Once `west.h5` exists, `build.sh` refuses to overwrite the
build. `init.sh` and `run.sh` resolve a relative `WORK_DIR` against
`WEST_SIM_ROOT`, so callbacks use the same inputs and state after entering a
segment directory.

If a kill, node failure or scheduler time limit stops `w_run` inside a block, no
block marker is written and `west.h5` keeps the incomplete segments. Re-running
`./run.sh` with the same inputs propagates only those segments again. Before
calling `runseg.sh`, the WESTPA 2022.15 executable propagator removes and
recreates each incomplete `traj_segs/<iteration>/<segment>/` directory. Copy
partial AMBER output elsewhere before the rerun if you need it for diagnosis.

`runseg.sh` stops with `Segment output from an earlier propagation attempt was
kept` when a segment directory already holds output from an earlier attempt.
This happens when the callback runs outside `w_run` or under a WESTPA version
that keeps partial segments. Inspect the files, move the directory to
`<segment>.failed.<timestamp>` with the `mv` command printed in the error, and
rerun `./run.sh`. Interrupting and resuming a real AMBER/WESTPA run has not been
tested.

### Troubleshooting

`run.sh` appends to one log per block, `work/west.<block>.log` (e.g.
`west.001.log`).

| Error message | What to check |
| --- | --- |
| `Config error: ...` (`build.sh`) | `trajectory_interval_steps` divides `tau_steps`, `run_blocks × iterations_per_block = total_iterations`, and bins are increasing numbers. |
| `the basis progress coordinate ... lies in a target bin` | The basis state is inside the target. Redefine `bin_boundaries` or `tstate.file` and build in a new `WORK_DIR`. |
| `w_init not found. Activate the WESTPA 2 environment.` | Activate the environment where WESTPA is installed. |
| `Existing WESTPA state retained` | Continue with `./run.sh`; start a new run with `init.sh` in another `WORK_DIR`. |
| `Multiple process workers cannot share the default pmemd.cuda engine`, `exceeds the number of WE_GPU_IDS entries` | Give each worker its own GPU id in `WE_GPU_IDS`. |
| `AMBER propagation failed with exit status N` | `work/seg_logs/<iteration>-<segment>.log` and `segment.out` in the segment directory |
| `start progress coordinate failed`, `end progress coordinate failed` | `pcoord.start.cpptraj.log` and `pcoord.end.cpptraj.log` in the segment directory |
| `WESTPA stopped before block NNN completion` | Read the end of `work/west.NNN.log`, then rerun the same `./run.sh` command. |

See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state, reruns after failure,
concurrent-run protection and log locations.
