# ABFE template

## 한국어

사용자가 직접 실행하는 파일은 이 directory의 root에 있습니다. `helpers/`는 `build.sh`, `run.sh` 또는 `anal.py`가 자동 호출하는 leaf-local 내부 code입니다. `helpers/result_generation.py`는 외부 consumer에서 결과를 읽기 전 별도로 검사할 때도 사용합니다.

중단되거나 marker가 없는 stage output은 자동 삭제하거나 재실행하지 않고 보존한 채 중단합니다.

Water count를 위한 first-pass LEaP input과 `solvated.pdb`는 `work/.build_tmp.XXXXXX/`에서 생성합니다. 전체 build가 성공하면 temporary directory를 삭제하고, 실패하면 진단을 위해 경로를 출력하고 보존합니다. Final PDB, topology, restart, resolved config와 LEaP log는 유지합니다.

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

Ligand restraint coupling, complex/solvent charge decoupling과 vdW decoupling을
포함하는 double-decoupling ABFE window를 만듭니다. `build.sh`에는 ligand가
포함된 reviewed complex PDB를 전달하며, 같은 residue name과 atom name을 가진
precharged MOL2와 frcmod를 config에서 지정합니다.

```bash
./build.sh prepared_complex.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

세 protein anchor와 세 ligand anchor는 각각 정확히 한 atom을 선택해야 하며 서로
달라야 합니다. Build는 초기 구조에서 1 distance, 2 angle, 3 torsion reference를
계산합니다. Restraint/charge는 11-state schedule, vdW는 16-state schedule을
사용해 총 65개 window를 만듭니다. 기본 force constant는 distance 5
kcal/mol/Å², angle/torsion 100 kcal/mol/rad²이고 standard state는 1 M, 300 K입니다.

각 window production은 10,000,000 steps이며 `bar_intervall=5000`으로 MBAR
energy를 기록합니다. Partial production은 자동으로 덮어쓰지 않습니다.
`download.sh PDB_ID`는 optional source complex를 내려받습니다. `build.sh`는
double-decoupling system과 65개 window를 만들고, `run.sh`는 stage를 실행하며,
`anal.py`는 FE-ToolKit의 `edgembar-amber2dats.py`와 `edgembar`를 사용해
restraint correction과 각 alchemical contribution을 합산합니다.

Neutral ligand만 지원합니다. `build.ligand_net_charge`는 정수 0이어야 하며,
MOL2 charge 합은 이 값과 0.01 e 이내로 일치해야 합니다. Build와 dry-run은
output을 복사하거나 생성하기 전에 ParmEd로 이를 확인합니다. 과거 charged config도
input 생성, run과 analysis에서 거부합니다. Summary의
`leading_pme_net_charge_correction`은 0과 `not_applicable_neutral_ligand`를 기록하며,
charged correction을 계산한 값이 아닙니다.

### Config 선택값

| Option | 현재 지원값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `ligand_force_field` | `GAFF2`만 지원 | `GAFF2` | Ligand parameter 형식을 결정합니다. |
| `charge_method` | precharged `RESP` MOL2만 지원 | `RESP` | MOL2의 RESP charge를 그대로 사용합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Complex와 solvent leg의 water model을 선택합니다. |
| `box_shape` | `rectangular`만 실제 적용 | `rectangular` | FEP builder는 두 leg에 `solvatebox`를 사용합니다. |
| `salt_type` | `NaCl`만 실제 적용 | `NaCl` | FEP builder는 `Na+`와 `Cl-`를 기록합니다. |
| `equilibration_ensemble` | `NVT`, `NPT` | `NPT` | Generated equilibration input의 `ntb`와 `ntp`를 설정합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Generated production input의 `ntb`와 `ntp`를 설정합니다. |
| `random_seed` | 현재 config override 미적용 | `"random"` | Window seed는 global state index에서 결정됩니다. |

`restraint_lambdas`, `charge_lambdas`, `vdw_lambdas`는 0.0과 1.0을 포함하는
중복 없는 오름차순 list를 직접 지정합니다. Auto/file mode는 없으며 각 값이
해당 leg의 한 window가 되어 `work/states.tsv`에 기록됩니다.
`production_segments`는 현재 `1`만 지원합니다.

### Engine 선택과 실행 상태

`AMBER_ENGINE`이 설정되어 있으면 이를 사용하며, 없으면 build가 기록한 `work/resolved_config.toml`의 `run.engine`을 읽습니다. 허용하는 executable 이름은 `pmemd.cuda`이며 설치 경로를 지정할 수 있습니다. 빈 override, 누락된 engine 설정과 지원하지 않는 executable은 기본값으로 대체하지 않고 error로 중단합니다. Runner가 `helpers/config_utils.py`를 자동 호출해 이 설정을 읽습니다.

Build는 기존 topology/restart file이 있으면 input을 변경하기 전에 중단하고 파일을 보존합니다. 새 build에는 별도 `WORK_DIR`을 지정합니다.

빈 output도 기존 파일로 취급합니다. Completion marker와 필수 nonempty output이 모두 있어야 단계를 건너뛰며, partial output은 자동으로 덮어쓰지 않습니다.

### 동시 실행과 input 변경

Build는 work tree 전체를 보호합니다. Run은 states/config를 읽고 선택된 environment/leg/window에만 write scope를 등록하므로 서로 독립적인 window를 동시에 실행할 수 있습니다.
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


### Analysis 결과 저장

`anal.py`는 새 extracted energy, report와 최종 TSV를 temporary generation에서
계산합니다. Extraction, estimator, TSV 또는 HTML 생성이 실패하면 기존
`mbar/`, `free_energy.tsv`, `mbar_diagnostics.tsv`, `overlap_matrix.tsv`를 유지합니다.
실패한 command의 최근 log 내용은 stderr에 출력합니다.

자동 호출되는 `helpers/result_generation.py`가 이 파일들을 검증하고 게시합니다.
완료 기록은 `work/.analysis-generation.json`입니다. 여러 파일의 게시 도중
중단되면 `work/.analysis.pending`이 consumer와 재실행을 차단합니다. 실행 process가
종료됐는지 확인한 뒤 marker에 적힌 previous/new directory를 보존하고 검사합니다.
Marker만 삭제하거나 파일을 개별적으로 섞지 않습니다.

외부 script에서 결과를 읽기 전에는 다음 검사를 사용합니다. 별도 `WORK_DIR`을
사용했다면 `work`를 그 경로로 바꿉니다.

```bash
python3 helpers/result_generation.py work
```

공개 analysis entry는 자동으로 `helpers/writer_guard.py`를 호출해 같은 output의 동시 writer를 거부합니다. Engine 실행부터 결과 게시까지 보호하며, signal 종료 시 child가 멈춘 뒤 lock을 해제합니다. Lock을 임의로 삭제해 실행을 재개하지 않습니다.

## English

User-facing entry points remain in this directory root. `helpers/` contains leaf-local internal code called automatically by `build.sh`, `run.sh`, or `anal.py`; `helpers/result_generation.py` also supports a separate integrity check before an external consumer reads results.

Interrupted or unmarked stage output is retained and stops the workflow instead of being deleted or rerun automatically.

The first-pass LEaP input and water-count `solvated.pdb` are created under `work/.build_tmp.XXXXXX/`. A successful build removes that temporary directory; a failed build prints and retains it for diagnosis. Final PDB, topology, restart, resolved config, and LEaP logs are retained.

### Config choices

| Option | Current support | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `ligand_force_field` | `GAFF2` only | `GAFF2` | Selects the ligand parameter format. |
| `charge_method` | Precharged `RESP` MOL2 only | `RESP` | Uses the RESP charges already present in the MOL2 file. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects the water model for complex and solvent legs. |
| `box_shape` | Only `rectangular` is applied | `rectangular` | The FEP builder uses `solvatebox` for both legs. |
| `salt_type` | Only `NaCl` is applied | `NaCl` | The FEP builder writes `Na+` and `Cl-`. |
| `equilibration_ensemble` | `NVT`, `NPT` | `NPT` | Sets `ntb` and `ntp` in generated equilibration input. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Sets `ntb` and `ntp` in generated production input. |
| `random_seed` | Config override is not currently applied | `"random"` | Window seeds are derived from the global state index. |

`restraint_lambdas`, `charge_lambdas`, and `vdw_lambdas` are explicit, unique,
increasing lists spanning 0.0 to 1.0. They have no auto/file mode. Each value
creates one window in the corresponding leg and is recorded in
`work/states.tsv`. `production_segments` currently supports only `1`.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

This double-decoupling ABFE template includes restraint coupling and charge/vdW
decoupling in complex and solvent environments. Pass a reviewed complex PDB and
configure a matching precharged ligand MOL2/frcmod plus six distinct one-atom
anchor masks. The build creates 65 windows: 11 restraint, 22 charge, and 32 vdW
states. Each window runs 10,000,000 production steps and records MBAR energies
every 5,000 steps. `download.sh` can retrieve a source complex, `build.sh`
creates the double-decoupling systems and windows, `run.sh` executes them, and
`anal.py` combines the alchemical terms and restraint correction. Partial
production is preserved. FE-ToolKit `edgembar-amber2dats.py` and `edgembar`
must be available on `PATH` for analysis.

Only neutral ligands are supported. `build.ligand_net_charge` must be integer
zero, and the MOL2 charge sum must match within 0.01 e. Build and dry-run check
this before copying or generating outputs; ParmEd is required for this check.
Legacy charged configs are also rejected by input generation, run and analysis.
The summary records zero and `not_applicable_neutral_ligand` for
`leading_pme_net_charge_correction`; this is not a calculated charged correction.

### Engine selection and run state

`AMBER_ENGINE` overrides `run.engine` in the build-generated `work/resolved_config.toml`. Accepted executable names are `pmemd.cuda`; installation paths are accepted. Empty overrides, missing engine settings and unsupported executables fail instead of falling back to a default. The runner invokes `helpers/config_utils.py` automatically to read this setting.

Build stops before changing inputs when topology/restart files already exist, preserving those files. Use a separate `WORK_DIR` for a new build.

Empty outputs also count as existing files. A stage is skipped only when its completion marker and all required nonempty outputs exist; partial outputs are not overwritten automatically.

### Concurrent runs and input changes

Build protects the whole work tree. Run registers shared reads of states/config and writes only to selected environment/leg/window paths, allowing independent windows to run concurrently.
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

### Analysis result storage

`anal.py` calculates new extracted energies, reports, and final TSV files in a
temporary generation. Extraction, estimation, TSV, or HTML failure preserves
the previous `mbar/`, `free_energy.tsv`, `mbar_diagnostics.tsv`, and
`overlap_matrix.tsv`. Recent failed-command log lines are printed to stderr.

The automatically called `helpers/result_generation.py` validates and publishes
this group, recording completion in `work/.analysis-generation.json`. If multiple
file publication is interrupted, `work/.analysis.pending` blocks consumers and
reruns. Check that the process has ended, then preserve and inspect the
previous/new directories listed there. Do not remove only the marker or mix
individual files.

Before reading results in an external script, run the check below. Replace
`work` with your `WORK_DIR` if using another directory.

```bash
python3 helpers/result_generation.py work
```

Public analysis entries automatically use `helpers/writer_guard.py` to reject concurrent writers to the same output. Protection covers engine execution through publication, and signal cleanup drains children before releasing the lock. Do not delete a lock to force a retry.
