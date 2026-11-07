# Soluble-protein MD template / 수용성 단백질 MD template

## 한국어

사용자가 준비한 protein PDB를 선택한 protein–water compatibility pair의
explicit solvent에서 conventional MD로 계산합니다.
기본 config는 14 Å solute-to-box-edge distance, 0.15 M salt, 500 ps heating,
1 ns NPT equilibration과 10×10 ns production을 사용합니다.

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다. 필요한 program은
[상위 README](../README.md#준비-사항)에 있습니다. 사용자가 직접 실행하는 파일은
이 directory의 root에 있습니다. `helpers/`는 `build.sh` 또는 `run.sh`가 자동 호출하는
내부 code이며 직접 실행하지 않습니다.

### 실행

```bash
./download.sh 1UBQ
# Review and process structure/1UBQ.pdb before building.
./build.sh structure/1UBQ.pdb
./run.sh --dry-run
./run.sh
```

`download.sh`는 RCSB PDB를 `structure/`에 받으며 구조를 수정하지 않습니다. PDB atom
record를 확인한 뒤에만 최종 파일로 교체합니다. Protonation, alternate location,
missing residue/atom, crystal water와 biological assembly는 사용자가 결정합니다.

`build.sh`는 먼저 water 수를 세어 150 mM에 가까운 salt formula-unit 수를 계산한 뒤
neutralization과 salt addition을 포함한 최종 topology를 만듭니다.

`run.sh`는 minimization 두 단계, heating, equilibration과 production segment를
실행합니다. Equilibration은 `work/heat.rst7`을 initial coordinate file과 positional
restraint의 `-ref` input으로 함께 읽습니다.

`AMBER_ENGINE`이 설정되어 있으면 이를 사용하며, 없으면 `work/resolved_config.toml`의
`run.engine`을 읽습니다. 허용하는 executable 이름은 `pmemd.cuda`, `pmemd`, `sander`이며
설치 경로를 지정할 수 있습니다. 빈 override나 지원하지 않는 executable은 기본값으로
대체하지 않고 error로 중단합니다.

실행 상태, 실패 후 재실행, 동시 실행 보호와 build 임시 directory는
[GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

### 주요 output

| 파일 | 내용 |
| --- | --- |
| `work/system.parm7`, `system.rst7`, `system.pdb` | Build가 만든 topology와 initial coordinate file |
| `work/resolved_config.toml` | 실제 적용값과 salt formula-unit 수 |
| `work/leap.log` | Final LEaP log |
| `work/*.out`, `*.rst7`, `*.nc` | Minimization부터 equilibration까지의 stage output |
| `work/production.*` 또는 `work/NNN/production.*` | Production segment output |

첫 실행에서 production segment가 하나이면 output을 `work/`에 직접 저장합니다. 여러
개이면 `work/001`, `work/002` 순서로 저장합니다. 처음 numbered layout으로 실행했다면
segment 수를 줄여도 첫 output은 `work/001/`에 유지합니다. 한 segment를 root
`work/production.*`로 완료한 뒤 segment 수를 늘렸다면 첫 output은 그대로 두고 후속
output만 `work/002/`, `work/003/`에 생성합니다.

### Config 선택값

`config.toml`의 계산 길이는 MD steps로 입력합니다. 2 fs timestep에서 기본
heating 250,000 steps는 500 ps, equilibration 500,000 steps는 1 ns,
production 50,000,000 steps는 100 ns입니다.

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NVT`, `NPT` | `NPT` | Equilibration의 `ntb`와 `ntp`를 설정합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `pressure_coupling` | `isotropic`, `anisotropic` | `isotropic` | NPT stage에서 각각 `ntp=1`, `ntp=2`를 사용합니다. 다른 값은 build를 중단합니다. |
| `timestep` | 2.0 fs 이하 | `2.0` | AMBER `dt`(ps)로 기록합니다. Hydrogen mass repartitioning이 없으므로 2 fs보다 크면 build가 중단됩니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | Heating의 seed입니다. 이후 stage는 `ig=-1`로 실행할 때마다 새 seed를 사용합니다. |

### 숫자 option

| Key | 기본값 | Unit | 적용 stage | 값을 바꾸면 |
| --- | ---: | --- | --- | --- |
| `solute_box_distance` | 14.0 | Å | Build | Solute와 box 경계 사이 water 두께가 바뀝니다. 키우면 atom 수와 계산량이 늘어납니다. |
| `salt_concentration` | 150.0 | mM | Build | Salt formula unit 수 = round(water 수 × 농도(M) / 55.5)입니다. Neutralization ion은 따로 추가합니다. |
| `temperature` | 300.0 | K | Heating 목표, equilibration, production | `temp0`를 바꿉니다. |
| `pressure` | 1.0 | bar | NPT stage | `pres0`를 바꿉니다. |
| `minimization_steps` | 5000 | cycle | 두 minimization | `maxcyc`를 바꿉니다. |
| `minimization_steepest_steps` | 2500 | cycle | 두 minimization | `ncyc`입니다. 이 수만큼 steepest descent 뒤 conjugate gradient로 바꿉니다. `minimization_steps`보다 클 수 없습니다. |
| `heating_initial_temperature` | 20.0 | K | Heating | `tempi`와 `TEMP0` ramp 시작값입니다. `temperature`보다 클 수 없습니다. |
| `heating_steps` | 250000 | step | Heating | Ramp 길이입니다(2 fs에서 500 ps). |
| `equilibration_steps` | 500000 | step | Equilibration | Restrained NPT 길이입니다(1 ns). |
| `production_steps` | 50000000 | step | Production 전체 | 총 production 길이입니다(100 ns). `production_segments`로 나누어떨어져야 합니다. |
| `production_segments` | 10 | 개 | Production | Engine 실행 수입니다. Segment마다 `production_steps / production_segments` steps를 계산합니다. |
| `trajectory_interval_steps` | 5000 | step | Heating, equilibration, production | `ntwx`입니다. 기본값은 10 ps마다 1 frame, segment당 1,000 frame입니다. |
| `energy_interval_steps` | 5000 | step | Heating, equilibration, production | `ntpr`(energy 출력 간격)입니다. |
| `restart_interval_steps` | 5000 | step | Heating, equilibration, production | `ntwr`(restart 기록 간격)입니다. |

Config에 없는 고정값은 positional restraint 10(solvent minimization) → 5(heating) →
1(equilibration) kcal·mol⁻¹·Å⁻², `cut=10.0` Å, `gamma_ln=1.0` ps⁻¹, `taup=2.0` ps입니다.

기본값에서 engine 실행은 minimization 2회, heating, equilibration, production 10회로
14회이고 dynamics는 0.5 + 1 + 100 = 101.5 ns입니다. 각 실행은 `pmemd.cuda` process
하나가 GPU 하나로 계산하며 segment는 차례로 실행합니다. 실행 시간은 GPU와 atom 수에
따라 달라집니다. 전체 실행이 끝나면 `Production segments: work/001 through work/010`이
출력됩니다. Segment가 하나이면 `Production output: work/production.out`입니다.

## English

This template runs a user-prepared protein PDB in explicit solvent with the
selected protein–water compatibility pair. The default uses a 14 Å
solute-to-box-edge distance, approximately 0.15 M salt, 500 ps heating, 1 ns NPT
equilibration, and ten 10 ns production segments.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it. Required
programs are listed in the [parent README](../README.md#prerequisites). User-facing
entry points are in this directory root. `helpers/` contains internal code called
automatically by `build.sh` or `run.sh`; do not run it directly.

### Running

```bash
./download.sh 1UBQ
# Review and process structure/1UBQ.pdb before building.
./build.sh structure/1UBQ.pdb
./run.sh --dry-run
./run.sh
```

`download.sh` retrieves the RCSB PDB into `structure/` without modifying it and
replaces the final file only after checking its atom records. Review
protonation, alternate locations, missing atoms or residues, crystallographic
waters, and the biological assembly yourself.

`build.sh` first counts waters, estimates the number of salt formula units for
about 150 mM, and then generates the neutralized final topology with the salt.

`run.sh` runs two minimizations, heating, equilibration, and the production
segments. Equilibration reads `work/heat.rst7` as both the initial coordinate
file and the positional-restraint `-ref` input.

`AMBER_ENGINE` overrides `run.engine` in `work/resolved_config.toml`. Accepted
executable names are `pmemd.cuda`, `pmemd`, and `sander`; installation paths are
accepted. Empty overrides and unsupported executables fail instead of falling back
to a default.

See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state, reruns after failure,
concurrent-run protection, and the temporary build directory.

### Main outputs

| File | Content |
| --- | --- |
| `work/system.parm7`, `system.rst7`, `system.pdb` | Topology and initial coordinate file from the build |
| `work/resolved_config.toml` | Resolved values and salt formula-unit count |
| `work/leap.log` | Final LEaP log |
| `work/*.out`, `*.rst7`, `*.nc` | Stage outputs from minimization through equilibration |
| `work/production.*` or `work/NNN/production.*` | Production segment outputs |

On the first run, a single production segment is stored directly under `work/`;
multiple segments use `work/001`, `work/002`, and so on. If the first run used
numbered directories, reducing the count retains the first output under
`work/001/`. If one segment completed as `work/production.*`, increasing the
segment count keeps that output and writes later outputs under `work/002/`,
`work/003/`, etc.

### Config choices

Run lengths in `config.toml` are specified as MD steps. At the default 2 fs
timestep, 250,000 heating steps are 500 ps, 500,000 equilibration steps are
1 ns, and 50,000,000 production steps are 100 ns.

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NVT`, `NPT` | `NPT` | Sets equilibration `ntb` and `ntp`. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Sets production `ntb` and `ntp`. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `pressure_coupling` | `isotropic`, `anisotropic` | `isotropic` | NPT stages use `ntp=1` or `ntp=2`, respectively. Other values stop the build. |
| `timestep` | 2.0 fs or less | `2.0` | Written as AMBER `dt` in ps. Values above 2 fs stop the build because hydrogen masses are not repartitioned. |
| `random_seed` | `"random"` or a positive integer | `"random"` | Sets the heating seed; later stages use `ig=-1` and receive a new seed per invocation. |

### Numeric options

| Key | Default | Unit | Stage | Effect of changing it |
| --- | ---: | --- | --- | --- |
| `solute_box_distance` | 14.0 | Å | Build | Water thickness between the solute and box edge; larger values add atoms and cost. |
| `salt_concentration` | 150.0 | mM | Build | Salt formula units = round(water count × concentration (M) / 55.5); neutralizing ions are added separately. |
| `temperature` | 300.0 | K | Heating target, equilibration, production | Sets `temp0`. |
| `pressure` | 1.0 | bar | NPT stages | Sets `pres0`. |
| `minimization_steps` | 5000 | cycles | Both minimizations | Sets `maxcyc`. |
| `minimization_steepest_steps` | 2500 | cycles | Both minimizations | Sets `ncyc`: steepest descent for this many cycles, then conjugate gradient. Cannot exceed `minimization_steps`. |
| `heating_initial_temperature` | 20.0 | K | Heating | `tempi` and the start of the `TEMP0` ramp; cannot exceed `temperature`. |
| `heating_steps` | 250000 | steps | Heating | Ramp length (500 ps at 2 fs). |
| `equilibration_steps` | 500000 | steps | Equilibration | Restrained NPT length (1 ns). |
| `production_steps` | 50000000 | steps | All production | Total production length (100 ns); must be divisible by `production_segments`. |
| `production_segments` | 10 | count | Production | Number of engine runs; each computes `production_steps / production_segments` steps. |
| `trajectory_interval_steps` | 5000 | steps | Heating, equilibration, production | Sets `ntwx`; the default writes one frame per 10 ps, 1,000 frames per segment. |
| `energy_interval_steps` | 5000 | steps | Heating, equilibration, production | Sets `ntpr` (energy output interval). |
| `restart_interval_steps` | 5000 | steps | Heating, equilibration, production | Sets `ntwr` (restart write interval). |

Fixed values outside the config are positional restraints of 10 (solvent
minimization) → 5 (heating) → 1 (equilibration) kcal·mol⁻¹·Å⁻², `cut=10.0` Å,
`gamma_ln=1.0` ps⁻¹, and `taup=2.0` ps.

With the defaults, the engine runs 14 times (two minimizations, heating,
equilibration, and ten production segments) for 0.5 + 1 + 100 = 101.5 ns of
dynamics. Each run is one `pmemd.cuda` process on one GPU, and segments run in
order. Run time depends on the GPU and the atom count. A full run ends with
`Production segments: work/001 through work/010`; a single segment prints
`Production output: work/production.out`.
