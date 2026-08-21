# Simulation templates / Simulation templates

## 한국어

`1_Simulation/`은 고정된 example을 따라가는 tutorial입니다. `3_Templates/`는
사용자가 준비한 structure와 method별 `config.toml`을 입력받아 실제 계산을
시작할 수 있는 workflow입니다. 기본 parameter는 universal production protocol이
아니므로 system에 맞게 수정하고 pilot run으로 확인합니다.

각 leaf directory는 독립적으로 복사할 수 있는 self-contained template입니다.
실행에 필요한 helper와 `requirements.txt`가 같은 leaf 안에 있으며, family 상위
directory나 `3_Templates/common`의 code를 호출하지 않습니다. 복사한 leaf
directory 안에서 script를 실행합니다.

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

공통 build 설정은 다음과 같습니다.

| Config key | 적용 방식 |
| --- | --- |
| `box_shape` | Soluble system에서 `rectangular`은 `solvatebox`, `octahedral`은 `solvateoct`를 사용합니다. Membrane protein과 Funnel-MetaD는 `rectangular`만 허용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` 중 하나를 선택합니다. System을 먼저 neutralize하고 설정된 salt를 추가합니다. |
| `salt_concentration` | Config 주석에 표시된 mM 단위 농도입니다. 기본값은 `150.0`입니다. |
| `disulfide_bonds` | PDB chain ID와 residue number를 `[["A:23", "A:88"]]` 형식으로 지정합니다. 두 residue의 `SG` atom을 확인한 뒤 solvation 전에 bond를 만듭니다. |

`minimization_steps`, `minimization_steepest_steps`와
`heating_initial_temperature`은 해당 engine input의 `maxcyc`/`ncyc`와
temperature ramp를 바꿉니다. `energy_interval_steps`는 energy와 log 기록 간격,
`restart_interval_steps`는 AMBER `ntwr`에 적용됩니다. GROMACS checkpoint의
`-cpt`는 wall-clock minute 단위이므로 `restart_interval_steps`로 치환하지
않습니다. `equilibration_ensemble`과 `production_ensemble`은 각 stage의
`NVT` 또는 `NPT` 설정을 따로 지정합니다.
Membrane protein을 제외한 template의 기본 minimization은
`maxcyc=5000`, `ncyc=2500`입니다. Membrane protein은 기존
`maxcyc=10000`, `ncyc=5000`을 유지합니다.

Config key에는 unit suffix를 붙이지 않습니다. `temperature`, `pressure`,
`timestep`, distance, force constant의 unit은 관련 section header 바로
아래에 한 번만 표시합니다. `tleap`/AMBER는 distance Å와 energy
kcal/mol, GROMACS는 time ps, PLUMED는 length nm와 energy kJ/mol을
사용하므로 engine 경계를 구분해 적었습니다.

대부분의 `run.sh`는 다음 범위 option을 제공합니다. Option이 없으면 기존과
같이 전체 workflow를 실행합니다.

| Option | 범위 |
| --- | --- |
| `--preparation-only` | Production 직전까지 실행합니다. GaMD/GaREUS의 parameter preparation도 포함합니다. |
| `--production-only` | Completion marker와 필요한 restart/method state가 있는 경우 production만 실행합니다. |
| `--segments START-END` | 1-based inclusive production segment 범위를 선택합니다. |
| `--windows START-END` | FEP에서는 0-based, US에서는 기존 `--window`와 같은 1-based inclusive 범위를 사용합니다. |
| `--system` | `complex` 또는 `solvent` RBFE/ABFE environment를 선택합니다. |
| `--stage` | `restraint`, `charge` 또는 `vdw` ABFE leg를 선택합니다. 현재 RBFE input은 charge와 vdW를 함께 바꾸므로 별도 stage를 선택하지 않습니다. |

REUS와 GaREUS는 exchange에 참여하는 모든 window를 함께 실행합니다. 따라서
production window subset은 제공하지 않습니다. WE는 build와 propagation
interface가 이미 분리되어 있어 preparation/production mode option을 추가하지
않았습니다. `START > 1`인 segment는 직전 restart와 method state가 있어야 합니다.

| Directory | 제공하는 workflow |
| --- | --- |
| [`1_MD`](1_MD/README.md) | Soluble protein, protein–ligand와 membrane-protein conventional MD |
| [`2_US`](2_US/README.md) | Directed seed selection과 umbrella sampling |
| [`3_REMD`](3_REMD/README.md) | T-REMD, REST2, REST3, REUS와 GaREUS |
| [`4_GaMD`](4_GaMD/README.md) | GaMD, LiGaMD3와 Pep-GaMD |
| [`5_FEP`](5_FEP/README.md) | RBFE와 double-decoupling ABFE |
| [`6_WE`](6_WE/README.md) | WESTPA와 AMBER를 사용하는 weighted ensemble |
| [`7_MetaD`](7_MetaD/README.md) | WT-MetaD, funnel MetaD, OPES_METAD와 OPES_EXPANDED |

Minimization, heating과 equilibration은 process가 정상 종료되면 completion marker를
기록합니다. Marker가 없는 partial preproduction은 해당 stage부터 다시 실행합니다.
Production, replica-exchange state, GaMD state, WESTPA state와 PLUMED bias state는
자동으로 삭제하거나 덮어쓰지 않습니다. Method별 continuation 조건은 leaf
README에서 설명합니다.

## English

`1_Simulation/` contains fixed-system tutorials. `3_Templates/` contains
config-driven starting workflows for user-prepared structures. The defaults are
not universal production protocols; adjust them for the system and assess them
with pilot simulations.

Each leaf is a self-contained template that can be copied independently. Its
runtime helpers and `requirements.txt` are stored inside the leaf; scripts do
not call code from the family directory or `3_Templates/common`. Run every
template from its leaf directory. `download.sh` retrieves only a
source structure and does not decide protonation, missing atoms, alternate
locations, biological assemblies, ligands, bound ions, or crystallographic
waters. Pass a reviewed, build-ready PDB to `build.sh`.

Each `config.toml` defines build choices, thermodynamic conditions, production
length, and method-specific parameters. The build writes the applied settings
to `work/resolved_config.toml`; replica and window methods also write
`work/states.tsv`. Every user-facing script describes its arguments and options
with `-h` or `--help`.

Common build controls are `box_shape`, `salt_type`, `salt_concentration`, and
`disulfide_bonds`. Soluble systems map `rectangular` and `octahedral` to LEaP
`solvatebox` and `solvateoct`; membrane protein and Funnel-MetaD require a
rectangular box. Supported salts are NaCl, KCl, MgCl2, and CaCl2. The system is
neutralized before bulk salt is added, and `salt_concentration` uses the mM unit
shown next to the value in `config.toml`. Disulfides use PDB chain and residue
references such as `[["A:23", "A:88"]]` and are created before solvation after
both SG atoms are checked.

Stage controls replace values in the generated engine inputs without changing
the execution commands. They include total and steepest-descent minimization
steps, the initial heating temperature, energy and restart intervals, and
separate equilibration and production ensembles. `restart_interval_steps` maps
to AMBER `ntwr`; it is not converted to GROMACS `-cpt`, whose unit is wall-clock
minutes.
The default minimization is `maxcyc=5000`, `ncyc=2500` for every template
except membrane protein, which retains `maxcyc=10000`, `ncyc=5000`.

Config keys do not carry unit suffixes. Units for `temperature`, `pressure`,
`timestep`, distances, and force constants are stated once immediately below
the relevant section header. The comments distinguish tleap/AMBER distances
in Å and energies in kcal/mol, GROMACS time in ps, and PLUMED lengths in nm
and energies in kJ/mol.

Most runners support `--preparation-only`, `--production-only`, and inclusive
1-based `--segments START-END`. FEP adds `--system`, ABFE adds `--stage`, and
FEP windows use 0-based `--windows START-END`. US preserves its existing
1-based window numbering. RBFE couples charge and vdW in one path, so it has no
separate stage selector. REUS and GaREUS always run all exchange windows, and
WE keeps its already-separated build and propagation interface. Continuation
from a segment after 1 requires the preceding restart and method state.

The seven families cover conventional MD, umbrella sampling, replica exchange,
GaMD variants, RBFE/ABFE, WESTPA weighted ensemble, and MetaD/OPES. Incomplete
preproduction stages can be rerun, while production and method state files are
preserved rather than overwritten automatically. See each leaf README for its
continuation contract.
