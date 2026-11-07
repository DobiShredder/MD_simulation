# LiGaMD3 template

## 한국어

Amber 26 `igamd=28` triple boost를 사용합니다. Ligand essential nonbonded,
나머지 nonbonded와 bonded potential에 각각 boost를 적용합니다. Conventional MD 뒤에
GaMD parameter preparation을 실행하고, production segment는 MD restart와
`gamd-restart.dat`를 함께 이어받습니다. Triple-boost LiGaMD3는 이 directory의
고정 method이며 별도 config mode가 아닙니다. 이 workflow는 serial `pmemd.cuda`만
지원합니다.

### 필요한 input

- `build.sh`에 넘길 reviewed complex PDB
- `config.toml`에서 지정하는 precharged RESP MOL2와 matching frcmod
- `config.toml`의 `ligand_mask`와 `receptor_mask`

`ligand_mask`와 `receptor_mask`는 residue 이름으로 추정하지 않는 system별
selection입니다. Build 과정에서 두 mask가 atom을 선택하는지, 겹치지 않는지,
receptor가 LiGaMD3의 `bgpro2atm`–`edpro2atm`에 필요한 연속 atom 범위인지
검사합니다. 두 LEaP pass는 같은 `ligand.mol2`와 `ligand.frcmod`를 읽으며, final
pass 전에 내용이 바뀌었으면 build가 중단합니다.

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

필요한 program과 기본 계산량은 [GaMD templates README](../README.md#필요한-program)를
참고합니다.

### 실행

```bash
./build.sh prepared_complex.pdb
./run.sh --dry-run
./run.sh --allow-unverified
```

Amber 26 `pmemd.cuda`에서 이 template의 LiGaMD3(`igamd=28`) 실행은 아직 검증하지
않았습니다(미검증). 실제 engine 실행에는 `--allow-unverified`가 필요하고,
`--dry-run`은 이 argument 없이 실행됩니다. 이 argument는 호환성을 보장하지
않습니다. 짧은 run으로 GaMD parameter와 state, 기록된 boost, `gamd-restart.dat`와
continuation을 확인하기 전에는 결과를 해석하지 않습니다.

Amber 26의 LiGaMD3 `gamd.log`는 세 boost를 별도 column으로 기록하지 않고
`Boost-Energy-Potential`과 `Boost-Energy-Dihedral` 두 aggregate column만
기록합니다. Frame별 total boost `ΔV`는 두 column의 합이며, 각 column은
`ΔV_L`, `ΔV_D`, `ΔV_B`를 분리한 값이 아닙니다.

### 파일 역할

| File | 역할 |
| --- | --- |
| `download.sh` | `download.sh PDB_ID`로 source complex를 RCSB에서 받아 atom record를 확인한 뒤 저장; ligand parameter는 만들지 않음 |
| `config.toml` | Build, MD 길이와 GaMD 통계 parameter |
| `build.sh` | Mask 검사, complex topology와 LiGaMD3 input 생성 |
| `run.sh` | Minimization부터 segmented production까지 실행; 실제 engine 실행에는 `--allow-unverified` 필요 |
| `helpers/generate_gamd_inputs.py` | `gamd_prepare.in`과 `production.in` 생성; `build.sh`가 자동 호출 |

`helpers/`의 나머지 파일도 `build.sh`와 `run.sh`가 자동 호출하는 leaf-local 내부
code이며 직접 실행하지 않습니다.

### Output

Production이 여러 segment이면 `work/001`, `work/002`, ...에 저장합니다. 처음부터
여러 segment를 실행하면 `work/001/`부터 생성합니다. 처음 numbered layout으로
실행했다면 segment 수를 줄여도 첫 output은 `work/001/`에 유지합니다. 한 segment를
root `work/production.*`로 완료한 뒤 segment 수를 늘렸다면 첫 output은 그대로 두고
후속 output만 `work/002/`, `work/003/`에 생성합니다.

이 leaf에는 analysis entry가 없습니다. Production의 `production.gamd.log`와
`production.nc`를 segment별로 보존합니다.
[GaMD reweighting tutorial](../../../2_Analysis/7_Enhanced_Sampling/7.2_GaMD_Reweighting/README.md)은
지정된 tutorial의 단일 log와 CV 100 records를 소비합니다. 이 template의 여러
segment를 자동 병합하는 consumer는 제공하지 않습니다.

### 성공 확인

| Command | 마지막 출력 | 확인할 파일 |
| --- | --- | --- |
| `./build.sh` | `Protein-ligand topology and restart: work/system.parm7, work/system.rst7` | `work/inputs/gamd_prepare.in`, `work/inputs/production.in`, `work/resolved_config.toml`의 `[gamd]` |
| `./run.sh --allow-unverified --preparation-only` | `GaMD preparation output: work/gamd_prepare.rst7 and work/gamd_prepare.gamd.rst` | `work/gamd_prepare.gamd.log` |
| `./run.sh --allow-unverified` | Segment마다 `Completed: production segment N/10 (work/00N)`, 마지막에 `GaMD production completed: work` | Segment별 `production.nc`, `production.gamd.log`, `production.gamd.rst`, `production.rst7` |

다음 단계는 segment별 boost distribution 확인입니다. 기준은
[GaMD templates README](../README.md#결과-해석)에 있습니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `ligand_force_field` | `GAFF2`만 지원 | `GAFF2` | Ligand parameter 형식을 결정합니다. |
| `charge_method` | precharged `RESP` MOL2만 지원 | `RESP` | `ligand_mol2`의 RESP charge를 그대로 사용합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Conventional equilibration에 적용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NVT` | LiGaMD3 preparation과 production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | `"random"`은 AMBER `ig=-1`, 정수에서 stage와 segment별 seed를 파생합니다. |

### 숫자 option

GaMD statistics 길이, `sigma0*`와 `averaging_interval_steps`는 아래 section에서
설명합니다. 나머지 숫자 key는 다음과 같습니다.

| Key | 기본값 | Unit | Stage | 효과 |
| --- | --- | --- | --- | --- |
| `solute_box_distance` | 14.0 | Å | Build | Solute와 box 경계 사이 최소 water 두께입니다. |
| `salt_concentration` | 150.0 | mM | Build | Water 수로부터 neutralization 뒤 추가할 salt pair 수를 계산합니다. |
| `temperature` | 300.0 | K | Heating 이후 전체 | `temp0`와 heating 목표 온도입니다. |
| `pressure` | 1.0 | bar | NPT stage | `pres0`입니다. 기본 config에서는 equilibration에만 적용됩니다. |
| `timestep` | 2.0 | fs | 모든 MD | AMBER `dt`(ps)로 기록합니다. Hydrogen mass repartitioning이 없으므로 2.0 fs를 넘으면 거부합니다. |
| `minimization_steps`, `minimization_steepest_steps` | 5000, 2500 | cycles | Minimization | `maxcyc`와 `ncyc`입니다. Steepest descent 뒤 conjugate gradient를 사용합니다. |
| `heating_initial_temperature` | 20.0 | K | Heating | `tempi`입니다. `temperature`보다 클 수 없습니다. |
| `heating_steps` | 250000 | steps | Heating | NVT heating 길이입니다. Non-solvent atom에 5 kcal/mol/Å² restraint를 둡니다. |
| `equilibration_steps` | 500000 | steps | Equilibration | NPT equilibration 길이입니다. |
| `production_steps` | 50000000 | steps | Production | 모든 segment를 합한 길이입니다. `production_segments`로 나누어떨어져야 합니다. |
| `production_segments` | 10 | — | Production | Segment 수입니다. Segment마다 engine을 한 번 실행합니다. |
| `trajectory_interval_steps` | 5000 | steps | Heating 이후 전체 | `ntwx`입니다. `gamd.log`도 같은 간격으로 기록되어 기본 segment당 1,000 records입니다. |
| `energy_interval_steps` | 5000 | steps | Heating 이후 전체 | `ntpr`입니다. |
| `restart_interval_steps` | 5000 | steps | Heating 이후 전체 | `ntwr`입니다. |
| `ligand_net_charge` | 0 | e | Build | `ligand_mol2` partial charge 합과 0.01 e 안에서 같아야 합니다. |

### Statistics 구간

`conventional_preparation_steps`는 `ntcmdprep`, `conventional_statistics_steps`는
preparation을 포함한 conventional MD 전체 길이인 `ntcmd`입니다.
`boost_preparation_steps`는 `ntebprep`, `boost_statistics_steps`는 preparation을
포함한 boost equilibration 전체 길이인 `nteb`입니다. 각 statistics 값은 대응하는
preparation 값보다 커야 하며, 네 값은 `averaging_interval_steps`의 배수여야 합니다.

기본값은 각 구간의 전체 1,000,000 steps 중 처음 200,000 steps를 preparation에
사용하고, 나머지 800,000 steps에서 statistics를 수집합니다. Parameter preparation의
전체 길이는 `ntcmd + nteb`인 2,000,000 steps이며 production 길이에는 포함하지
않습니다.

### Boost 상한과 averaging window

`sigma0P`, `sigma0D`, `sigma0B`는 같은 이름의 AMBER keyword로 기록됩니다.
`igamd=28`에서 각각 첫 번째(ligand essential nonbonded), 두 번째(나머지
nonbonded), 세 번째(bonded) boost의 standard deviation 상한이며 기본값은 모두
6 kcal/mol입니다.

Amber 26 manual은 `ntave`를 system 전체 atom 수의 약 4배로 권장합니다.
`build.sh`는 topology를 만든 뒤 atom 수와 권장값(4 x atoms)을 출력하고,
`averaging_interval_steps`가 이보다 작으면 stderr에 warning을 출력합니다.
기본값 50,000은 12,500 atoms까지의 system에 해당하므로 일반적인 solvated protein에서는
warning이 출력됩니다. 값을 바꿀 때는 네 statistics 길이도 새 값의 배수로 맞춥니다.

### Seed와 segment input

정수 `random_seed=s`에서 heating은 `s`, equilibration은 `s+1`, GaMD parameter
preparation은 `s+2`를 사용합니다. Production segment `n`은 `s+2+n`을 사용합니다.
`"random"`은 각 stage의 `ig=-1`로 AMBER가 seed를 선택하게 합니다.

Stage seed와 production seed의 기준값은 `resolved_config.toml`의 `[gamd]`에
기록합니다. Build가 만든 `work/inputs/production.in`은 첫 production seed를 가진
template이며, runner가 각 segment directory의 `production.in`을 생성해 실제 `ig`를
기록합니다. Seed가 같아도 engine, hardware와 실행 조건이 다르면 trajectory가
같다는 뜻은 아닙니다.

### Engine 선택

`AMBER_ENGINE`이 설정되어 있으면 이를 사용하며, 없으면 build가 기록한
`work/resolved_config.toml`의 `run.engine`을 읽습니다. 허용하는 executable 이름은
`pmemd.cuda`이며 설치 경로를 지정할 수 있습니다. 빈 override, 누락된 engine 설정과
지원하지 않는 executable은 기본값으로 대체하지 않고 error로 중단합니다. Runner가
`helpers/config_utils.py`를 자동 호출해 이 설정을 읽습니다.

### 문제 해결

| Message | 원인과 조치 |
| --- | --- |
| `Error: LiGaMD3 on the Amber 26 GPU engine is unverified; rerun with --allow-unverified after reading README.md.` | 위 미검증 설명을 읽은 뒤 `--allow-unverified`를 붙입니다. `--dry-run`에는 필요하지 않습니다. |
| `Error: LiGaMD3 and Pep-GaMD require the serial pmemd.cuda engine: ...` | `AMBER_ENGINE` 또는 `run.engine`을 serial `pmemd.cuda`로 바꿉니다. |
| `LiGaMD3 receptor_mask must select one contiguous atom range` 또는 `ligand_mask and receptor_mask overlap` | `receptor_mask`가 water, ion과 ligand를 모두 제외해야 합니다. `salt_type`을 바꾸면 해당 ion residue 이름도 제외합니다. |
| `Config error: ligand MOL2 charge does not match ligand_net_charge: X` | `ligand_net_charge`를 MOL2 charge 합과 맞추거나 charge를 다시 fitting합니다. |
| `Config error: production steps must be divisible by production_segments` | `production_steps`를 `production_segments`의 배수로 맞춥니다. |
| `GaMD statistics in config.toml: NAME (V) must be a multiple of averaging_interval_steps (A)` | 네 statistics 길이를 `averaging_interval_steps`의 배수로 맞춥니다. |
| `Warning: averaging_interval_steps (A) is below 4 x topology atoms (...). ...` | Build는 계속됩니다. 아래 averaging window section을 보고 값을 정합니다. |
| `Completed GaMD parameter preparation is required for production: ...` | `--production-only` 전에 `--preparation-only` 또는 전체 `run.sh`로 preparation을 끝냅니다. |
| `Previous production segment is incomplete: work/00N` | `--segments START-END`의 START 앞 segment가 완료되지 않았습니다. 앞 segment부터 실행합니다. |

실행 상태, 실패 후 재실행, 동시 실행 보호는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

This template uses the Amber 26 `igamd=28` triple boost on ligand-essential
nonbonded, remaining nonbonded, and bonded potentials. GaMD parameter preparation
follows conventional MD, and each production segment continues both the MD
restart and `gamd-restart.dat`. Triple-boost LiGaMD3 is fixed by this directory
and is not a config mode. Serial `pmemd.cuda` is required.

### Required inputs

- A reviewed complex PDB passed to `build.sh`
- A precharged RESP MOL2 and matching frcmod, set in `config.toml`
- `ligand_mask` and `receptor_mask` in `config.toml`

`ligand_mask` and `receptor_mask` are system-specific selections; they are not
inferred from residue names. The build validates non-empty, non-overlapping
selections and requires the receptor to form the contiguous atom range used by
`bgpro2atm` and `edpro2atm`. Both LEaP passes read the same `ligand.mol2` and
`ligand.frcmod`; the build stops if their contents change before the final pass.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

See the [GaMD templates README](../README.md#required-programs) for required
programs and the default computation.

### Run

```bash
./build.sh prepared_complex.pdb
./run.sh --dry-run
./run.sh --allow-unverified
```

LiGaMD3 (`igamd=28`) with this template has not been verified on Amber 26
`pmemd.cuda` (unverified). Engine runs require `--allow-unverified`;
`--dry-run` works without it. The argument does not guarantee compatibility. Do
not interpret results until a short run confirms the GaMD parameters and state,
the logged boost, `gamd-restart.dat` and continuation.

Amber 26 does not write the three LiGaMD3 boosts as separate `gamd.log`
columns. It writes only the aggregate `Boost-Energy-Potential` and
`Boost-Energy-Dihedral` columns. The per-frame total boost `ΔV` is their sum;
neither column is a separated `ΔV_L`, `ΔV_D` or `ΔV_B`.

### File roles

| File | Role |
| --- | --- |
| `download.sh` | `download.sh PDB_ID` downloads a source complex from RCSB and saves it after checking atom records; it does not create ligand parameters |
| `config.toml` | Build, MD length and GaMD statistics parameters |
| `build.sh` | Checks the masks and creates the complex topology and LiGaMD3 inputs |
| `run.sh` | Runs minimization through segmented production; engine runs require `--allow-unverified` |
| `helpers/generate_gamd_inputs.py` | Writes `gamd_prepare.in` and `production.in`; called by `build.sh` |

The other files in `helpers/` are also leaf-local internal code called
automatically by `build.sh` and `run.sh`; do not run them directly.

### Outputs

Multi-segment production is written to `work/001`, `work/002`, and so on. Runs
configured with multiple segments from the start use `work/001/` onward. If the
first run used numbered directories, reducing the count retains the first output
under `work/001/`. If one segment completed as `work/production.*`, increasing
the segment count retains that first output and writes later outputs under
`work/002/`, `work/003/`, etc.

This leaf has no analysis entry. Preserve each production segment's
`production.gamd.log` and `production.nc`. The
[GaMD reweighting tutorial](../../../2_Analysis/7_Enhanced_Sampling/7.2_GaMD_Reweighting/README.md)
consumes one log and 100 matching CV records from its designated tutorial.
It does not merge this template's production segments automatically.

### Success check

| Command | Last line | Files to check |
| --- | --- | --- |
| `./build.sh` | `Protein-ligand topology and restart: work/system.parm7, work/system.rst7` | `work/inputs/gamd_prepare.in`, `work/inputs/production.in`, `[gamd]` in `work/resolved_config.toml` |
| `./run.sh --allow-unverified --preparation-only` | `GaMD preparation output: work/gamd_prepare.rst7 and work/gamd_prepare.gamd.rst` | `work/gamd_prepare.gamd.log` |
| `./run.sh --allow-unverified` | `Completed: production segment N/10 (work/00N)` per segment, then `GaMD production completed: work` | Each segment's `production.nc`, `production.gamd.log`, `production.gamd.rst`, `production.rst7` |

Next, check each segment's boost distribution with the criteria in the
[GaMD templates README](../README.md#interpreting-the-results).

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `ligand_force_field` | `GAFF2` only | `GAFF2` | Selects the ligand parameter format. |
| `charge_method` | Precharged `RESP` MOL2 only | `RESP` | Uses the RESP charges already present in `ligand_mol2`. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to conventional equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NVT` | Sets `ntb` and `ntp` for LiGaMD3 preparation and production. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | `"random"` maps to AMBER `ig=-1`; an integer derives stage and segment seeds. |

### Numeric options

GaMD statistics lengths, `sigma0*` and `averaging_interval_steps` are described
in the sections below. The remaining numeric keys are:

| Key | Default | Unit | Stage | Effect |
| --- | --- | --- | --- | --- |
| `solute_box_distance` | 14.0 | Å | Build | Minimum water thickness between the solute and the box edge. |
| `salt_concentration` | 150.0 | mM | Build | Sets the number of salt pairs added after neutralization from the water count. |
| `temperature` | 300.0 | K | Heating onward | `temp0` and the heating target. |
| `pressure` | 1.0 | bar | NPT stages | `pres0`; with the default config only equilibration uses it. |
| `timestep` | 2.0 | fs | All MD | Written as AMBER `dt` (ps). Values above 2.0 fs are rejected because hydrogen masses are not repartitioned. |
| `minimization_steps`, `minimization_steepest_steps` | 5000, 2500 | cycles | Minimization | `maxcyc` and `ncyc`; steepest descent, then conjugate gradient. |
| `heating_initial_temperature` | 20.0 | K | Heating | `tempi`; cannot exceed `temperature`. |
| `heating_steps` | 250000 | steps | Heating | NVT heating length with a 5 kcal/mol/Å² non-solvent restraint. |
| `equilibration_steps` | 500000 | steps | Equilibration | NPT equilibration length. |
| `production_steps` | 50000000 | steps | Production | Total length over all segments; must be divisible by `production_segments`. |
| `production_segments` | 10 | — | Production | Number of segments, one engine run each. |
| `trajectory_interval_steps` | 5000 | steps | Heating onward | `ntwx`. `gamd.log` uses the same interval, giving 1,000 records per default segment. |
| `energy_interval_steps` | 5000 | steps | Heating onward | `ntpr`. |
| `restart_interval_steps` | 5000 | steps | Heating onward | `ntwr`. |
| `ligand_net_charge` | 0 | e | Build | Must match the sum of `ligand_mol2` partial charges within 0.01 e. |

### Statistics intervals

`conventional_preparation_steps` sets `ntcmdprep`; `conventional_statistics_steps`
sets `ntcmd`, the total conventional MD length including preparation.
`boost_preparation_steps` sets `ntebprep`; `boost_statistics_steps` sets `nteb`,
the total boost equilibration length including preparation. Each statistics value
must exceed its preparation value, and all four values must be multiples of
`averaging_interval_steps`.

By default, each 1,000,000-step interval contains 200,000 preparation steps and
800,000 steps for statistics collection. The full parameter preparation length is
`ntcmd + nteb`, or 2,000,000 steps; it is separate from the production length.

### Boost limits and averaging window

`sigma0P`, `sigma0D` and `sigma0B` are written as the AMBER keywords of the same
name. With `igamd=28`, they limit the standard deviations of the first
(ligand-essential nonbonded), second (remaining nonbonded) and third (bonded)
boosts; all default to 6 kcal/mol.

The Amber 26 manual recommends `ntave` of about four times the total atom
count. After creating the topology, `build.sh` prints the atom count and the
recommended value (4 x atoms), and writes a warning to stderr if
`averaging_interval_steps` is smaller. The default 50,000 matches systems of up
to 12,500 atoms, so a typical solvated protein triggers the warning. When
changing it, keep the four statistics lengths multiples of the new value.

### Seeds and segment inputs

For integer `random_seed=s`, heating uses `s`, equilibration `s+1`, and GaMD
parameter preparation `s+2`. Production segment `n` uses `s+2+n`. With
`"random"`, each stage uses `ig=-1` and AMBER selects its seed.

Stage seeds and the production seed base are recorded under `[gamd]` in
`resolved_config.toml`. The build-generated `work/inputs/production.in` is the
first-seed template; the runner creates `production.in` in each segment
directory with its actual `ig`. Fixed seeds do not guarantee identical
trajectories across engines, hardware, or execution conditions.

### Engine selection

`AMBER_ENGINE` overrides `run.engine` in the build-generated
`work/resolved_config.toml`. Accepted executable names are `pmemd.cuda`;
installation paths are accepted. Empty overrides, missing engine settings and
unsupported executables fail instead of falling back to a default. The runner
invokes `helpers/config_utils.py` automatically to read this setting.

### Troubleshooting

| Message | Cause and fix |
| --- | --- |
| `Error: LiGaMD3 on the Amber 26 GPU engine is unverified; rerun with --allow-unverified after reading README.md.` | Read the unverified note above, then add `--allow-unverified`. `--dry-run` does not need it. |
| `Error: LiGaMD3 and Pep-GaMD require the serial pmemd.cuda engine: ...` | Set `AMBER_ENGINE` or `run.engine` to serial `pmemd.cuda`. |
| `LiGaMD3 receptor_mask must select one contiguous atom range` or `ligand_mask and receptor_mask overlap` | `receptor_mask` must exclude water, ions and the ligand. When changing `salt_type`, exclude that ion residue name too. |
| `Config error: ligand MOL2 charge does not match ligand_net_charge: X` | Match `ligand_net_charge` to the MOL2 charge sum or refit the charges. |
| `Config error: production steps must be divisible by production_segments` | Make `production_steps` a multiple of `production_segments`. |
| `GaMD statistics in config.toml: NAME (V) must be a multiple of averaging_interval_steps (A)` | Make all four statistics lengths multiples of `averaging_interval_steps`. |
| `Warning: averaging_interval_steps (A) is below 4 x topology atoms (...). ...` | The build continues. Choose the value using the averaging-window section below. |
| `Completed GaMD parameter preparation is required for production: ...` | Finish preparation with `--preparation-only` or a full `run.sh` before `--production-only`. |
| `Previous production segment is incomplete: work/00N` | The segment before START in `--segments START-END` is not complete. Run the earlier segment first. |

See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state, reruns after failure and concurrent-run protection.
