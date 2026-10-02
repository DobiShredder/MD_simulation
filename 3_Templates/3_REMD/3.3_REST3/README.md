# REST3 template

## 한국어

사용자가 직접 실행하는 파일은 이 directory의 root에 있습니다. `helpers/`는 `build.sh`, `run.sh` 또는 `anal.py`가 자동 호출하는 leaf-local 내부 code이며 직접 실행하지 않습니다.

중단되거나 marker가 없는 stage output은 자동 삭제하거나 재실행하지 않고 보존한 채 중단합니다.

Water count를 위한 first-pass LEaP input과 `solvated.pdb`는 `work/.build_tmp.XXXXXX/`에서 생성합니다. 전체 build가 성공하면 temporary directory를 삭제하고, 실패하면 진단을 위해 경로를 출력하고 보존합니다. Final PDB, topology, restart, resolved config와 LEaP log는 유지합니다. REST build의 preprocessing TPR, processed topology와 energy-check raw file도 같은 temporary directory에 둡니다. 성공 후에는 `work/topol.top`, `work/system.gro`, replica topology, `work/build.log`, `work/build_summary.toml`과 `work/energy_check.tsv`를 남깁니다. `./build.sh --keep-intermediates INPUT.pdb`를 사용하면 성공 후에도 temporary directory를 보존합니다. Replica는 공통 `work/system.gro`를 직접 참조합니다. 실제 minimization, equilibration, production TPR·`*.grompp.log`와 restart는 정리하지 않습니다.

이 directory의 runtime code는 별도로 복사해 사용할 수 있습니다. GROMACS를
build할 때는 상위 `patches/` directory의 correction도 함께 사용합니다. Python
dependency는 복사한 directory의 `requirements.txt`를 사용해 설치합니다.

REST2 scaling에 κ schedule을 추가합니다. 기본 schedule은 357 K까지 κ=1.0을
유지하고 450 K에서 1.020이 되도록 선형 보간합니다. 이 값은 universal default가
아니며 IDP와 force-field/water 조합별 pilot simulation에서 compactness와 exchange를
확인해야 합니다. κ 효과는 temperature predictor에 포함되지 않습니다.

```bash
./download.sh 1UBQ
./build.sh structure/1UBQ.pdb
replicas=$(awk 'NR > 1 {count++} END {print count + 0}' work/states.tsv)
./run.sh --cpus "$replicas" --gpus 1
```

명시적인 κ 목록은 `[rest3_kappa]`의 `mode = "file"`과 `file`로 입력합니다.
Temperature와 κ 목록의 길이는 같아야 합니다. Runtime에는 REST2와 같은 patched
GROMACS/PLUMED HREX build와 상위 directory의
[`HREX_WORKLOAD_FIX_1` correction](../patches/gromacs-2024.3-plumed-2.10-hrex-energy.patch)이
필요합니다. 적용 순서와 검증 범위는 [상위 README](../README.md)에 있습니다.
`download.sh`는 source PDB와 함께
검증된 `repex-topology-parser` 0.2.2 source를 내려받습니다.
기본 OPC 설정에서는 `kappa_atom_names=['OW']`가 water oxygen type을 선택합니다.
`helpers/verify_rest3.py`는 O/H1/H2/EP의 type·charge·mass와 solvent interaction이
replica 사이에서 보존되는지 검사합니다. `water_model = "TIP3P"` compatibility
option도 유지합니다.
각 replica의 preproduction은 tutorial과 같은 minimization과 NPT equilibration
순서이며 별도 heating stage는 사용하지 않습니다. 첫 `grompp` 전에는 ParmEd가
출력한 긴 CMAP 실수를 GROMACS 2024.x가 읽을 수 있는 정밀도로 정규화합니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 REST3 water atom type을 함께 결정합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `tempered_region` | `solute`만 지원 | `solute` | Water와 ion을 제외한 전체 solute를 tempering합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Replica equilibration에 적용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | GROMACS production pressure coupling을 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 LINCS를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | State별 seed를 무작위로 만들거나 정수에서 파생합니다. |

| Mode option | Mode | 사용하는 설정 | 무시하는 설정과 결과 |
| --- | --- | --- | --- |
| `temperature_mode` | `auto` (기본값) | `minimum_temperature`, `maximum_temperature`, `target_exchange_probability`, `generator_tolerance` | `temperature_file`을 무시하고 tempered-solute atom 수로 ladder를 계산합니다. |
| `temperature_mode` | `file` | `temperature_file` | Auto 설정을 무시하고 file temperature에서 `lambda_pp`와 `lambda_pw`를 계산합니다. |
| `rest3_kappa.mode` | `linear` (기본값) | `onset_temperature`, `maximum_temperature`, `maximum_kappa` | `file`을 무시하고 onset 이하 1.0, 이후 선형 κ를 계산합니다. |
| `rest3_kappa.mode` | `file` | `file` | Linear 설정을 무시하고 κ 목록을 순서대로 사용합니다. |

Temperature와 κ file은 사용자가 생성해야 합니다. 두 file 모두 공백, comma,
semicolon, `|`를 구분자로 받고 `#` comment를 허용합니다. Temperature는 둘 이상의
양수여야 하고 중복 없이 오름차순이며 첫 값은 `run.temperature`와 같아야 합니다.
κ 개수는 temperature state 수와 같아야 하고 모든 κ는 1.0 이상이어야 합니다.
두 mode를 조합할 수 있으며 최종 temperature, λ, κ와 seed는
`work/states.tsv`에서 확인합니다.

`maxwarn`은 public config option이 아닙니다. `helpers/grompp_utils.bash`는 `grompp`를
먼저 warning 우회 없이 실행합니다. 변환된 topology의 남은 전하가 ±0.01 e
이내이고 `System has non-zero total charge` warning 하나만 있을 때만
내부적으로 `-maxwarn 1`로 다시
실행합니다. 다른 warning은 해당 `*.grompp.log`를 남기고 계산을 중단합니다.

### Engine 선택과 실행 상태

`GROMACS`와 `GROMACS_MPI`가 설정되어 있으면 각각 사용하며, 없으면 build가 기록한 `work/resolved_config.toml`의 `run.equilibration_engine`과 `run.production_engine`을 읽습니다. Executable 이름은 각각 `gmx`, `gmx_mpi`이며 설치 경로를 지정할 수 있습니다. Build의 GROMACS command도 source config의 같은 선택과 override를 사용합니다. 최초 minimization은 공통 `work/system.gro`를, 이후 stage는 replica별 `.gro`와 필요한 `.cpt`를 사용합니다. 빈 override, 누락된 engine 설정과 지원하지 않는 executable은 기본값으로 대체하지 않고 error로 중단합니다. Runner가 `helpers/config_utils.py`를 자동 호출해 이 설정을 읽습니다.

Build는 기존 topology/restart file이 있으면 input을 변경하기 전에 중단하고 파일을 보존합니다. 새 build에는 별도 `WORK_DIR`을 지정합니다.

다운로드는 임시 파일의 PDB atom record를 확인한 뒤 최종 파일로 교체합니다. 실패하면 기존 PDB를 보존하고 임시 파일을 정리합니다.

Replica 실행이나 batch 도중 `grompp`가 실패하면 이미 시작한 replica가 모두 종료될 때까지 기다린 뒤 실패로 종료합니다. 후속 stage는 시작하지 않습니다.

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

User-facing entry points remain in this directory root. `helpers/` contains leaf-local internal code called automatically by `build.sh`, `run.sh`, or `anal.py`; it is not a separate entry point.

Interrupted or unmarked stage output is retained and stops the workflow instead of being deleted or rerun automatically.

The first-pass LEaP input and water-count `solvated.pdb` are created under `work/.build_tmp.XXXXXX/`. A successful build removes that temporary directory; a failed build prints and retains it for diagnosis. Final PDB, topology, restart, resolved config, and LEaP logs are retained. REST preprocessing TPRs, processed topologies, and raw energy-check files use the same temporary directory. After success, the build retains `work/topol.top`, `work/system.gro`, replica topologies, `work/build.log`, `work/build_summary.toml`, and `work/energy_check.tsv`. Use `./build.sh --keep-intermediates INPUT.pdb` to retain the temporary directory after success. Replicas reference the shared `work/system.gro` directly. Run-stage minimization, equilibration, production TPRs, `*.grompp.log` files, and restarts are never cleaned.

`maxwarn` is not a public configuration option. `helpers/grompp_utils.bash` first runs
`grompp` without a warning override and retries it with `-maxwarn 1` only when the
converted topology has a residual charge within ±0.01 e and the log contains
exactly one `System has non-zero total charge` warning. Any other warning stops
the workflow and remains in the corresponding `*.grompp.log`.

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects both LEaP water and REST3 water atom types. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `tempered_region` | `solute` only | `solute` | Tempers the complete non-water, non-ion solute. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to replica equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Selects GROMACS production pressure coupling. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies LINCS to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | Creates random state seeds or derives them from the integer. |

| Mode option | Mode | Settings used | Ignored settings and result |
| --- | --- | --- | --- |
| `temperature_mode` | `auto` (default) | `minimum_temperature`, `maximum_temperature`, `target_exchange_probability`, `generator_tolerance` | Ignores `temperature_file` and predicts a ladder from tempered-solute atoms. |
| `temperature_mode` | `file` | `temperature_file` | Ignores auto settings and computes `lambda_pp` and `lambda_pw` from file temperatures. |
| `rest3_kappa.mode` | `linear` (default) | `onset_temperature`, `maximum_temperature`, `maximum_kappa` | Ignores `file`; κ is 1.0 through onset and then increases linearly. |
| `rest3_kappa.mode` | `file` | `file` | Ignores linear settings and uses the κ list in order. |

The user must create the temperature and κ files. Both accept whitespace,
commas, semicolons, and `|` as separators and allow `#` comments. Temperatures
must contain at least two unique, increasing positive values, with the first
equal to `run.temperature`. The κ count must equal the temperature-state count,
and every κ must be at least 1.0. The two modes can be combined; final
temperatures, λ values, κ values, and seeds are recorded in `work/states.tsv`.

This directory's runtime code can be copied on its own. Keep the parent
`patches/` correction available when building GROMACS. Install the Python
dependencies from the local `requirements.txt` after copying it.

Production requires the same patched GROMACS/PLUMED HREX build as REST2 and
the [`HREX_WORKLOAD_FIX_1` correction](../patches/gromacs-2024.3-plumed-2.10-hrex-energy.patch).
See the [parent README](../README.md) for application steps and validation
scope.

REST3 adds a κ schedule to REST2 scaling. The default keeps κ at 1.0 through
357 K and linearly reaches 1.020 at 450 K. This is not a universal value; assess
compactness and exchange in a system- and force-field-specific pilot run. The
temperature predictor does not model the κ correction. File mode accepts an
explicit κ list with one value per state. Replica preproduction uses the same
minimization-to-NPT-equilibration sequence as the fixed tutorial.
With the default OPC model, `kappa_atom_names=['OW']` selects the water oxygen
type. `helpers/verify_rest3.py` checks preservation of O/H1/H2/EP atom records and
solvent interactions across replicas. The optional `water_model = "TIP3P"`
compatibility path remains available. Before the first `grompp`, the build
normalizes long ParmEd-formatted CMAP numbers to a precision accepted by
GROMACS 2024.x.

### Engine selection and run state

`GROMACS` and `GROMACS_MPI` override `run.equilibration_engine` and `run.production_engine` in the build-generated `work/resolved_config.toml`. Executable names must be `gmx` and `gmx_mpi`; installation paths are accepted. GROMACS commands during build use the same selection and override from the source config. Initial minimization reads shared `work/system.gro`; subsequent stages read each replica’s `.gro` and, where required, `.cpt`. Empty overrides, missing engine settings and unsupported executables fail instead of falling back to a default. The runner invokes `helpers/config_utils.py` automatically to read this setting.

Build stops before changing inputs when topology/restart files already exist, preserving those files. Use a separate `WORK_DIR` for a new build.

Downloads replace the final PDB only after validating atom records in a temporary file. Failure preserves the existing PDB and removes the temporary file.

If a replica or a mid-batch `grompp` command fails, the runner waits for all already-started replicas before returning failure. Subsequent stages do not start.

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
