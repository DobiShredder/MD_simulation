# Pep-GaMD template

## 한국어

`igamd=15`로 peptide potential과 나머지 system potential에 dual boost를
적용합니다. Conventional MD 뒤에 GaMD parameter preparation을 실행합니다.
`gamd_prepare.gamd.rst`에서 시작한 GaMD state는 각 production segment의
`production.gamd.rst`로 이어집니다. Peptide-selective boost는 이 directory의 고정
method이며 별도 config mode가 아닙니다. Amber 26 serial `pmemd.cuda`가 필요합니다.

### 필요한 input

- `build.sh`에 넘길 reviewed complex PDB
- Boost 대상 peptide를 지정하는 `config.toml`의 `peptide_mask`. 기본값이 비어 있어 build 전에 지정해야 합니다.

Build가 `peptide_mask`의 실제 atom selection을 확인합니다.

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

필요한 program과 기본 계산량은 [GaMD templates README](../README.md#필요한-program)를
참고합니다.

### 실행

```bash
./build.sh prepared_complex.pdb
./run.sh --dry-run
./run.sh
```

### 파일 역할

| File | 역할 |
| --- | --- |
| `download.sh` | `download.sh PDB_ID`로 source complex를 RCSB에서 받아 atom record를 확인한 뒤 저장 |
| `config.toml` | Build, MD 길이와 GaMD 통계 parameter |
| `build.sh` | Peptide mask 검증, topology와 Pep-GaMD input 생성 |
| `run.sh` | Minimization부터 segmented production까지 실행 |
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
| `./build.sh` | `AMBER topology and restart: work/system.parm7, work/system.rst7` | `work/inputs/gamd_prepare.in`, `work/inputs/production.in`, `work/resolved_config.toml`의 `[gamd]` |
| `./run.sh --preparation-only` | `GaMD preparation output: work/gamd_prepare.rst7 and work/gamd_prepare.gamd.rst` | `work/gamd_prepare.gamd.log` |
| `./run.sh` | Segment마다 `Completed: production segment N/10 (work/00N)`, 마지막에 `GaMD production completed: work` | Segment별 `production.nc`, `production.gamd.log`, `production.gamd.rst`, `production.rst7` |

다음 단계는 segment별 boost distribution 확인입니다. 기준은
[GaMD templates README](../README.md#결과-해석)에 있습니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein과 peptide parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Conventional equilibration에 적용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NVT` | Pep-GaMD preparation과 production의 `ntb`와 `ntp`를 설정합니다. |
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

`sigma0P`와 `sigma0D`는 같은 이름의 AMBER keyword로 기록됩니다. `igamd=15`에서
`sigma0P`는 첫 번째 boost(peptide potential), `sigma0D`는 두 번째 boost(나머지
system potential)의 standard deviation 상한이며 기본값은 둘 다 6 kcal/mol입니다.

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
| `peptide_mask is empty in config.toml [gamd]. ...` | 기본값은 비어 있습니다. Build 전에 peptide residue를 AMBER mask로 지정합니다(예: `:58-65`). tleap은 input PDB의 residue 순서대로 1부터 번호를 매기며 PDB residue 번호는 쓰지 않습니다. |
| `peptide_mask does not select any atoms: ...` | Mask가 final topology에서 atom을 고르지 못했습니다. `work/system.parm7`이 이미 만들어졌으므로 `work`를 다른 이름으로 옮긴 뒤 mask를 고쳐 다시 build합니다. |
| `Engine configuration error (...): Unsupported engine '...'; expected: pmemd.cuda` | `AMBER_ENGINE` 또는 `run.engine`을 serial `pmemd.cuda`로 바꿉니다. |
| `Config error: production steps must be divisible by production_segments` | `production_steps`를 `production_segments`의 배수로 맞춥니다. |
| `GaMD statistics in config.toml: NAME (V) must be a multiple of averaging_interval_steps (A)` | 네 statistics 길이를 `averaging_interval_steps`의 배수로 맞춥니다. |
| `Warning: averaging_interval_steps (A) is below 4 x topology atoms (...). ...` | Build는 계속됩니다. 위 "Boost 상한과 averaging window" section을 보고 값을 정합니다. |
| `Completed GaMD parameter preparation is required for production: ...` | `--production-only` 전에 `--preparation-only` 또는 전체 `run.sh`로 preparation을 끝냅니다. |
| `Previous production segment is incomplete: work/00N` | `--segments START-END`의 START 앞 segment가 완료되지 않았습니다. 앞 segment부터 실행합니다. |

실행 상태, 실패 후 재실행, 동시 실행 보호는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

This template uses `igamd=15` to boost the peptide potential and the remaining
system potential. GaMD parameter preparation follows conventional MD. The GaMD
state starting from `gamd_prepare.gamd.rst` continues through each segment's
`production.gamd.rst`. The peptide-selective boost is fixed by this directory
and is not a config mode. Amber 26 serial `pmemd.cuda` is required.

### Required inputs

- A reviewed complex PDB passed to `build.sh`
- `peptide_mask` in `config.toml`, selecting the peptide to boost. It is empty by default and must be set before the build.

The build verifies that `peptide_mask` selects atoms.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

See the [GaMD templates README](../README.md#required-programs) for required
programs and the default computation.

### Run

```bash
./build.sh prepared_complex.pdb
./run.sh --dry-run
./run.sh
```

### File roles

| File | Role |
| --- | --- |
| `download.sh` | `download.sh PDB_ID` downloads a source complex from RCSB and saves it after checking atom records |
| `config.toml` | Build, MD length and GaMD statistics parameters |
| `build.sh` | Validates the peptide mask and creates the topology and Pep-GaMD inputs |
| `run.sh` | Runs minimization through segmented production |
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
| `./build.sh` | `AMBER topology and restart: work/system.parm7, work/system.rst7` | `work/inputs/gamd_prepare.in`, `work/inputs/production.in`, `[gamd]` in `work/resolved_config.toml` |
| `./run.sh --preparation-only` | `GaMD preparation output: work/gamd_prepare.rst7 and work/gamd_prepare.gamd.rst` | `work/gamd_prepare.gamd.log` |
| `./run.sh` | `Completed: production segment N/10 (work/00N)` per segment, then `GaMD production completed: work` | Each segment's `production.nc`, `production.gamd.log`, `production.gamd.rst`, `production.rst7` |

Next, check each segment's boost distribution with the criteria in the
[GaMD templates README](../README.md#interpreting-the-results).

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects protein and peptide parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to conventional equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NVT` | Sets `ntb` and `ntp` for Pep-GaMD preparation and production. |
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

`sigma0P` and `sigma0D` are written as the AMBER keywords of the same name. With
`igamd=15`, `sigma0P` limits the standard deviation of the first boost (peptide
potential) and `sigma0D` that of the second boost (remaining-system potential);
both default to 6 kcal/mol.

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
| `peptide_mask is empty in config.toml [gamd]. ...` | The default is empty. Set the peptide residues as an AMBER mask before building (for example `:58-65`). tleap numbers residues from 1 in input-PDB order, not by PDB residue number. |
| `peptide_mask does not select any atoms: ...` | The mask selects no atoms in the final topology. `work/system.parm7` already exists, so move `work` aside, fix the mask and build again. |
| `Engine configuration error (...): Unsupported engine '...'; expected: pmemd.cuda` | Set `AMBER_ENGINE` or `run.engine` to serial `pmemd.cuda`. |
| `Config error: production steps must be divisible by production_segments` | Make `production_steps` a multiple of `production_segments`. |
| `GaMD statistics in config.toml: NAME (V) must be a multiple of averaging_interval_steps (A)` | Make all four statistics lengths multiples of `averaging_interval_steps`. |
| `Warning: averaging_interval_steps (A) is below 4 x topology atoms (...). ...` | The build continues. Choose the value using the "Boost limits and averaging window" section above. |
| `Completed GaMD parameter preparation is required for production: ...` | Finish preparation with `--preparation-only` or a full `run.sh` before `--production-only`. |
| `Previous production segment is incomplete: work/00N` | The segment before START in `--segments START-END` is not complete. Run the earlier segment first. |

See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state, reruns after failure and concurrent-run protection.
