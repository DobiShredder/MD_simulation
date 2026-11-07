# Protein–ligand MD template / Protein–ligand MD template

## 한국어

사용자가 준비한 complex PDB와 RESP charge가 포함된 ligand MOL2로 conventional
MD를 구성합니다. Protein과 water는 지원되는 compatibility pair를 사용하고,
ligand parameter는 GAFF2를 유지합니다. 기본값은 14 Å OPC box, 0.15 M salt,
250,000-step(500 ps) heating, 500,000-step(1 ns) equilibration과
10×5,000,000-step(10×10 ns) production입니다.

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다. 필요한 program은
[상위 README](../README.md#준비-사항)에 있습니다. 사용자가 직접 실행하는 파일은
이 directory의 root에 있습니다. `helpers/`는 `build.sh` 또는 `run.sh`가 자동 호출하는
내부 code이며 직접 실행하지 않습니다.

### 필요한 input

`config.toml`에서 다음 경로와 chemical identity를 먼저 수정합니다.

```toml
ligand_residue_name = "LIG"
ligand_net_charge = 0
charge_method = "RESP"
ligand_mol2 = "inputs/ligand.mol2"
ligand_frcmod = "inputs/ligand.frcmod"
```

MOL2에는 RESP charge와 GAFF2 atom type이 이미 들어 있어야 합니다. 이 template는
Gaussian/ESP/RESP 계산이나 atom mapping을 자동으로 만들지 않습니다. Build는
MOL2 residue name과 net charge가 config 및 complex PDB와 일치하는지 검사합니다.

### 실행

```bash
./download.sh 3HTB
# Prepare the complex PDB and place reviewed ligand parameters under inputs/.
./build.sh structure/3HTB.pdb
./run.sh --dry-run
./run.sh
```

`download.sh`는 RCSB PDB를 `structure/`에 받으며 구조를 수정하지 않습니다. PDB atom
record를 확인한 뒤에만 최종 파일로 교체합니다.

`build.sh`는 water 수를 세는 first pass와 final pass에서 같은 `ligand.mol2`와
`ligand.frcmod`를 읽고, final pass 전에 parameter 내용이 바뀌었는지 검사합니다.

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

Build는 `work/system.parm7`, `system.rst7`, `system.pdb`, `resolved_config.toml`과
LEaP log를 만듭니다. Production segment가 하나이면 output을 `work/`에, 여러 개이면
`work/001`부터 저장합니다. 처음 numbered layout으로 실행했다면 segment 수를 줄여도 첫
output은 `work/001/`에 유지합니다. 한 segment를 root `work/production.*`로 완료한 뒤
segment 수를 늘렸다면 첫 output은 그대로 두고 후속 output만 `work/002/`, `work/003/`에
생성합니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `ligand_force_field` | `GAFF2`만 지원 | `GAFF2` | Ligand parameter 형식을 결정합니다. |
| `charge_method` | precharged `RESP` MOL2만 지원 | `RESP` | `ligand_mol2`의 RESP charge를 그대로 사용합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Equilibration의 pressure coupling을 활성화합니다. |
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
| `ligand_net_charge` | 0 | e | Build 검사 | MOL2 partial charge 합과 같아야 합니다. 다르면 build가 중단됩니다. |
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

### 자주 생기는 문제

공통 message는 [상위 README](../README.md#자주-생기는-문제)에 있습니다.

| Message | 조치 |
| --- | --- |
| `Config error: ParmEd is required to validate ligand parameters` | `requirements.txt`로 ParmEd를 설치합니다. |
| `Config error: ligand MOL2 residue must be LIG` | MOL2 residue name과 `ligand_residue_name`을 맞춥니다. |
| `Config error: complex PDB does not contain ligand residue LIG` | Complex PDB의 ligand residue name을 MOL2와 같게 고칩니다. |
| `Final build: ligand parameter changed between LEaP passes` | Build 중 `ligand_mol2`나 `ligand_frcmod`가 바뀌었습니다. 파일을 고정한 뒤 새 `WORK_DIR`에서 다시 build합니다. |

## English

This template builds conventional protein–ligand MD from a reviewed complex PDB
and a ligand MOL2 containing precomputed RESP charges and GAFF2 atom types.
Protein and water use a supported compatibility pair; the ligand keeps GAFF2.
The default run uses a 14 Å OPC box, approximately 0.15 M salt, 250,000-step
(500 ps) heating, 500,000-step (1 ns) equilibration, and ten 5,000,000-step
(10 ns) production segments at a 2 fs timestep.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it. Required
programs are listed in the [parent README](../README.md#prerequisites). User-facing
entry points are in this directory root. `helpers/` contains internal code called
automatically by `build.sh` or `run.sh`; do not run it directly.

### Required inputs

Set the ligand residue, integer net charge, MOL2 path, and frcmod path in
`config.toml` first.

```toml
ligand_residue_name = "LIG"
ligand_net_charge = 0
charge_method = "RESP"
ligand_mol2 = "inputs/ligand.mol2"
ligand_frcmod = "inputs/ligand.frcmod"
```

The MOL2 must already contain RESP charges and GAFF2 atom types. The template
does not perform quantum chemistry, ESP/RESP fitting, or atom mapping. The build
checks the MOL2 residue name and total charge against the config and verifies that
the complex PDB contains that residue.

### Running

```bash
./download.sh 3HTB
# Prepare the complex PDB and place reviewed ligand parameters under inputs/.
./build.sh structure/3HTB.pdb
./run.sh --dry-run
./run.sh
```

`download.sh` retrieves the RCSB PDB into `structure/` without modifying it and
replaces the final file only after checking its atom records.

`build.sh` reads the same `ligand.mol2` and `ligand.frcmod` in the water-count
first pass and the final pass, and checks that their contents have not changed
before the final pass.

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

The build writes `work/system.parm7`, `system.rst7`, `system.pdb`,
`resolved_config.toml`, and the LEaP logs. A single production segment is stored
under `work/`; multiple segments start at `work/001`. If the first run used
numbered directories, reducing the count retains the first output under
`work/001/`. If one segment completed as `work/production.*`, increasing the
segment count keeps that output and writes later outputs under `work/002/`,
`work/003/`, etc.

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `ligand_force_field` | `GAFF2` only | `GAFF2` | Selects the ligand parameter format. |
| `charge_method` | Precharged `RESP` MOL2 only | `RESP` | Uses the RESP charges already present in `ligand_mol2`. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Enables pressure coupling during equilibration. |
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
| `ligand_net_charge` | 0 | e | Build check | Must equal the summed MOL2 partial charges; otherwise the build stops. |
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

### Common problems

Shared messages are listed in the [parent README](../README.md#common-problems).

| Message | Action |
| --- | --- |
| `Config error: ParmEd is required to validate ligand parameters` | Install ParmEd from `requirements.txt`. |
| `Config error: ligand MOL2 residue must be LIG` | Make the MOL2 residue name match `ligand_residue_name`. |
| `Config error: complex PDB does not contain ligand residue LIG` | Rename the ligand residue in the complex PDB to match the MOL2. |
| `Final build: ligand parameter changed between LEaP passes` | `ligand_mol2` or `ligand_frcmod` changed during the build. Keep the files fixed and build again in a new `WORK_DIR`. |
