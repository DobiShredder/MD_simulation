# OPES_EXPANDED multithermal template

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
| `production_ensemble` | `NVT`, `NPT` | `NVT` | OPES_EXPANDED production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | `"random"`은 AMBER `ig=-1`, 정수는 고정 seed를 사용합니다. |

OPES_EXPANDED 방식은 이 directory에서 고정되며 별도 config mode가 아닙니다.

Potential energy `ene`에서 300–500 K multithermal target을 만들고
OPES_EXPANDED가 temperature state의 free-energy offset을 학습합니다. 물리적인 MD
temperature는 300 K이며, bias를 통해 설정 범위의 energy fluctuation을 sampling합니다.

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

`minimum_temperature`와 `maximum_temperature`는 base temperature를
포함해야 합니다. 기본 `PACE=500`이며 state grid는 `ECV_MULTITHERMAL`이 자동으로
만듭니다. 기본 config는 NPT equilibration 뒤 box를 고정한 NVT production을
실행합니다.

첫 segment는 `DELTAFS`와 `opes.state`를 만들고 이후 segment는 `RESTART`와
`STATE_RFILE=opes.state`로 이어받습니다. PLUMED 2.10은 어느 file에서도 restart할
수 있지만, 이 template는 readable checkpoint인 `opes.state`를 continuation의
단일 기준으로 사용하고 `DELTAFS`는 state별 free-energy estimate와 분석용으로
보존합니다. `anal.py`는 energy, expanded CV, bias 범위와 생성된 state 수를
기록합니다.

이 template는 multithermal expansion입니다. Hamiltonian expansion을 사용하려면
Hamiltonian state 정의와 engine coupling을 별도로 구성해야 합니다.
`download.sh PDB_ID`는 optional source PDB를 내려받습니다. `build.sh`는 NPT
equilibration과 NVT expanded-ensemble input을 만들고, `run.sh`는 state를 이어받아
segment를 실행하며, `anal.py`는 누적 output을 요약합니다.

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
| `production_ensemble` | `NVT`, `NPT` | `NVT` | Sets OPES_EXPANDED production `ntb` and `ntp`. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | `"random"` maps to AMBER `ig=-1`; an integer fixes the seed. |

The OPES_EXPANDED method is fixed by this directory and is not a separate
config mode.

This template constructs a 300–500 K multithermal target from potential energy.
The physical MD thermostat remains at 300 K while OPES_EXPANDED learns
temperature-state free-energy offsets and biases energy fluctuations. By
default, NPT equilibration is followed by fixed-volume NVT production.

The configured range must contain the base temperature. The first segment
creates `DELTAFS` and `opes.state`. PLUMED 2.10 can restart from either file;
this template consistently reads the readable `opes.state` checkpoint and
retains `DELTAFS` for state free-energy estimates and analysis. Analysis reports
energy, expanded-CV and bias ranges plus the generated state count. Hamiltonian
expansion requires a separate Hamiltonian-state definition and coupling setup.
`download.sh`, `build.sh`, `run.sh`, and `anal.py` retrieve, generate,
propagate, and summarize the configured workflow, respectively.

### Engine selection and run state

`AMBER_ENGINE` overrides `run.engine` in the build-generated `work/resolved_config.toml`. Accepted executable names are `pmemd.cuda`, `pmemd`, `sander`; installation paths are accepted. Before build, dry-run alone may read `config.toml` when the resolved file is absent. An AMBER build with the required PLUMED integration is still needed. Empty overrides, missing engine settings and unsupported executables fail instead of falling back to a default. The runner invokes `helpers/config_utils.py` automatically to read this setting.

Build stops before changing inputs when topology/restart files already exist, preserving those files. Use a separate `WORK_DIR` for a new build.

Downloads replace the final PDB only after validating atom records in a temporary file. Failure preserves the existing PDB and removes the temporary file.

Empty outputs also count as existing files. A stage is skipped only when its completion marker and all required nonempty outputs exist; partial outputs are not overwritten automatically.
