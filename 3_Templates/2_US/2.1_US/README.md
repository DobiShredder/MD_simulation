# Ratchet MD and umbrella sampling template

## 한국어

사용자가 직접 실행하는 파일은 이 directory의 root에 있습니다. `helpers/`는 `build.sh`, `run.sh` 또는 `anal.py`가 자동 호출하는 leaf-local 내부 code이며 직접 실행하지 않습니다.

중단되거나 marker가 없는 stage output은 자동 삭제하거나 재실행하지 않고 보존한 채 중단합니다.

Water count를 위한 first-pass LEaP input과 `solvated.pdb`는 `work/.build_tmp.XXXXXX/`에서 생성합니다. 전체 build가 성공하면 temporary directory를 삭제하고, 실패하면 진단을 위해 경로를 출력하고 보존합니다. Final PDB, topology, restart, resolved config와 LEaP log는 유지합니다.

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

Ratchet MD(rMD)로 reaction coordinate가 목표 방향으로 증가하는 pathway를
만들고, ordered first-crossing frame을 umbrella window seed로 사용합니다.
rMD trajectory는 seed 생성에만 사용하며 PMF는 US production에서 계산합니다.

```bash
./build.sh prepared.pdb

cd rmd
./run.sh
python3 anal.py

cd ../us
./build.sh
./run.sh
```

`build.sh`는 rMD와 모든 umbrella window가 공유하는 topology와 restart를
만듭니다. `rmd/run.sh`는 tutorial과 같은 minimization, heating,
equilibration, PLUMED ABMD command 순서로 pathway를 생성합니다.
`rmd/anal.py`는 seed restart를 만들고 `us/build.sh`가 `windows.tsv`의
`CENTER_A FORCE_KCAL_MOL_A2` row를 window directory로 변환합니다.
`download.sh PDB_ID`는 RCSB source PDB를 수정하지 않고 `structure/`에
받습니다. Protonation, missing atom과 불필요한 chain은 build 전에 사용자가
정리합니다.

`[umbrella]` atom mask는 각각 한 atom을 선택해야 합니다.
`[ratchet_md] target_distance`는 Å로 입력하고 PLUMED `ABMD TO`의 nm로
변환합니다. `kappa`는 PLUMED ABMD의 ρ 정의를 따르며 일반
harmonic distance force constant와 같은 양이 아닙니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NVT`, `NPT` | `NPT` | Seed와 window equilibration의 `ntb`와 `ntp`를 설정합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Window production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | `"random"`은 AMBER `ig=-1`, 정수는 고정 seed를 사용합니다. |

`windows_file`은 항상 명시적인 window center 목록을 읽습니다. 이 option에는
`auto`/`file` mode 구분이 없습니다. Blank line과 `#`로 시작하는 comment line을
제외한 각 행은 whitespace로 구분한 `CENTER_A FORCE` 두 값이어야 합니다. 두 값은
양수이고 center는 중복 없이 오름차순이어야 합니다. `production_segments`는
현재 `1`만 지원합니다.

### Engine 선택과 실행 상태

`AMBER_ENGINE`이 설정되어 있으면 이를 사용하며, 없으면 build가 기록한 `work/resolved_config.toml`의 `run.engine`을 읽습니다. 허용하는 executable 이름은 `pmemd.cuda`이며 설치 경로를 지정할 수 있습니다. `rmd/`와 `us/` runner는 상위의 공통 `../work/resolved_config.toml`을 읽습니다. 빈 override, 누락된 engine 설정과 지원하지 않는 executable은 기본값으로 대체하지 않고 error로 중단합니다. Runner가 `helpers/config_utils.py`를 자동 호출해 이 설정을 읽습니다.

Build는 기존 topology/restart file이 있으면 input을 변경하기 전에 중단하고 파일을 보존합니다. 새 build 전에는 기존 `work/`를 다른 위치에 보관하거나 별도 tutorial 사본을 사용합니다.

다운로드는 임시 파일의 PDB atom record를 확인한 뒤 최종 파일로 교체합니다. 실패하면 기존 PDB를 보존하고 임시 파일을 정리합니다.

### 동시 실행과 input 변경

Parent build, rMD, seed analysis와 US build/run은 parent `work.writers`를 공유하고 실제 output 범위를 등록합니다. 선택한 US window는 서로 독립 실행할 수 있지만, 전체 window를 만드는 build와는 충돌합니다.
자동 호출되는 `helpers/writer_guard.py`가 scope 등록과 자식 process 종료를 관리하고,
`helpers/input_identity.py`가 작은 계산 input의 SHA256을 비교합니다.
`--help`와 `--dry-run`은 lock과 identity를 만들지 않습니다.

첫 stage 실행 전에 사용한 input을 `.*.identity.json`에 기록합니다. 같은 input의
완료 stage는 재사용하지만, topology, 최초 coordinate file, generated engine input
또는 해당 stage가 소비하는 predecessor restart가 바뀌면 실행 전에 거부합니다.
기록이 없는 기존 완료·partial 결과도 보존하고 거부합니다. Identity를 새 input으로
덮어쓰거나 과거 결과에 소급 생성하지 않습니다. 변경된 계산은 새 `WORK_DIR`에서
build부터 시작합니다. 고정 경로를 쓰는 parent build/rMD/US build는 leaf를 별도 directory에 복사해 새 계산을 시작합니다. 완료 marker는 engine 성공과 필요한 output 확인 뒤에
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

### Window table과 seed generation

`rmd/anal.py`와 `us/build.sh`는 `resolved_config.toml`의 `umbrella.windows_file`을 같은 leaf 기준으로 읽습니다. 기본값은 `us/windows.tsv`입니다. Seed 추출은 table 사본을 `rmd/work/seeds/windows.tsv`에 저장합니다. Builder는 이 사본과 실제 table이 같은지, `seeds.tsv`의 개수·순서·center가 같은지 검사한 뒤 window를 만듭니다. Center 또는 force를 바꾸었다면 별도 work directory에서 seed부터 새로 생성합니다.

## English

User-facing entry points remain in this directory root. `helpers/` contains leaf-local internal code called automatically by `build.sh`, `run.sh`, or `anal.py`; it is not a separate entry point.

Interrupted or unmarked stage output is retained and stops the workflow instead of being deleted or rerun automatically.

The first-pass LEaP input and water-count `solvated.pdb` are created under `work/.build_tmp.XXXXXX/`. A successful build removes that temporary directory; a failed build prints and retains it for diagnosis. Final PDB, topology, restart, resolved config, and LEaP logs are retained.

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NVT`, `NPT` | `NPT` | Sets `ntb` and `ntp` for seed and window equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Sets window-production `ntb` and `ntp`. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | `"random"` maps to AMBER `ig=-1`; an integer fixes the seed. |

`windows_file` always supplies an explicit list of window centers. It does not
have separate `auto` and `file` modes. After blank lines and full-line `#`
comments are skipped, each row must contain two whitespace-separated values,
`CENTER_A FORCE`. Both values must be positive, and centers must be unique and
in increasing order. `production_segments` currently supports only `1`.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

Ratchet MD generates a target-directed pathway along the configured distance.
Ordered first-crossing frames seed the umbrella windows; only the umbrella
production trajectories are used for the PMF.

The shared `build.sh` creates one topology and restart for rMD and every
window. `rmd/run.sh` follows the tutorial minimization, heating, equilibration,
and PLUMED ABMD command structure. `rmd/anal.py` extracts seed restarts, and
`us/build.sh` converts the two-column `windows.tsv` table into window
directories before `us/run.sh` propagates them.
`download.sh PDB_ID` retrieves an unmodified RCSB PDB into `structure/`;
protonation, missing atoms, and unwanted chains remain user preparation steps.

Each umbrella atom mask must select one atom. `target_distance` is entered in
Å and converted to the PLUMED `ABMD TO` value in nm. `kappa` follows the
PLUMED ABMD ρ definition and is not an ordinary harmonic-distance force
constant.

### Engine selection and run state

`AMBER_ENGINE` overrides `run.engine` in the build-generated `work/resolved_config.toml`. Accepted executable names are `pmemd.cuda`; installation paths are accepted. The `rmd/` and `us/` runners read the shared `../work/resolved_config.toml`. Empty overrides, missing engine settings and unsupported executables fail instead of falling back to a default. The runner invokes `helpers/config_utils.py` automatically to read this setting.

Build stops before changing inputs when topology/restart files already exist, preserving those files. Preserve the existing `work/` elsewhere or use a separate tutorial copy before a new build.

Downloads replace the final PDB only after validating atom records in a temporary file. Failure preserves the existing PDB and removes the temporary file.

### Concurrent runs and input changes

Parent build, rMD, seed analysis, and US build/run share the parent `work.writers` registry with explicit output scopes. Selected US windows can run independently; a whole-window build conflicts with them.
The automatically called `helpers/writer_guard.py` registers scopes and supervises
child processes; `helpers/input_identity.py` compares SHA256 hashes of small
calculation inputs. Help and dry-run commands create no locks or identities.

Inputs are recorded in `.*.identity.json` before the first stage launch. Completed
stages can reuse identical inputs. Changes to topology, initial coordinates,
generated engine inputs, or the predecessor restart consumed by a stage cause
rejection before execution. Existing complete or partial results without an
identity are also retained and rejected. Records are never replaced or created
retroactively for old results. Start a changed calculation with a fresh
`WORK_DIR`, beginning with the build. For the fixed-path parent build, rMD, and US build, start from a separate copy of the leaf. Completion markers are written
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

### Window tables and seed generations

Both `rmd/anal.py` and `us/build.sh` read `umbrella.windows_file` from `resolved_config.toml`, relative to the leaf directory; the default is `us/windows.tsv`. Seed extraction saves a copy at `rmd/work/seeds/windows.tsv`. Before creating windows, the builder checks this copy against the current table and verifies the count, order, and centers in `seeds.tsv`. Changing centers or forces requires a new seed generation in a separate work directory.
