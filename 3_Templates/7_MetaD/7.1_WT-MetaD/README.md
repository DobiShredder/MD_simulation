# WT-MetaD template

## 한국어

사용자가 직접 실행하는 파일은 이 directory의 root에 있습니다. `helpers/`는 `build.sh`, `run.sh` 또는 `anal.py`가 자동 호출하는 leaf-local 내부 code이며 직접 실행하지 않습니다.

중단되거나 marker가 없는 stage output은 자동 삭제하거나 재실행하지 않고 보존한 채 중단합니다.

Water count를 위한 first-pass LEaP input과 `solvated.pdb`는 `work/.build_tmp.XXXXXX/`에서 생성합니다. 전체 build가 성공하면 temporary directory를 삭제하고, 실패하면 진단을 위해 경로를 출력하고 보존합니다. Final PDB, topology, restart, resolved config와 LEaP log는 유지합니다.

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Conventional equilibration에 적용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | WT-MetaD production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | `"random"`은 AMBER `ig=-1`, 정수는 고정 seed를 사용합니다. |

WT-MetaD 방식은 이 directory에서 고정되며 별도 config mode가 아닙니다.

`cv.dat`에 정의한 CV를 방문할 때마다 Gaussian hill을 추가합니다. 이미 bias가
쌓인 위치에서는 `BIASFACTOR=10`에 따라 새 hill이 작아져 conventional MetaD보다
완만하게 free-energy surface를 채웁니다.

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

`config.toml`의 `collective_variable.arguments`는 `cv.dat`의 label과 같아야 합니다.
기본 φ/ψ atom 번호는 capped alanine 예시이므로 topology에 맞게 바꿉니다.
`sigma`, `grid_min`, `grid_max`와 `grid_bins`는 CV 수와 같은 길이여야 합니다.
기본 hill은 1.2 kJ/mol, `PACE=500`, `BIASFACTOR=10`입니다.

`build.sh`는 configured protein/water topology와 preproduction input을 만듭니다. `run.sh`는
500 ps heating과 1 ns NPT equilibration 뒤 10×10 ns production을 실행합니다.
첫 segment는 새 `HILLS`를 만들고 이후 segment는 `RESTART`로 같은 file에
추가합니다. Partial production segment는 자동 삭제하지 않습니다.
`download.sh PDB_ID`는 optional source PDB를 수정하지 않고 내려받습니다.

`anal.py`는 모든 segment의 누적 `COLVAR`와 `HILLS`를 읽습니다. 기본적으로
`plumed sum_hills`를 실행하며 `--skip-fes`로 diagnostic TSV만 만들 수 있습니다.
PLUMED의 기본 unit인 energy kJ/mol, length nm, time ps를 사용합니다.

### Engine 선택과 실행 상태

`AMBER_ENGINE`이 설정되어 있으면 이를 사용하며, 없으면 build가 기록한 `work/resolved_config.toml`의 `run.engine`을 읽습니다. 허용하는 executable 이름은 `pmemd.cuda`, `pmemd`, `sander`이며 설치 경로를 지정할 수 있습니다. Build 전 dry-run에 한해서 resolved config가 없으면 `config.toml`을 읽습니다. PLUMED 연동이 가능한 AMBER build가 필요합니다. 빈 override, 누락된 engine 설정과 지원하지 않는 executable은 기본값으로 대체하지 않고 error로 중단합니다. Runner가 `helpers/config_utils.py`를 자동 호출해 이 설정을 읽습니다.

Build는 기존 topology/restart file이 있으면 input을 변경하기 전에 중단하고 파일을 보존합니다. 새 build에는 별도 `WORK_DIR`을 지정합니다.

다운로드는 임시 파일의 PDB atom record를 확인한 뒤 최종 파일로 교체합니다. 실패하면 기존 PDB를 보존하고 임시 파일을 정리합니다.

빈 output도 기존 파일로 취급합니다. Completion marker와 필수 nonempty output이 모두 있어야 단계를 건너뛰며, partial output은 자동으로 덮어쓰지 않습니다.

### 동시 실행과 input 변경

Build와 run은 같은 work tree에 동시에 쓸 수 없습니다. 서로 다른 `WORK_DIR`은 독립 실행을 허용합니다.
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

처음 numbered layout으로 실행했다면 segment 수를 줄여도 첫 output은 `work/001/`에 유지합니다. 한 segment를 root `work/production.*`로 완료한 뒤 segment 수를 늘렸다면 첫 output은 그대로 두고 후속 output만 `work/002/`, `work/003/`에 생성합니다. 처음부터 여러 segment를 실행하면 `work/001/`부터 생성합니다.


### Analysis 결과 저장

`anal.py`는 diagnostic TSV와 새 FES를 별도 temporary generation에서 만들고
확인한 뒤 `work/analysis/`을 교체합니다. `sum_hills`가 exit 0을 반환해도
새 `fes.dat`이 없거나 비어 있으면 실패로 처리하고 이전 결과를 유지합니다.
`--skip-fes`의 새 결과에는 과거 FES를 포함하지 않습니다.

자동 호출되는 `helpers/result_generation.py`가 완료한 output hash를
`analysis/.generation.json`에 기록합니다. 게시가 중단되어
`work/.analysis.pending`이 남으면 재실행을 거부합니다. 실행 process가 종료됐는지
확인한 뒤 marker의 previous/new directory를 보존하고 검사합니다.

## English

User-facing entry points remain in this directory root. `helpers/` contains leaf-local internal code called automatically by `build.sh`, `run.sh`, or `anal.py`; it is not a separate entry point.

Interrupted or unmarked stage output is retained and stops the workflow instead of being deleted or rerun automatically.

The first-pass LEaP input and water-count `solvated.pdb` are created under `work/.build_tmp.XXXXXX/`. A successful build removes that temporary directory; a failed build prints and retains it for diagnosis. Final PDB, topology, restart, resolved config, and LEaP logs are retained.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to conventional equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Sets WT-MetaD production `ntb` and `ntp`. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | `"random"` maps to AMBER `ig=-1`; an integer fixes the seed. |

The WT-MetaD method is fixed by this directory and is not a separate config
mode.

WT-MetaD deposits Gaussian hills along the CVs defined in `cv.dat`. The current
bias reduces subsequent hill heights through `BIASFACTOR=10`. CV labels in
`collective_variable.arguments` must match `cv.dat`; the supplied φ/ψ atom
numbers are only a capped-alanine example.

The defaults use 1.2 kJ/mol hills every 500 steps and ten 10 ns segments. The
first segment creates `HILLS`; later segments use `RESTART` and append to the
same bias history. Analysis summarizes the cumulative `COLVAR` and runs
`plumed sum_hills` unless `--skip-fes` is selected. `download.sh` can retrieve
an unmodified source PDB, while `build.sh`, `run.sh`, and `anal.py` create,
propagate, and analyze the configured workflow.

### Engine selection and run state

`AMBER_ENGINE` overrides `run.engine` in the build-generated `work/resolved_config.toml`. Accepted executable names are `pmemd.cuda`, `pmemd`, `sander`; installation paths are accepted. Before build, dry-run alone may read `config.toml` when the resolved file is absent. An AMBER build with the required PLUMED integration is still needed. Empty overrides, missing engine settings and unsupported executables fail instead of falling back to a default. The runner invokes `helpers/config_utils.py` automatically to read this setting.

Build stops before changing inputs when topology/restart files already exist, preserving those files. Use a separate `WORK_DIR` for a new build.

Downloads replace the final PDB only after validating atom records in a temporary file. Failure preserves the existing PDB and removes the temporary file.

Empty outputs also count as existing files. A stage is skipped only when its completion marker and all required nonempty outputs exist; partial outputs are not overwritten automatically.

### Concurrent runs and input changes

If the first run used numbered directories, reducing the count retains the first output under `work/001/`.

Build and run cannot write the same work tree concurrently. Separate `WORK_DIR` trees can run independently.
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

If one segment completed as `work/production.*`, increasing the segment count retains that first output and writes later outputs under `work/002/`, `work/003/`, etc. Runs configured with multiple segments from the start use `work/001/` onward.

### Analysis result storage

`anal.py` creates diagnostic TSV files and a fresh FES in a separate temporary
generation before replacing `work/analysis/`. An exit-zero `sum_hills` that
creates no nonempty `fes.dat` is a failure and preserves previous results.
A new `--skip-fes` generation does not retain the old FES.

The automatically called `helpers/result_generation.py` records output hashes
in `analysis/.generation.json`. Interrupted publication leaves
`work/.analysis.pending` and blocks reruns. Check that the process has ended,
then preserve and inspect the previous/new directories listed in the marker.
