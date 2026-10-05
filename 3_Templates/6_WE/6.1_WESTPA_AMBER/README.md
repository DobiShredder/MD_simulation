# WESTPA–AMBER weighted ensemble template

## 한국어

Basis-state heating과 equilibration은 `ntwx=0`이므로 `.nc`를 생성하지 않습니다. 완료와 재사용에는 stage별 `.out`, `.info`와 restart file이 필요하며, restart는 heating의 `heat.rst7`과 equilibration의 `bstates/basis.rst7`입니다. Minimization diagnostic은 `minimize.info`에 저장합니다. 완료된 stage의 필수 output이 없거나 비어 있으면 기존 파일을 보존하고 중단합니다.

사용자가 직접 실행하는 파일은 이 directory의 root에 있습니다. `helpers/`는 `build.sh`, `run.sh` 또는 `anal.py`가 자동 호출하는 leaf-local 내부 code이며 직접 실행하지 않습니다.

중단되거나 marker가 없는 stage output은 자동 삭제하거나 재실행하지 않고 보존한 채 중단합니다.

Water count를 위한 first-pass LEaP input과 `solvated.pdb`는 `work/.build_tmp.XXXXXX/`에서 생성합니다. 전체 build가 성공하면 temporary directory를 삭제하고, 실패하면 진단을 위해 경로를 출력하고 보존합니다. Final PDB, topology, restart, resolved config와 LEaP log는 유지합니다.

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

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
| `helpers/configure_we.py` | `build.sh`가 호출 | block config와 AMBER segment input 생성 |
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
생성합니다. 중단된 minimization, heating 또는 equilibration output은 삭제하지 않고
build를 중단합니다. 기존 output을 별도로 보관하거나 새 `WORK_DIR`을 지정한
뒤 다시 시작합니다. `west.h5`가 만들어진 뒤에는 build를 덮어쓰지 않습니다.
Basis-state MD는 tutorial과 같은 whole-system minimization, 20 K부터 시작하는
restrained NVT heating과 NPT equilibration 순서입니다.

`run.sh`는 완료된 block을 건너뛰며 `--block N`으로 한 block만 선택할 수
있습니다. `init.sh`는 기존 `west.h5`나 segment data를 삭제하지 않습니다.
새 run은 다른 `WORK_DIR`에서 초기화합니다.

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

### Config 선택값

| Option | 현재 지원값 | 기본값 | 적용 방식 |
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

`mode`에는 현재 다른 선택지가 없습니다. `basis_state_file`과
`target_state_file`은 `steady_state` mode에서 모두 필요하며, `init.sh`가 이를
읽어 `work/west.h5`를 초기화합니다.

### Engine 선택과 실행 상태

`AMBER_ENGINE`이 설정되어 있으면 이를 사용하며, 없으면 build가 기록한 `work/resolved_config.toml`의 `run.engine`을 읽습니다. 허용하는 executable 이름은 `pmemd.cuda`, `pmemd`, `sander`이며 설치 경로를 지정할 수 있습니다. Build는 source config의 같은 항목을 사용합니다. WESTPA propagation도 동일한 override 우선순위를 따릅니다. CPU process worker 사용 조건은 그대로 유지합니다. 빈 override, 누락된 engine 설정과 지원하지 않는 executable은 기본값으로 대체하지 않고 error로 중단합니다. Runner가 `helpers/config_utils.py`를 자동 호출해 이 설정을 읽습니다.

같은 input과 config로 완료 topology를 재사용할 때는 새 임시 directory를 만들지
않으므로 삭제도 하지 않습니다. 새 build가 성공하면 이번 실행에서 만든
`.build_tmp.*`를 정리하고, 실패하면 진단 파일과 해당 directory를 보존합니다.

다운로드는 임시 파일의 PDB atom record를 확인한 뒤 최종 파일로 교체합니다. 실패하면 기존 PDB를 보존하고 임시 파일을 정리합니다.

상대 `WORK_DIR`은 `init.sh`와 `run.sh`에서 `WEST_SIM_ROOT` 기준으로 확정합니다. Callback이 segment directory로 이동해도 같은 input과 state를 사용합니다.

### 동시 실행과 input 변경

로컬 WESTPA callback은 검증된 manager 보호를 이어받습니다. 단독 callback은 segment와 progress-coordinate output의 독립 scope를 획득합니다. Callback script도 init/run의 input identity에 포함됩니다.

Build/init/run wrapper는 같은 work tree의 topology/basis, HDF5와 block marker를 보호합니다. 서로 다른 `WORK_DIR`은 독립 실행을 허용합니다. Weight와 resampling은 WESTPA manager가 관리하며 HDF5는 불변 input으로 hash하지 않습니다.
자동 호출되는 `helpers/writer_guard.py`가 scope 등록과 자식 process 종료를 관리하고,
`helpers/input_identity.py`가 작은 계산 input의 SHA256을 비교합니다.
`--help`와 `--dry-run`은 lock과 identity를 만들지 않습니다.

첫 stage 실행 전에 사용한 input을 `.*.identity.json`에 기록합니다. 같은 input의
완료 stage는 재사용하지만, topology, 최초 coordinate file, generated engine input
또는 해당 stage가 소비하는 predecessor restart가 바뀌면 실행 전에 거부합니다.
기록이 없는 기존 완료·partial 결과도 보존하고 거부합니다. Identity를 새 input으로
덮어쓰거나 과거 결과에 소급 생성하지 않습니다. 변경된 계산은 새 `WORK_DIR`에서
build부터 시작합니다. 완료 marker는 engine 성공과 필요한 output 확인 뒤에
생성합니다. Output으로 갱신되는 bias/replica state와 완료한 predecessor input을
구분하며, 기존 input을 바꾸지 않는 후속 segment 추가는 허용합니다.

실행 때 다시 소비하지 않는 원본 `config.toml` 변경은 이미 생성된 input에 반영되지
않습니다. 검사 대상은 실제 실행 input과 실행 때 소비하는 설정입니다. Identity에는
절대 경로가 들어가므로 진행 중인 work tree나 source 파일을 이동·복사한 뒤 이어서
실행하는 방식은 지원하지 않습니다.

Lock metadata는 `work.writers/<token>/owner.json`에 host, PID, command와 scope를
기록합니다. 등록 중에는 `work.writers/.gate/owner.json`도 사용합니다. 정상 종료,
실패 또는 INT/TERM 후에는 자식 engine 종료를 확인하고 자신의 lock만 해제합니다.
SIGKILL 또는 node 장애로 남은 lock은 자동으로 지우지 않습니다. Metadata를 읽고
관련 host의 job과 모든 자식 process가 종료됐는지 확인한 뒤 해당 token의
`owner.json`과 비어 있는 directory를 수동으로 제거합니다. `.gate`가 남았으면 모든
등록·해제 작업의 종료도 확인합니다. PID만으로 다른 host의 작업 종료를 판단하지
않습니다. Cluster filesystem의 atomic directory 생성과 remote/daemon process
종료는 로컬 fixture에서 검증하지 않았습니다.


Weight diagnostics는 finite이며 음수가 아닌 weight와 segment별 1차원 finite pcoord를 요구합니다. Total weight는 유한한 양수여야 합니다. 합을 1로 강제 보정하지 않고 실제 합을 출력합니다. 잘못된 HDF5를 읽으면 기존 TSV를 보존합니다. `calc_pcoord.sh`는 cpptraj output의 numeric RMSD와 column 수를 확인하고 잘못된 값을 반환하지 않습니다.

공개 analysis entry는 자동으로 `helpers/writer_guard.py`를 호출해 같은 output의 동시 writer를 거부합니다. Engine 실행부터 결과 게시까지 보호하며, signal 종료 시 child가 멈춘 뒤 lock을 해제합니다. Lock을 임의로 삭제해 실행을 재개하지 않습니다.

## English

Basis-state heating and equilibration use `ntwx=0` and do not generate `.nc`. Completion and reuse require each stage’s `.out`, `.info`, and restart: `heat.rst7` for heating and `bstates/basis.rst7` for equilibration. Minimization diagnostics go to `minimize.info`. Missing or empty required output stops the build and preserves existing files.

User-facing entry points remain in this directory root. `helpers/` contains leaf-local internal code called automatically by `build.sh`, `run.sh`, or `anal.py`; it is not a separate entry point.

Interrupted or unmarked stage output is retained and stops the workflow instead of being deleted or rerun automatically.

The first-pass LEaP input and water-count `solvated.pdb` are created under `work/.build_tmp.XXXXXX/`. A successful build removes that temporary directory; a failed build prints and retains it for diagnosis. Final PDB, topology, restart, resolved config, and LEaP logs are retained.

### Config choices

| Option | Current support | Default | Effect |
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

No other `mode` value is currently implemented. Both `basis_state_file` and
`target_state_file` are required in `steady_state` mode; `init.sh` reads them
when initializing `work/west.h5`.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

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
Interrupted minimization, heating, or equilibration output is retained and the
build stops. Archive the existing output or choose a new `WORK_DIR` before
starting again.
Basis-state MD follows whole-system minimization, restrained NVT heating from
20 K, and NPT equilibration.
Once `west.h5` exists, `build.sh` refuses to overwrite production state.
Completed WESTPA blocks are skipped; `--block N` selects one block.
`init.sh` never deletes an existing `west.h5` or segment data. Initialize a
new run in a different `WORK_DIR`.

The default is serial `pmemd.cuda` on one GPU. A CPU engine may use the
`processes` work manager and multiple workers. GPU worker placement remains an
external scheduler decision. Analysis reads the resolved bins and target file,
then reports total weight, effective walker count, bin occupancy, and target
arrivals. Target counts alone are not a rate estimate.

### Engine selection and run state

`AMBER_ENGINE` overrides `run.engine` in the build-generated `work/resolved_config.toml`. Accepted executable names are `pmemd.cuda`, `pmemd`, `sander`; installation paths are accepted. Build reads the same key from the source config. WESTPA propagation follows the same override precedence. Existing CPU process-worker restrictions still apply. Empty overrides, missing engine settings and unsupported executables fail instead of falling back to a default. The runner invokes `helpers/config_utils.py` automatically to read this setting.

When reusing a completed topology with the same input and config, no new temporary
directory is created or removed. A successful new build removes its own
`.build_tmp.*` directory; a failed build retains that directory and diagnostic files.

Downloads replace the final PDB only after validating atom records in a temporary file. Failure preserves the existing PDB and removes the temporary file.

The `init.sh` and `run.sh` entries resolve a relative `WORK_DIR` against `WEST_SIM_ROOT`, so callbacks use the same inputs and state after entering a segment directory.

### Concurrent runs and input changes

Local WESTPA callbacks inherit a verified manager writer. Standalone callbacks acquire separate scopes for segment and progress-coordinate outputs. Callback scripts are included in the init/run input identity.

Build/init/run wrappers protect topology/basis, HDF5, and block markers in the same work tree. Separate `WORK_DIR` trees can run independently. WESTPA manages weights and resampling; HDF5 is not hashed as an immutable input.
The automatically called `helpers/writer_guard.py` registers scopes and supervises
child processes; `helpers/input_identity.py` compares SHA256 hashes of small
calculation inputs. Help and dry-run commands create no locks or identities.

Inputs are recorded in `.*.identity.json` before the first stage launch. Completed
stages can reuse identical inputs. Changes to topology, initial coordinates,
generated engine inputs, or the predecessor restart consumed by a stage cause
rejection before execution. Existing complete or partial results without an
identity are also retained and rejected. Records are never replaced or created
retroactively for old results. Start a changed calculation with a fresh
`WORK_DIR`, beginning with the build. Completion markers are written
after engine success and required-output checks. Mutable bias/replica outputs are
distinguished from completed predecessor inputs; additional segments that leave
existing inputs intact are allowed.

Changes to a source `config.toml` that is not read at runtime do not update inputs
already generated by the build. Checks cover actual execution inputs and settings
consumed at runtime. Identities contain absolute paths: moving or copying an
ongoing work tree or its source files and then continuing is unsupported.

`work.writers/<token>/owner.json` records the host, PID, command, and scopes.
`work.writers/.gate/owner.json` is used briefly during registration and release.
Normal exits, failures, and INT/TERM release only the current job's lock after
verifying child-engine termination. Locks left by SIGKILL or node failure are
retained. Read the metadata and verify that the job and all children have stopped
on the relevant hosts before manually removing that token's `owner.json` and its
empty directory. A leftover `.gate` also requires checking that all registration
and release operations have stopped. A PID alone does not establish that a job
on another host has ended. Atomic directory operations on cluster filesystems
and termination of remote/daemon processes were not tested by local fixtures.

Weight diagnostics require finite, nonnegative weights and finite one-dimensional pcoord for each segment. Total weight must be finite and positive; diagnostics report the actual sum without renormalizing it to one. Invalid HDF5 leaves existing TSV files intact. `calc_pcoord.sh` checks numeric RMSD and column counts before returning a cpptraj result.

Public analysis entries automatically use `helpers/writer_guard.py` to reject concurrent writers to the same output. Protection covers engine execution through publication, and signal cleanup drains children before releasing the lock. Do not delete a lock to force a retry.
