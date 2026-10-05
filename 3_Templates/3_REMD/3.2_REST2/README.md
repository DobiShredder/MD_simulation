# REST2 template

## 한국어

최소 2개·짝수 replica만 지원합니다. `build.sh`와 `run.sh`는 홀수 schedule을 자동 조정하지 않고 거부합니다. `run.sh --dry-run`도 실제 state table의 count를 검사합니다. 기존 홀수 결과는 새 work directory에서 다시 준비합니다.

File schedule은 LEaP 실행 전에 검사합니다. Auto count는 임시 topology에서 predictor를 실행한 뒤 검사하고, 통과한 preparation만 work directory에 복사합니다. 홀수이면 기존 input/state/log를 보존하고 진단용 temporary directory를 남깁니다. `build.sh --dry-run`은 file을 검사하지만 auto predictor를 실행하지 않으므로 auto count 검증은 실제 build까지 보류됩니다. Predictor 계산식과 temperature/target probability는 자동 변경하지 않습니다.

사용자가 직접 실행하는 파일은 이 directory의 root에 있습니다. `helpers/`는 `build.sh`, `run.sh` 또는 `anal.py`가 자동 호출하는 leaf-local 내부 code이며 직접 실행하지 않습니다.

중단되거나 marker가 없는 stage output은 자동 삭제하거나 재실행하지 않고 보존한 채 중단합니다.

Water count를 위한 first-pass LEaP input과 `solvated.pdb`는 `work/.build_tmp.XXXXXX/`에서 생성합니다. 전체 build가 성공하면 temporary directory를 삭제하고, 실패하면 진단을 위해 경로를 출력하고 보존합니다. Final PDB, topology, restart, resolved config와 LEaP log는 유지합니다. REST build의 preprocessing TPR, processed topology와 energy-check raw file도 같은 temporary directory에 둡니다. 성공 후에는 `work/topol.top`, `work/system.gro`, replica topology, `work/build.log`, `work/build_summary.toml`과 `work/energy_check.tsv`를 남깁니다. `./build.sh --keep-intermediates INPUT.pdb`를 사용하면 성공 후에도 temporary directory를 보존합니다. Replica는 공통 `work/system.gro`를 직접 참조합니다. 실제 minimization, equilibration, production TPR·`*.grompp.log`와 restart는 정리하지 않습니다.

이 directory의 runtime code는 별도로 복사해 사용할 수 있습니다. GROMACS를
build할 때는 상위 `patches/` directory의 correction도 함께 사용합니다. Python
dependency는 복사한 directory의 `requirements.txt`를 사용해 설치합니다.

Water와 ion을 제외한 solute 전체를 tempered region으로 사용합니다. Temperature
predictor에는 solute atom 수와 water 0을 전달하고, 생성한 effective temperature
`T_i`에서 `lambda_pp=T_0/T_i`, `lambda_pw=sqrt(lambda_pp)`를 계산합니다.

```bash
./download.sh 1UBQ
./build.sh structure/1UBQ.pdb
replicas=$(awk 'NR > 1 {count++} END {print count + 0}' work/states.tsv)
./run.sh --cpus "$replicas" --gpus 1
```

Production에는 PLUMED 2.10이 patch된 GROMACS 2024.3/2024.6 external-MPI build와
상위 directory의
[`HREX_WORKLOAD_FIX_1` correction](../patches/gromacs-2024.3-plumed-2.10-hrex-energy.patch)이
필요합니다. 적용 순서와 검증 범위는 [상위 README](../README.md)에 있습니다.
`run.sh`는 시작 전에 이 marker와 `-hrex` 지원을 검사합니다. Predictor의 목표
probability는 실제 HREX acceptance를 보장하지 않으므로 짧은 pilot run에서
`Repl average probabilities`를 확인합니다.
각 replica는 tutorial과 같이 minimization 뒤 300 K velocity를 생성하는 NPT
equilibration을 실행합니다. 별도 heating stage는 두지 않습니다. Build는
scale 1 topology와 원본 topology의 single-frame potential energy 차이가
0.1 kJ/mol 이하인지도 검사합니다. 첫 `grompp` 전에는 ParmEd가 출력한 긴
CMAP 실수를 GROMACS 2024.x가 읽을 수 있는 정밀도로 정규화합니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `tempered_region` | `solute`만 지원 | `solute` | Water와 ion을 제외한 전체 solute를 tempering합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Replica equilibration에 적용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | GROMACS production pressure coupling을 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 LINCS를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | State별 seed를 무작위로 만들거나 정수에서 파생합니다. |

| `temperature_mode` | 사용하는 설정 | 무시하는 설정 | 생성 결과 |
| --- | --- | --- | --- |
| `auto` (기본값) | `minimum_temperature`, `maximum_temperature`, `target_exchange_probability`, `generator_tolerance` | `temperature_file` | Tempered solute atom 수와 water 0으로 ladder를 계산합니다. |
| `file` | `temperature_file` | Auto ladder 설정 | File temperature에서 `lambda_pp=T0/T`, `lambda_pw=sqrt(lambda_pp)`를 계산합니다. |

Temperature file은 사용자가 생성해야 합니다. 구분자는 공백, comma, semicolon,
`|`이며 `#` 뒤는 comment입니다. 값은 양수이고 중복 없이 오름차순이어야 하며,
둘 이상이어야 하고 첫 값은 `run.temperature`와 같아야 합니다. 적용된 temperature,
λ와 seed는 `work/states.tsv`에 기록됩니다.

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


Scale-one energy 비교에는 finite energy와 finite tolerance가 필요합니다. Tolerance는 0 이상의 kJ/mol 값입니다. NaN/Inf energy, overflow한 차이 또는 잘못된 tolerance는 검증 실패이며 기존 비교 output을 교체하지 않습니다.

### Salt와 charge 기록

Temperature predictor와 topology 검사는 NaCl, KCl, MgCl2, CaCl2의 실제 ion residue 이름을 같은 기준으로 분류합니다. REST2 hot marker는 water와 이 ion을 제외합니다. REST3 verifier는 각 cation/anion과 water의 interaction 보존을 검사합니다.

`build_summary.toml`은 `System has non-zero total charge` 문구의 값을 `total_charge_e`에 기록합니다. Log에 charge 값이 없으면 `total_charge_known=false`로 표시하고 값을 0으로 추정하지 않습니다. Log가 누락되면 summary 생성을 중단합니다.

### Production checkpoint continuation

첫 production segment는 equilibration의 coordinate/velocity를 `grompp -t`로 읽고
새 production 계산을 시작합니다. 두 번째부터는 predecessor checkpoint를
`mdrun -cpi`에도 전달해 thermostat/barostat와 전체 MD state를 이어받습니다.
`helpers/production_segment.py`가 자동 호출되어 predecessor의 step/time/part를
검사하고, 원본 `production.mdp`에서 누적 `init-step`을 가진
`production.NNN.mdp`를 생성합니다. 기존 파생 input은 내용이 같을 때만 재사용합니다.

각 후속 segment는 `-noappend`로 독립 output을 생성합니다. Engine의
`production.NNN.partMMMM.*`는 모든 요청 step이 완료된 checkpoint를 확인한 뒤
`production.NNN.*`로 옮깁니다. `.cpt` 이름은 바꾸지 않습니다. 다음 segment도
`-noappend`를 사용하므로 checkpoint에 기록된 원래 part output의 이름과 checksum을
수정하지 않습니다. Trajectory는 이 canonical `.xtc` 경로에서 읽습니다.

Exit 0이어도 checkpoint가 요청한 마지막 step/time에 도달하지 않았으면 완료 marker를
만들지 않습니다. 실패 뒤 canonical 또는 part output이 남으면 보존하고 재실행을
거부합니다. 이전 runner의 후속 segment가 time을 다시 시작했거나 checkpoint part가
맞지 않으면 새 `WORK_DIR`에서 시작합니다. 과거 결과나 identity를 자동 복구하지 않습니다.

실제 GROMACS 2024.3의 단일 replica CPU 계산에서 segment helper의 누적 step/time,
part output 이름과 기존 파일 보존을 확인했습니다. 공개 runner의 MPI HREX/GPU
continuation은 미검증입니다. Runner가 GPU ID를 전달하므로 CPU-only 환경에서는
실행되지 않습니다.

## English

Only even replica counts of at least two are supported. `build.sh` and `run.sh` reject odd schedules without adjusting them. `run.sh --dry-run` checks the actual state-table count too. Prepare a new work directory for results built with an odd schedule.

File schedules are checked before LEaP. Auto counts are checked after running the predictor on a temporary topology; only preparation with a valid count is copied to the work directory. Odd results preserve existing inputs, states and logs and retain temporary diagnostics. `build.sh --dry-run` validates files but defers auto-count validation until an actual build. The predictor algorithm, temperature range and target probability are not adjusted automatically.

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
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `tempered_region` | `solute` only | `solute` | Tempers the complete non-water, non-ion solute. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to replica equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Selects GROMACS production pressure coupling. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies LINCS to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | Creates random state seeds or derives them from the integer. |

| `temperature_mode` | Settings used | Settings ignored | Result |
| --- | --- | --- | --- |
| `auto` (default) | `minimum_temperature`, `maximum_temperature`, `target_exchange_probability`, `generator_tolerance` | `temperature_file` | Predicts the ladder from tempered-solute atoms and zero waters. |
| `file` | `temperature_file` | Auto-ladder settings | Computes `lambda_pp=T0/T` and `lambda_pw=sqrt(lambda_pp)` from the file temperatures. |

The user must create the temperature file. It accepts whitespace, commas,
semicolons, and `|` as separators; text after `#` is a comment. It must contain
at least two unique, increasing positive values, and its first value must equal
`run.temperature`. Applied temperatures, λ values, and seeds are written to
`work/states.tsv`.

This directory's runtime code can be copied on its own. Keep the parent
`patches/` correction available when building GROMACS. Install the Python
dependencies from the local `requirements.txt` after copying it.

The complete non-water, non-ion solute is the tempered region. The offline
predictor receives the solute atom count and zero waters, then the build derives
`lambda_pp=T_0/T_i` and `lambda_pw=sqrt(lambda_pp)` for every effective
temperature. Production requires the patched PLUMED 2.10 HREX integration and
the [`HREX_WORKLOAD_FIX_1` correction](../patches/gromacs-2024.3-plumed-2.10-hrex-energy.patch).
See the [parent README](../README.md) for application steps and validation
scope. Preproduction follows the
tutorial's minimization-to-NPT-equilibration sequence, and the build checks
scale-one energy identity with a 0.1 kJ/mol tolerance. Before the first
`grompp`, it normalizes long ParmEd-formatted CMAP numbers to a precision
accepted by GROMACS 2024.x.

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

The scale-one energy comparison requires finite energies and a finite, nonnegative tolerance in kJ/mol. Nonfinite energy, an overflowed difference, or invalid tolerance fails validation without replacing existing comparison output.

### Salt and charge records

The temperature predictor and topology checks use consistent residue names for NaCl, KCl, MgCl2, and CaCl2. The REST2 hot marker excludes water and these ions. REST3 verification checks preservation of every cation/anion interaction with water.

`build_summary.toml` records the value reported by `System has non-zero total charge` as `total_charge_e`. If the log contains no charge value, it records `total_charge_known=false` and omits the numeric value. Missing logs stop summary generation.

### Production checkpoint continuation

The first production segment reads equilibration coordinates and velocities with
`grompp -t` and starts a new production stage. From the second segment onward,
`mdrun -cpi` also restores the predecessor checkpoint's full MD state, including
thermostat/barostat state. The runner automatically calls
`helpers/production_segment.py` to check predecessor step/time/part and derive
`production.NNN.mdp` with cumulative `init-step` from the original `production.mdp`.
An existing derived input is reused only when its content matches.

Each continuation uses `-noappend` for separate outputs. After checking that the
checkpoint reached the requested final step/time, the runner moves
`production.NNN.partMMMM.*` to the canonical `production.NNN.*` names. The `.cpt`
name is unchanged. Subsequent segments also use `-noappend`, so checkpoint-recorded
part output names and checksums remain intact. Read trajectories from the canonical
`.xtc` paths.

Exit 0 alone does not create a completion marker when the checkpoint ends early.
Canonical or part outputs left by failure are retained and prevent rerunning that
stage. Use a new `WORK_DIR` if an older runner's continuation reset time or has an
incompatible checkpoint part. Old results and identities are not repaired automatically.
The segment helper was checked with actual single-replica GROMACS 2024.3 CPU runs
for cumulative step/time, part output names, and preservation of existing files.
Public-runner MPI HREX/GPU continuation remains unverified. The runner passes GPU
IDs and cannot run in a CPU-only environment.

### Schedule file 검사 / Schedule file checks

Temperature file에는 finite 값만 사용합니다. `nan`, `inf`,
`-inf`와 float 범위를 넘는 값은 거부합니다. `build.sh`는 topology, raw PDB 사본,
engine input과 build log를 저장하기 전에 검사하며, 오류에 해당 file 경로를 표시합니다.
내부 input generator의 `--validate-only`는 이 preflight에 자동으로 사용됩니다.
Temperature 순서·양수 조건은 기존 조건을 따릅니다.

Temperature files accept only finite values. `nan`, `inf`,
`-inf`, and values outside the float range are rejected. `build.sh` checks them
before saving topology, the raw PDB copy, engine inputs, or build logs, and reports
the offending file path. The internal input generator's `--validate-only` option
is called automatically for this preflight. Existing temperature ordering,
and positivity still apply.
