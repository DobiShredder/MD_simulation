# GaREUS template

## 한국어

최소 2개·짝수 replica만 지원합니다. `build.sh`와 `run.sh`는 홀수 schedule을 자동 조정하지 않고 거부합니다. `run.sh --dry-run`도 실제 state table의 count를 검사합니다. 기존 홀수 결과는 새 work directory에서 다시 준비합니다.

사용자가 직접 실행하는 파일은 이 directory의 root에 있습니다. `helpers/`는 `build.sh`, `run.sh` 또는 `anal.py`가 자동 호출하는 leaf-local 내부 code이며 직접 실행하지 않습니다.

중단되거나 marker가 없는 stage output은 자동 삭제하거나 재실행하지 않고 보존한 채 중단합니다.

Water count를 위한 first-pass LEaP input과 `solvated.pdb`는 `work/.build_tmp.XXXXXX/`에서 생성합니다. 전체 build가 성공하면 temporary directory를 삭제하고, 실패하면 진단을 위해 경로를 출력하고 보존합니다. Final PDB, topology, restart, resolved config와 LEaP log는 유지합니다. Replica는 공통 `work/system.parm7`과 `work/system.rst7`을 직접 참조하며 replica별 engine input, bias, seed와 restart는 각 directory에 남습니다.

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

REUS의 umbrella-state 교환에 system 전체의 dual-boost GaMD를 결합합니다.
한 reference replica에서 만든 `gamd-restart.dat`를 모든 window에 복사하므로
production 시작 시 같은 boost parameter를 사용합니다.

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
```

Reaction-coordinate mask, center, force와 exchange interval은 REUS와 같습니다.
GaMD statistics 길이와 `sigma0=6 kcal/mol`은 `[gamd]`에 기록됩니다. Build는
REUS와 같은 window/restraint generator에 GaMD parameter-preparation input을
추가합니다. Run은 GaMD state continuation과 AMBER `-rem 3` exchange command를
조합합니다. MD restart, window restraint와 GaMD state 중 하나라도 partial이면
production을 덮어쓰지 않습니다.
`download.sh PDB_ID`는 source PDB를 내려받고 `build.sh`는 topology, window와
GaMD input을 생성합니다.

기본 production은 window당 200 ns입니다. 2 fs timestep과 1000-step exchange
interval에서 `nstlim=1000`, `numexchg=100000`으로 생성됩니다.
기본 20개 window는 6–25 Å이며 replica 009에서 공통 GaMD state를 준비합니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Window equilibration에 적용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NVT` | GaMD exchange production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | Window별 seed를 무작위로 만들거나 정수에서 파생합니다. |

`windows_file`은 항상 명시적인 center 목록을 읽으며 `auto`/`file` mode가
아닙니다. Blank line과 `#`로 시작하는 comment line을 제외하고 각 행에는 center
하나만 적습니다. Center 목록은 비어 있지 않고 중복 없이 오름차순이어야 합니다.
각 행이 한 exchange state가 되고 최종 mapping은 `work/states.tsv`에 기록됩니다.

### Engine 선택과 실행 상태

`AMBER_ENGINE`이 설정되어 있으면 이를 사용하며, 없으면 build가 기록한 `work/resolved_config.toml`의 `run.engine`을 읽습니다. 허용하는 executable 이름은 `pmemd.cuda`이며 설치 경로를 지정할 수 있습니다. Exchange production에는 `AMBER_MPI_ENGINE` 또는 resolved config의 `run.mpi_engine`을 사용하며 executable 이름은 `pmemd.cuda.MPI`입니다. 기존 resolved config에 `run.mpi_engine`이 없으면 `AMBER_MPI_ENGINE`을 지정하거나 새 `WORK_DIR`에서 build합니다. 빈 override, 누락된 engine 설정과 지원하지 않는 executable은 기본값으로 대체하지 않고 error로 중단합니다. Runner가 `helpers/config_utils.py`를 자동 호출해 이 설정을 읽습니다.

Engine이 성공하고 모든 replica의 stage별 필수 output이 존재할 때만 `.STAGE.complete`를 기록합니다. Minimization은 `.out`, `.rst7`, `.info`를 요구하며 MD stage는 `.nc`도 요구합니다. Exchange production은 `exchange.NNN.log`도 확인합니다. GaREUS production은 GaMD log와 restraint 기록도 확인합니다. Marker만 있거나 marker 없는 output이 남아 있으면 파일을 보존하고 중단합니다. 새 `WORK_DIR`를 사용하거나 남은 파일을 검토한 뒤 재실행합니다. 기존 결과를 자동으로 완료 처리하지 않습니다.

Build는 기존 topology/restart file이 있으면 input을 변경하기 전에 중단하고 파일을 보존합니다. 새 build에는 별도 `WORK_DIR`을 지정합니다.

다운로드는 임시 파일의 PDB atom record를 확인한 뒤 최종 파일로 교체합니다. 실패하면 기존 PDB를 보존하고 임시 파일을 정리합니다.

### 동시 실행과 input 변경

Build와 run은 shared input, replica output 및 exchange state가 있는 work tree를 함께 보호합니다. 같은 tree에서 replica별로 따로 실행하지 않습니다. 서로 다른 `WORK_DIR`은 독립 실행을 허용합니다.
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


## English

Only even replica counts of at least two are supported. `build.sh` and `run.sh` reject odd schedules without adjusting them. `run.sh --dry-run` checks the actual state-table count too. Prepare a new work directory for results built with an odd schedule.

User-facing entry points remain in this directory root. `helpers/` contains leaf-local internal code called automatically by `build.sh`, `run.sh`, or `anal.py`; it is not a separate entry point.

Interrupted or unmarked stage output is retained and stops the workflow instead of being deleted or rerun automatically.

The first-pass LEaP input and water-count `solvated.pdb` are created under `work/.build_tmp.XXXXXX/`. A successful build removes that temporary directory; a failed build prints and retains it for diagnosis. Final PDB, topology, restart, resolved config, and LEaP logs are retained. Replicas reference the shared `work/system.parm7` and `work/system.rst7` directly, while replica-specific engine inputs, bias, seeds, and restart files remain in each directory.

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to window equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NVT` | Sets GaMD exchange-production `ntb` and `ntp`. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | Creates random window seeds or derives them from the integer. |

`windows_file` always supplies an explicit center list and is not an
`auto`/`file` mode. After blank lines and full-line `#` comments are skipped,
each row must contain exactly one center. The list must be nonempty, unique,
and increasing. Each row becomes one exchange state, and the final mapping is
written to `work/states.tsv`.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

GaREUS combines umbrella-state exchange with a common system-wide dual GaMD
boost. One reference replica prepares `gamd-restart.dat`, which is copied to
all windows before production. The build extends the shared REUS window
generator with GaMD preparation input, and the run combines GaMD state
continuation with the AMBER `-rem 3` exchange command. Partial production,
restraint, or GaMD state is not overwritten. `download.sh`
retrieves a source PDB and `build.sh` creates the topology, windows, and GaMD
inputs. The default is 200 ns
per window, rendered as `nstlim=1000` and `numexchg=100000` at 2 fs. The
default has 20 windows from 6 to 25 Å and prepares the shared GaMD state in
replica 009.

### Engine selection and run state

`AMBER_ENGINE` overrides `run.engine` in the build-generated `work/resolved_config.toml`. Accepted executable names are `pmemd.cuda`; installation paths are accepted. Exchange production uses `AMBER_MPI_ENGINE` or resolved `run.mpi_engine`, with executable name `pmemd.cuda.MPI`. If an older resolved config lacks `run.mpi_engine`, set `AMBER_MPI_ENGINE` or build in a new `WORK_DIR`. Empty overrides, missing engine settings and unsupported executables fail instead of falling back to a default. The runner invokes `helpers/config_utils.py` automatically to read this setting.

A `.STAGE.complete` marker is written only after engine success and all required replica outputs are present. Minimization requires `.out`, `.rst7` and `.info`; MD stages also require `.nc`. Exchange production also requires `exchange.NNN.log`. GaREUS production also requires its GaMD log and restraint records. A marker without required outputs, or outputs without a marker, causes an error while preserving files. Use a new `WORK_DIR` or inspect the retained files before retrying. Legacy outputs are never marked complete automatically.

Build stops before changing inputs when topology/restart files already exist, preserving those files. Use a separate `WORK_DIR` for a new build.

Downloads replace the final PDB only after validating atom records in a temporary file. Failure preserves the existing PDB and removes the temporary file.

### Concurrent runs and input changes

Build and run protect the shared inputs, replica outputs, and exchange state in the work tree. Replicas in the same tree are not separate concurrent runs. Separate `WORK_DIR` trees can run independently.
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

GaREUS continuation은 replica별 `prepared.gamd.rst`와 `production.NNN.gamd.rst` snapshot에서 GaMD state를 이어받습니다. `gamd-restart.dat`는 각 segment 동안 갱신되는 engine output입니다.

GaREUS continuation inherits GaMD state from each replica’s `prepared.gamd.rst` and `production.NNN.gamd.rst` snapshots. `gamd-restart.dat` is the evolving engine output during a segment.
