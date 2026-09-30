# OPES_METAD template

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
| `production_ensemble` | `NVT`, `NPT` | `NPT` | OPES_METAD production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | `"random"`은 AMBER `ig=-1`, 정수는 고정 seed를 사용합니다. |

OPES_METAD 방식은 이 directory에서 고정되며 별도 config mode가 아닙니다.

OPES_METAD는 방문한 위치에 hill을 그대로 누적하지 않습니다. CV sample로
probability distribution을 추정하고 target distribution에 필요한 bias를
갱신합니다. `KERNELS`는 압축된 distribution estimate이고 `opes.state`는 restart에
필요한 adaptive state입니다.

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

`cv.dat`의 label과 `collective_variable.arguments`를 함께 수정합니다. 기본
alanine φ/ψ atom 번호는 다른 topology에 적용하지 않습니다. 기본값은
`BARRIER=50 kJ/mol`, `PACE=500`, sigma 0.15 rad이며 CV별 sigma가 필요합니다.

100 ns production은 10 segments로 나뉩니다. 첫 segment가 `KERNELS`와
`opes.state`를 만들고, 이후 segment는 `RESTART`와 `STATE_RFILE`로 두 state를
이어받습니다. Root `COLVAR`도 append됩니다. State file이 하나라도 없으면 다음
segment를 시작하지 않습니다.

`anal.py`는 CV와 bias 범위, final effective sample 수와 kernel 수를 기록합니다.
이 값은 convergence 판정 자체가 아니며 CV coverage와 독립 run을 함께 봅니다.
`download.sh PDB_ID`는 optional source PDB를 내려받습니다. `build.sh`는 topology와
PLUMED input을 만들고 `run.sh`는 `opes.state`를 이어받아 segmented production을
실행합니다.

### Engine 선택과 실행 상태

`AMBER_ENGINE`이 설정되어 있으면 이를 사용하며, 없으면 build가 기록한 `work/resolved_config.toml`의 `run.engine`을 읽습니다. 허용하는 executable 이름은 `pmemd.cuda`, `pmemd`, `sander`이며 설치 경로를 지정할 수 있습니다. Build 전 dry-run에 한해서 resolved config가 없으면 `config.toml`을 읽습니다. PLUMED 연동이 가능한 AMBER build가 필요합니다. 빈 override, 누락된 engine 설정과 지원하지 않는 executable은 기본값으로 대체하지 않고 error로 중단합니다. Runner가 `helpers/config_utils.py`를 자동 호출해 이 설정을 읽습니다.

Build는 기존 topology/restart file이 있으면 input을 변경하기 전에 중단하고 파일을 보존합니다. 새 build에는 별도 `WORK_DIR`을 지정합니다.

다운로드는 임시 파일의 PDB atom record를 확인한 뒤 최종 파일로 교체합니다. 실패하면 기존 PDB를 보존하고 임시 파일을 정리합니다.

빈 output도 기존 파일로 취급합니다. Completion marker와 필수 nonempty output이 모두 있어야 단계를 건너뛰며, partial output은 자동으로 덮어쓰지 않습니다.

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
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Sets OPES_METAD production `ntb` and `ntp`. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | `"random"` maps to AMBER `ig=-1`; an integer fixes the seed. |

The OPES_METAD method is fixed by this directory and is not a separate config
mode.

OPES_METAD estimates the sampled CV distribution and updates the bias needed
for a target distribution instead of directly accumulating MetaD hills.
`KERNELS` stores the compressed estimate and `opes.state` stores restartable
adaptive state.

CV labels must match `cv.dat`; the supplied alanine atom numbers are examples.
Defaults are a 50 kJ/mol barrier, 500-step pace, and 0.15 rad sigma per CV. Ten
segments share root-level `KERNELS`, `opes.state`, and `COLVAR`; continuations
use both `RESTART` and `STATE_RFILE`. `download.sh` retrieves an optional source
PDB, while `build.sh`, `run.sh`, and `anal.py` create, propagate, and analyze
the configured workflow.

### Engine selection and run state

`AMBER_ENGINE` overrides `run.engine` in the build-generated `work/resolved_config.toml`. Accepted executable names are `pmemd.cuda`, `pmemd`, `sander`; installation paths are accepted. Before build, dry-run alone may read `config.toml` when the resolved file is absent. An AMBER build with the required PLUMED integration is still needed. Empty overrides, missing engine settings and unsupported executables fail instead of falling back to a default. The runner invokes `helpers/config_utils.py` automatically to read this setting.

Build stops before changing inputs when topology/restart files already exist, preserving those files. Use a separate `WORK_DIR` for a new build.

Downloads replace the final PDB only after validating atom records in a temporary file. Failure preserves the existing PDB and removes the temporary file.

Empty outputs also count as existing files. A stage is skipped only when its completion marker and all required nonempty outputs exist; partial outputs are not overwritten automatically.
