# Simulation templates / Simulation templates

## 한국어

`1_Simulation/`은 고정된 example을 따라가는 tutorial입니다. `3_Templates/`는
사용자가 준비한 structure와 method별 `config.toml`을 입력받아 실제 계산을
시작할 수 있는 workflow입니다. 기본 parameter는 universal production protocol이
아니므로 system에 맞게 수정하고 pilot run으로 확인합니다.

| Directory | 제공하는 workflow |
| --- | --- |
| [`1_MD`](1_MD/README.md) | Soluble protein, protein–ligand와 membrane-protein conventional MD |
| [`2_US`](2_US/README.md) | Directed seed selection과 umbrella sampling |
| [`3_REMD`](3_REMD/README.md) | T-REMD, REST2, REST3, REUS와 GaREUS |
| [`4_GaMD`](4_GaMD/README.md) | GaMD, LiGaMD3와 Pep-GaMD |
| [`5_FEP`](5_FEP/README.md) | RBFE와 double-decoupling ABFE |
| [`6_WE`](6_WE/README.md) | WESTPA와 AMBER를 사용하는 weighted ensemble |
| [`7_MetaD`](7_MetaD/README.md) | WT-MetaD, funnel MetaD, OPES_METAD와 OPES_EXPANDED |

| Directory | 기본 engine(선택 가능한 executable) | GPU와 MPI |
| --- | --- | --- |
| `1_MD` | AMBER `pmemd.cuda`(`pmemd`, `sander`) | GPU 1개 또는 CPU |
| `2_US` | AMBER `pmemd.cuda`. Directed seed를 만드는 rMD 단계에는 PLUMED 연동 build가 필요합니다. | GPU 1개 |
| `3_REMD` | T-REMD, REUS, GaREUS: `pmemd.cuda.MPI`. REST2, REST3: PLUMED 2.10.2 이상으로 patch한 GROMACS 2024.3 `gmx_mpi` | State 수만큼 MPI rank, GPU |
| `4_GaMD`, `5_FEP` | AMBER `pmemd.cuda` | GPU 1개 |
| `6_WE` | WESTPA 2 + AMBER `pmemd.cuda`(`pmemd`, `sander`) | 기본 GPU 1개. `WE_GPU_IDS`로 worker별 GPU를 지정합니다. |
| `7_MetaD` | PLUMED 2.10 연동 AMBER `pmemd.cuda`(`pmemd`, `sander`) | GPU 1개 또는 CPU |

Engine 설정 key와 build 조건은 각 leaf README에 있습니다.

각 leaf directory는 독립적으로 복사할 수 있는 self-contained template입니다.
사용자가 실행하는 script와 config는 leaf root에, 자동 호출되는 내부 code는
`helpers/`에 있습니다. `requirements.txt`도 같은 leaf에 있으며 family 상위
directory의 code를 호출하지 않습니다. 복사한 leaf directory 안에서 script를
실행합니다.

각 leaf의 `requirements.txt`로 필요한 Python dependency를 설치합니다.
상위 `requirements.txt`는 모든 leaf의 dependency를 합친 목록입니다.
`h5py`는 WESTPA의 HDF5 state를 읽는 WE leaf에 포함됩니다.

```bash
./download.sh 1UBQ
./build.sh structure/1UBQ.pdb
./run.sh --dry-run
./run.sh
```

`download.sh`는 source structure만 내려받습니다. Protonation, missing atom,
alternate location, biological assembly, ligand, bound ion과 crystal water는 자동으로
결정하지 않습니다. 검토를 마친 build-ready PDB를 `build.sh`에 전달합니다.

`config.toml`에는 build, thermodynamic state, production 길이와 method parameter가
들어 있습니다. Build 결과에는 실제 적용값을 기록한 `work/resolved_config.toml`이
포함됩니다. Replica/window method는 `work/states.tsv`도 생성합니다. 모든
user-facing script는 `-h`와 `--help`로 argument와 option 설명을 출력합니다.

대부분의 `run.sh`는 다음 범위 option을 제공합니다. Option이 없으면 전체
workflow를 실행합니다.

| Option | 범위 |
| --- | --- |
| `--preparation-only` | Production 직전까지 실행합니다. GaMD/GaREUS의 parameter preparation도 포함합니다. |
| `--production-only` | Completion marker와 필요한 restart/method state가 있는 경우 production만 실행합니다. |
| `--segments START-END` | 1-based inclusive production segment 범위를 선택합니다. |
| `--windows START-END` | FEP에서는 0-based, US에서는 1-based inclusive 범위를 사용합니다. US는 window 하나를 고르는 `--window N`도 제공합니다. |
| `--system` | `complex` 또는 `solvent` RBFE/ABFE environment를 선택합니다. |
| `--stage` | `restraint`, `charge` 또는 `vdw` ABFE leg를 선택합니다. RBFE input은 charge와 vdW를 함께 바꾸므로 별도 stage를 선택하지 않습니다. |

REUS와 GaREUS는 exchange에 참여하는 모든 window를 함께 실행합니다. 따라서
production window subset은 제공하지 않습니다. WE는 build와 propagation
interface가 이미 분리되어 있어 preparation/production mode option을 추가하지
않았습니다. `START > 1`인 segment는 직전 restart와 method state가 있어야 합니다.

### Config 작성 규칙

각 leaf README의 `Config 선택값` table은 값에 따라 동작이 달라지는 option과
지원되는 고정값을 설명합니다. `auto`, `file`처럼 다른 parameter를 활성화하는
mode는 사용되는 설정과 무시되는 설정을 함께 표시합니다. 숫자 parameter의
의미와 unit은 결과에 직접 영향을 주는 항목만 method 설명 가까이에 둡니다.
Leaf directory만 복사해도 config의 허용값을 확인할 수 있도록 leaf README를
기준 문서로 사용합니다.

Protein force field와 water model은 독립적으로 조합하지 않습니다. 각 leaf
README에 적힌 compatibility pair만 선택하며, 지원하지 않는 조합은 topology
build 전에 config error로 중단됩니다. 대부분의 soluble template은
`ff99SB-ILDN + TIP3P`, `ff14SB + TIP3P`, `ff19SB + OPC`를 지원하고 기본값은
`ff19SB + OPC`입니다. Membrane처럼 downstream 조합을 별도로 검증해야 하는
leaf는 더 좁은 범위를 사용할 수 있습니다.

공통 build 설정은 다음과 같습니다. 허용값이나 고정 여부는 leaf README를
따릅니다.

| Config key | 적용 방식 |
| --- | --- |
| `box_shape` | `rectangular`은 `solvatebox`, `octahedral`은 `solvateoct`를 사용합니다. Membrane protein, FEP와 Funnel-MetaD는 `rectangular`만 사용합니다. |
| `salt_type` | System을 먼저 neutralize한 뒤 bulk salt를 추가합니다. `NaCl`, `KCl`, `MgCl2`, `CaCl2`를 지원하며 FEP는 `NaCl`만 적용합니다. |
| `salt_concentration` | Config 주석에 표시된 mM 단위 농도입니다. 기본값은 `150.0`입니다. |
| `disulfide_bonds` | PDB chain ID와 residue number를 `[["A:23", "A:88"]]` 형식으로 지정합니다. 두 residue의 `SG` atom을 확인한 뒤 solvation 전에 bond를 만듭니다. |

`minimization_steps`, `minimization_steepest_steps`와
`heating_initial_temperature`은 해당 engine input의 `maxcyc`/`ncyc`와
temperature ramp를 바꿉니다. `energy_interval_steps`는 energy와 log 기록 간격,
`restart_interval_steps`는 AMBER `ntwr`에 적용됩니다. GROMACS checkpoint의
`-cpt`는 wall-clock minute 단위이므로 `restart_interval_steps`로 치환하지
않습니다. `equilibration_ensemble`과 `production_ensemble`은 각 stage를 따로
설정하며, 실제 허용되는 `NVT`/`NPT` 조합은 leaf README에 표시합니다.
Membrane protein을 제외한 template의 기본 minimization은
`maxcyc=5000`, `ncyc=2500`이고, membrane protein은 `maxcyc=10000`,
`ncyc=5000`입니다.

Config key에는 unit suffix를 붙이지 않습니다. `temperature`, `pressure`,
`timestep`, distance, force constant의 unit은 관련 section header 바로
아래에 한 번만 표시합니다. `tleap`/AMBER는 distance Å와 energy
kcal/mol, GROMACS는 time ps, PLUMED는 length nm와 energy kJ/mol을
사용하므로 engine 경계를 구분해 적었습니다.

Config의 숫자 값과 numeric array에는 NaN/Inf를 사용할 수 없습니다. 양수와 0을
허용하는 범위는 parameter별로 다릅니다.

### 실행 상태

Completion marker, partial output, input 변경, 동시 실행과 실패 후 재실행 규칙은
[GUIDE.md 부록](../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다. Method별 continuation 조건은 leaf
README에서 설명합니다.

## English

`1_Simulation/` contains fixed-system tutorials. `3_Templates/` contains
config-driven starting workflows for user-prepared structures and a
method-specific `config.toml`. The defaults are not universal production
protocols; adjust them for the system and assess them with pilot simulations.

| Directory | Workflows |
| --- | --- |
| [`1_MD`](1_MD/README.md) | Soluble-protein, protein–ligand, and membrane-protein conventional MD |
| [`2_US`](2_US/README.md) | Directed seed selection and umbrella sampling |
| [`3_REMD`](3_REMD/README.md) | T-REMD, REST2, REST3, REUS, and GaREUS |
| [`4_GaMD`](4_GaMD/README.md) | GaMD, LiGaMD3, and Pep-GaMD |
| [`5_FEP`](5_FEP/README.md) | RBFE and double-decoupling ABFE |
| [`6_WE`](6_WE/README.md) | Weighted ensemble with WESTPA and AMBER |
| [`7_MetaD`](7_MetaD/README.md) | WT-MetaD, funnel MetaD, OPES_METAD, and OPES_EXPANDED |

| Directory | Default engine (selectable executables) | GPU and MPI |
| --- | --- | --- |
| `1_MD` | AMBER `pmemd.cuda` (`pmemd`, `sander`) | One GPU or CPU |
| `2_US` | AMBER `pmemd.cuda`; the rMD directed-seed stage needs a PLUMED-enabled build | One GPU |
| `3_REMD` | T-REMD, REUS, GaREUS: `pmemd.cuda.MPI`. REST2, REST3: GROMACS 2024.3 `gmx_mpi` patched with PLUMED 2.10.2 or newer | One MPI rank per state, GPU |
| `4_GaMD`, `5_FEP` | AMBER `pmemd.cuda` | One GPU |
| `6_WE` | WESTPA 2 + AMBER `pmemd.cuda` (`pmemd`, `sander`) | One GPU by default; `WE_GPU_IDS` assigns a GPU per worker |
| `7_MetaD` | PLUMED 2.10-enabled AMBER `pmemd.cuda` (`pmemd`, `sander`) | One GPU or CPU |

Engine config keys and build requirements are in each leaf README.

Each leaf is a self-contained template that can be copied independently.
User-facing scripts and config remain in the leaf root, while automatically
called internal code is stored in `helpers/`. `requirements.txt` also remains
inside the leaf; scripts do not call code from the family directory. Run every
template from its leaf directory.

Install Python dependencies from the leaf's `requirements.txt`. The root
`requirements.txt` lists the union of all leaf dependencies. `h5py` is included
in the WE leaf for WESTPA HDF5 state access.

A typical run is `./download.sh 1UBQ`, `./build.sh structure/1UBQ.pdb`,
`./run.sh --dry-run`, and `./run.sh`. `download.sh` retrieves only a source
structure and does not decide protonation, missing atoms, alternate locations,
biological assemblies, ligands, bound ions, or crystallographic waters. Pass a
reviewed, build-ready PDB to `build.sh`.

Each `config.toml` defines build choices, thermodynamic conditions, production
length, and method-specific parameters. The build writes the applied settings
to `work/resolved_config.toml`; replica and window methods also write
`work/states.tsv`. Every user-facing script describes its arguments and options
with `-h` or `--help`.

Most runners support these range options. Without an option, the full workflow
runs.

| Option | Scope |
| --- | --- |
| `--preparation-only` | Runs up to production, including GaMD/GaREUS parameter preparation. |
| `--production-only` | Runs only production when the completion marker and required restart/method state exist. |
| `--segments START-END` | Selects an inclusive, 1-based production segment range. |
| `--windows START-END` | Uses 0-based indices for FEP and 1-based inclusive indices for US. US also accepts `--window N` for a single window. |
| `--system` | Selects the `complex` or `solvent` RBFE/ABFE environment. |
| `--stage` | Selects the `restraint`, `charge`, or `vdw` ABFE leg. RBFE couples charge and vdW in one path, so it has no stage selector. |

REUS and GaREUS always run all exchange windows, so they offer no production
window subset. WE keeps its already-separated build and propagation interface
and has no preparation/production mode option. Continuation from a segment
after 1 requires the preceding restart and method state.

### Config conventions

The `Config choices` table in each leaf README documents options that select
behavior and values that are fixed by the implementation. Modes such as `auto`
and `file` identify both the settings they consume and the settings they
ignore. Numeric parameters are described only when their meaning or unit is
needed to run or interpret that method. The leaf README is the authoritative
config reference so that a copied leaf directory remains self-contained.

Protein force fields and water models are not independent choices. Select only a
compatibility pair listed in the leaf README; unsupported pairs stop with a config
error before topology construction. Most soluble templates support
`ff99SB-ILDN + TIP3P`, `ff14SB + TIP3P`, and `ff19SB + OPC`, with
`ff19SB + OPC` as the default. Leaves such as membrane workflows may expose a
narrower range when downstream combinations require separate validation.

Common build controls are listed below. The leaf README defines whether each
value is configurable or fixed for that builder.

| Config key | Behavior |
| --- | --- |
| `box_shape` | `rectangular` maps to `solvatebox` and `octahedral` to `solvateoct`. Membrane protein, FEP, and Funnel-MetaD use `rectangular` only. |
| `salt_type` | The system is neutralized before bulk salt is added. `NaCl`, `KCl`, `MgCl2`, and `CaCl2` are supported; FEP applies `NaCl` only. |
| `salt_concentration` | Concentration in mM, as noted in `config.toml`. Default `150.0`. |
| `disulfide_bonds` | PDB chain and residue references such as `[["A:23", "A:88"]]`. Bonds are created before solvation after both `SG` atoms are checked. |

Stage controls replace values in the generated engine inputs without changing
the execution commands. `minimization_steps`, `minimization_steepest_steps`, and
`heating_initial_temperature` set `maxcyc`/`ncyc` and the temperature ramp.
`energy_interval_steps` sets the energy and log interval, and
`restart_interval_steps` maps to AMBER `ntwr`; it is not converted to GROMACS
`-cpt`, whose unit is wall-clock minutes. `equilibration_ensemble` and
`production_ensemble` are set separately, and the leaf README states which
`NVT` and `NPT` choices each stage accepts. The default minimization is
`maxcyc=5000`, `ncyc=2500` for every template except membrane protein, which
uses `maxcyc=10000`, `ncyc=5000`.

Config keys do not carry unit suffixes. Units for `temperature`, `pressure`,
`timestep`, distances, and force constants are stated once immediately below
the relevant section header. The comments distinguish tleap/AMBER distances
in Å and energies in kcal/mol, GROMACS time in ps, and PLUMED lengths in nm
and energies in kJ/mol.

Numeric config values and arrays must be finite. Whether zero is allowed
depends on the parameter.

### Run state

Completion markers, partial outputs, input changes, concurrent runs, and reruns
after a failure are described in [GUIDE.md appendix](../GUIDE.md#4-appendix-run-state-and-recovery). See each leaf
README for its continuation contract.
