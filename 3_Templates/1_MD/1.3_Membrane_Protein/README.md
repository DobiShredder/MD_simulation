# Membrane-protein MD template / Membrane-protein MD template

## 한국어

Membrane-oriented protein PDB와 사용자가 준비한 equilibrated Lipid21 bilayer
patch를 조합해 membrane system을 만들고 conventional MD를 실행합니다. 기본값은
ff19SB/Lipid21/OPC, anisotropic Monte Carlo pressure coupling, 1 ns equilibration과
10×10 ns production segments입니다.

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다. 필요한 program은
[상위 README](../README.md#준비-사항)에 있습니다. 사용자가 직접 실행하는 파일은
이 directory의 root에 있습니다. `helpers/`는 `build.sh` 또는 `run.sh`가 자동 호출하는
내부 code이며 직접 실행하지 않습니다.

### 필요한 input

Protein orientation, protonation, pore water와 bound ion은 자동으로 결정하지 않습니다.
Input PDB는 OPM 좌표계처럼 membrane normal이 z축이고 bilayer 중심이 z=0이어야 합니다.
OPM의 `1/2 of bilayer thickness` REMARK는 읽을 수 있을 때 출력에만 사용하며, 없으면
warning을 출력하고 계속합니다.

`config.toml`에서 bilayer patch 경로와 조성을 지정합니다.

```toml
bilayer_composition = "POPC=90,POPE=5,CHOL=5"
popc_bilayer_gro = "inputs/POPC.gro"
pope_bilayer_gro = "inputs/POPE.gro"
cholesterol_bilayer_gro = "inputs/CHOL15.gro"
xy_padding = 20.0
water_padding = 25.0
```

Bilayer patch는 이 repository에서 재배포하지 않습니다. 각 coordinate file의
force-field naming과 출처를 확인한 뒤 config 경로에 둡니다.

### 실행

```bash
./download.sh 1K4C
# Prepare an oriented, protonated protein PDB and the three bilayer patches.
./build.sh structure/1K4C.pdb
./run.sh --dry-run
./run.sh
```

`download.sh`는 RCSB PDB를 `structure/`에 받으며 구조를 수정하지 않습니다. PDB atom
record를 확인한 뒤에만 최종 파일로 교체합니다.

`build.sh`는 자동 호출하는 `helpers/build_membrane.py`로 bilayer를 복제하고 protein
overlap을 제거한 뒤 ff19SB/Lipid21/OPC topology를 생성합니다. Salt pair 수는 packed
PDB의 WAT oxygen atom 수와 설정 농도로 계산합니다. Residue 번호가 반복되어도 water
count는 유지합니다. 반올림한 pair 수가 0이면 neutralization만 실행하고 bulk-salt 추가
command는 생성하지 않습니다.

`AMBER_ENGINE`이 설정되어 있으면 이를 사용하며, 없으면 `work/resolved_config.toml`의
`run.engine`을 읽습니다. 허용하는 executable 이름은 `pmemd.cuda`, `pmemd`, `sander`이며
설치 경로를 지정할 수 있습니다. 빈 override나 지원하지 않는 executable은 기본값으로
대체하지 않고 error로 중단합니다.

실행 상태, 실패 후 재실행과 동시 실행 보호는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을
참고합니다.

### 계산 단계와 restraint

Water와 bulk ions는 첫 minimization부터 움직입니다. Lipid heavy-atom restraint는
첫 minimization 뒤에 풀고, protein restraint는 heavy atoms → backbone → 전체 해제
순서로 줄입니다. Sampling은 conventional MD이며 restraint는 preparation에만 적용합니다.

| Generated input | 단계 | Positional restraint | 기본 길이 |
| --- | --- | --- | --- |
| `work/inputs/min-solvent.in` | Solvent minimization | Protein + lipid heavy atoms, 10 kcal·mol⁻¹·Å⁻² | 10,000 cycles |
| `work/inputs/min-lipid.in` | Lipid/environment minimization | Protein heavy atoms, 10 kcal·mol⁻¹·Å⁻² | 10,000 cycles |
| `work/inputs/heat.in` | NVT heating, 20→300 K | Protein heavy atoms, 5 kcal·mol⁻¹·Å⁻² | 500 ps |
| `work/inputs/equilibrate-heavy.in` | NPT equilibration | Protein heavy atoms, 1 kcal·mol⁻¹·Å⁻² | 400 ps |
| `work/inputs/equilibrate-backbone.in` | NPT equilibration | Protein backbone, 1 kcal·mol⁻¹·Å⁻² | 400 ps |
| `work/inputs/equilibrate.in` | NPT equilibration | 없음 (`ntr=0`) | 200 ps |
| `work/inputs/production.in` | Production segment | 없음 (`ntr=0`) | 10 ns × 10 |

Heavy atoms는 protein selection에 `!@H=`를 적용합니다. Backbone은 같은 protein
selection에 `@N,CA,C,O,OXT`를 적용하므로 lipid·water의 `O`는 제외합니다.
Restrained stage는 `&ewald`의 `netfrc=0`으로 인위적인 net-force 제거를 끕니다.

두 minimization은 최초 `system.rst7`을 `-ref`로 사용합니다. Heating은
`min-lipid.rst7`에서 velocity를 생성합니다(`irest=0`, `ntx=1`). 세 equilibration은
이전 stage의 restart를 순서대로 읽어 원자 좌표와 velocity를 이어받습니다
(`irest=1`, `ntx=5`). Heavy-atom과 backbone stage는 `work/heat.rst7`을 같은 restraint
reference로 쓰고, 마지막 unrestrained stage의 `equilibrate.rst7`이 production의
initial restart가 됩니다.

### 주요 output

Stage별 `.out`, `.rst7`, dynamics의 `.nc`와 `.info`는 `work/`에 남습니다. Build는
`work/system.parm7`, `system.rst7`, `system.pdb`, `resolved_config.toml`과 `leap.log`를 만듭니다.
Production segment가 하나이면 output을 `work/`에, 여러 개이면 `work/001`부터
저장합니다. 처음 numbered layout으로 실행했다면 segment 수를 줄여도 첫 output은
`work/001/`에 유지합니다. 한 segment를 root `work/production.*`로 완료한 뒤 segment
수를 늘렸다면 첫 output은 그대로 두고 후속 output만 `work/002/`, `work/003/`에
생성합니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff19SB`만 지원 | `ff19SB` | Protein parameter를 선택합니다. |
| `lipid_force_field` | `Lipid21`만 지원 | `Lipid21` | Bilayer lipid parameter를 선택합니다. |
| `water_model` | `OPC`만 지원 | `OPC` | Lipid21 system의 water와 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`만 지원 | `rectangular` | Membrane builder가 rectangular periodic box를 만듭니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `KCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Membrane equilibration에 pressure coupling을 사용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Production의 `ntb`와 `ntp`를 설정합니다. |
| `pressure_coupling` | `anisotropic`만 지원 | `anisotropic` | Membrane box 축의 pressure scaling을 분리합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `timestep` | 2.0 fs 이하 | `2.0` | AMBER `dt`(ps)로 기록합니다. Hydrogen mass repartitioning이 없으므로 2 fs보다 크면 build가 중단됩니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | Heating의 seed입니다. 이후 stage는 `ig=-1`로 실행할 때마다 새 seed를 사용합니다. |
| `cutoff` | `lj_force_switch`보다 큰 값(Å) | `12.0` | 모든 stage의 `cut`입니다. Box 최소 변의 절반이 `cut` + 2 Å(pair-list skin) 이하이면 build가 중단됩니다. |
| `lj_force_switch` | `cutoff`보다 작은 양수(Å) | `10.0` | 모든 stage의 `fswitch`입니다. LJ force를 이 거리부터 `cut`까지 0으로 줄입니다. |

Amber26 manual §3.6은 MC barostat와 hard LJ cutoff 조합이 lipid bilayer를 변형할 수
있어 LJ force switch를 권장합니다(Gomez et al., *J. Comput. Chem.* 2022). Sander에서는
`fswitch`가 `vdwmeth=0`(long-range dispersion correction 없음)으로 바뀝니다. Force
switch만으로 약 20% 느려지고(manual) 12 Å cutoff는 계산량을 더 늘립니다. `pmemd.cuda`
실행은 미검증입니다.

이 leaf는 Lipid21 membrane build와 함께 검증한 `ff19SB + OPC`만 지원합니다.
`ff99SB-ILDN + TIP3P`와 `ff14SB + TIP3P`는 membrane/Lipid21 조합을 별도로
검증하지 않았으므로 config validation에서 거부합니다.

`protein_restraint_mask`는 protein residue만, `lipid_restraint_mask`는 lipid
residue만 선택하도록 topology와 대조합니다. 기본 protein mask는 Lipid21의
`PA,PC,PE,OL,CHL`과 water·bulk ions를 제외합니다. 별도 ligand나 다른 lipid가 있으면
이 selection을 수정합니다. Bound ion/water restraint는 자동으로 추가하지 않습니다.

`equilibration_steps`는 세 stage의 합계입니다. `equilibration_heavy_steps`와
`equilibration_backbone_steps`를 지정하고, 남은 steps를 unrestrained stage에
사용합니다. 각 stage에는 1 step 이상이 필요합니다. 두 stage 값을 생략한 config는
각각 총 steps의 40%를 사용합니다. 생성된 값은 `resolved_config.toml`에 기록합니다.

1 ns equilibration은 기본 실행 길이이며 membrane 수렴을 보장하지 않습니다. Membrane
area·두께와 protein 상태를 확인하면서 system에 맞게 equilibration을 늘립니다.

### 숫자 option

`cutoff`, `lj_force_switch`와 equilibration 분할 key는 위에서 설명했습니다.

| Key | 기본값 | Unit | 적용 stage | 값을 바꾸면 |
| --- | ---: | --- | --- | --- |
| `xy_padding` | 20.0 | Å | Build | Protein x·y 경계와 box 경계 사이 최소 거리입니다. 키우면 lipid 수와 atom 수가 늘어납니다. |
| `water_padding` | 25.0 | Å | Build | Protein z 경계와 box 경계 사이 최소 거리입니다. 키우면 water 층이 두꺼워집니다. |
| `protein_lipid_distance` | 2.0 | Å | Build | Protein heavy atom과 이 거리 안에 든 lipid를 분자 단위로 제거합니다. 키우면 protein 주변 빈 공간이 커집니다. |
| `salt_concentration` | 150.0 | mM | Build | Salt pair 수 = round(WAT 수 × 농도(M) / 55.5)입니다. |
| `temperature` | 300.0 | K | Heating 목표, equilibration, production | `temp0`를 바꿉니다. |
| `pressure` | 1.0 | bar | NPT stage | `pres0`를 바꿉니다. |
| `minimization_steps` | 10000 | cycle | 두 minimization | `maxcyc`를 바꿉니다. |
| `minimization_steepest_steps` | 5000 | cycle | 사용 안 함 | 두 minimization은 `ntmin=2`(steepest descent만 사용)라 적용되지 않습니다(Amber26 manual `ntmin`). 공통 config 검사 때문에 key만 남아 있습니다. |
| `heating_initial_temperature` | 20.0 | K | Heating | `tempi`와 `TEMP0` ramp 시작값입니다. |
| `heating_steps` | 250000 | step | Heating | Ramp 길이입니다(2 fs에서 500 ps). |
| `production_steps` | 50000000 | step | Production 전체 | 총 production 길이입니다(100 ns). `production_segments`로 나누어떨어져야 합니다. |
| `production_segments` | 10 | 개 | Production | Engine 실행 수입니다. |
| `trajectory_interval_steps` | 5000 | step | Heating 이후 dynamics | `ntwx`입니다. 기본값은 10 ps마다 1 frame, segment당 1,000 frame입니다. |
| `energy_interval_steps` | 5000 | step | Heating 이후 dynamics | `ntpr`입니다. |
| `restart_interval_steps` | 5000 | step | Heating 이후 dynamics | `ntwr`입니다. |

`gamma_ln=1.0` ps⁻¹와 `taup=2.0` ps는 config에 없는 고정값입니다.

기본값에서 engine 실행은 minimization 2회, heating, equilibration 3회, production
10회로 16회이고 dynamics는 0.5 + 1 + 100 = 101.5 ns입니다. 각 실행은 `pmemd.cuda`
process 하나가 GPU 하나로 계산하며 순서대로 진행합니다. 실행 시간은 GPU와 atom 수에
따라 달라집니다. 전체 실행이 끝나면 `Production segments: work/001 through work/010`이
출력됩니다. 결과 판단은 tutorial [3_Simulation README](../../../1_Simulation/1_MD/1.3_Membrane_Protein/3_Simulation/README.md#주요-output과-완료-확인)의
membrane 확인 항목을 참고합니다.

### 자주 생기는 문제

공통 message는 [상위 README](../README.md#자주-생기는-문제)에 있습니다.

| Message | 조치 |
| --- | --- |
| `NumPy is required.` | `requirements.txt`로 NumPy를 설치합니다. |
| `Membrane packing failed (helpers/build_membrane.py). See work/build_membrane.log` | Log의 마지막 error를 봅니다. Cholesterol 배치 실패는 `xy_padding`을 늘리거나 cholesterol 비율을 줄입니다. |
| `Config error: box ... is too small for cutoff=...` | Box 최소 변의 절반이 `cutoff` + 2 Å보다 커지도록 padding을 늘리거나 `cutoff`를 줄입니다. |
| `Run preflight: staged membrane input missing` | 이 template의 `build.sh`로 만든 `WORK_DIR`이 아닙니다. 새 `WORK_DIR`에서 build합니다. |

## English

This template combines a membrane-oriented protein PDB with user-supplied,
equilibrated Lipid21 bilayer patches and runs conventional MD. The default uses
ff19SB/Lipid21/OPC, anisotropic Monte Carlo pressure coupling, 1 ns
equilibration, and ten 10 ns production segments.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it. Required
programs are listed in the [parent README](../README.md#prerequisites). User-facing
entry points are in this directory root. `helpers/` contains internal code called
automatically by `build.sh` or `run.sh`; do not run it directly.

### Required inputs

The workflow does not choose orientation, protonation, pore waters, or bound
ions automatically. The PDB must be aligned with the membrane normal along z and
the bilayer center at z=0, as in OPM coordinates. The OPM
`1/2 of bilayer thickness` REMARK is only printed when present; without it the
builder prints a warning and continues.

Set the POPC, POPE, and cholesterol patch paths, composition, xy padding, and
water padding in `config.toml`.

```toml
bilayer_composition = "POPC=90,POPE=5,CHOL=5"
popc_bilayer_gro = "inputs/POPC.gro"
pope_bilayer_gro = "inputs/POPE.gro"
cholesterol_bilayer_gro = "inputs/CHOL15.gro"
xy_padding = 20.0
water_padding = 25.0
```

Bilayer coordinate patches are not redistributed by this repository. Check the
force-field naming and source of each file before placing it at the configured
path.

### Running

```bash
./download.sh 1K4C
# Prepare an oriented, protonated protein PDB and the three bilayer patches.
./build.sh structure/1K4C.pdb
./run.sh --dry-run
./run.sh
```

`download.sh` retrieves the RCSB PDB into `structure/` without modifying it and
replaces the final file only after checking its atom records.

`build.sh` calls `helpers/build_membrane.py` to replicate the bilayer and remove
protein overlaps, then builds the ff19SB/Lipid21/OPC topology. Salt pairs use the
packed PDB WAT oxygen count and the configured concentration. Repeated residue
numbers do not reduce the water count. A rounded pair count of zero keeps
neutralization and omits the bulk-salt command.

`AMBER_ENGINE` overrides `run.engine` in `work/resolved_config.toml`. Accepted
executable names are `pmemd.cuda`, `pmemd`, and `sander`; installation paths are
accepted. Empty overrides and unsupported executables fail instead of falling back
to a default.

See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state, reruns after failure and
concurrent-run protection.

### Stages and restraints

Water and bulk ions move from the first minimization. Lipid heavy-atom restraints
end after that stage. Protein restraints are narrowed from heavy atoms to backbone
to none during equilibration. Sampling remains conventional MD; these restraints
apply during preparation only.

| Generated input | Stage | Positional restraint | Default length |
| --- | --- | --- | --- |
| `work/inputs/min-solvent.in` | Solvent minimization | Protein + lipid heavy atoms, 10 kcal·mol⁻¹·Å⁻² | 10,000 cycles |
| `work/inputs/min-lipid.in` | Lipid/environment minimization | Protein heavy atoms, 10 kcal·mol⁻¹·Å⁻² | 10,000 cycles |
| `work/inputs/heat.in` | NVT heating, 20→300 K | Protein heavy atoms, 5 kcal·mol⁻¹·Å⁻² | 500 ps |
| `work/inputs/equilibrate-heavy.in` | NPT equilibration | Protein heavy atoms, 1 kcal·mol⁻¹·Å⁻² | 400 ps |
| `work/inputs/equilibrate-backbone.in` | NPT equilibration | Protein backbone, 1 kcal·mol⁻¹·Å⁻² | 400 ps |
| `work/inputs/equilibrate.in` | NPT equilibration | None (`ntr=0`) | 200 ps |
| `work/inputs/production.in` | Production segment | None (`ntr=0`) | 10 ns × 10 |

Heavy atoms use the protein selection intersected with `!@H=`. Backbone atoms
use the same selection intersected with `@N,CA,C,O,OXT`; lipid/water atoms named
`O` are excluded. Restrained stages set `netfrc=0` in `&ewald` to disable
artificial net-force removal.

Both minimizations reference the initial `system.rst7`. Heating generates
velocities from `min-lipid.rst7` (`irest=0`, `ntx=1`). All three equilibration
stages inherit coordinates and velocities from their predecessor restart
(`irest=1`, `ntx=5`). Heavy-atom and backbone stages share the `work/heat.rst7`
restraint reference. The final unrestrained `equilibrate.rst7` starts production.

### Main outputs

Stage `.out`, `.rst7`, dynamics `.nc`, and `.info` outputs remain in `work/`. The
build writes `work/system.parm7`, `system.rst7`, `system.pdb`, `resolved_config.toml`, and
`leap.log`. A single production segment is stored under `work/`; multiple
segments start at `work/001`. If the first run used numbered directories,
reducing the count retains the first output under `work/001/`. If one segment
completed as `work/production.*`, increasing the segment count keeps that output
and writes later outputs under `work/002/`, `work/003/`, etc.

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff19SB` only | `ff19SB` | Selects the protein parameters. |
| `lipid_force_field` | `Lipid21` only | `Lipid21` | Selects the bilayer lipid parameters. |
| `water_model` | `OPC` only | `OPC` | Selects water and ion parameters for the Lipid21 system. |
| `box_shape` | `rectangular` only | `rectangular` | The membrane builder creates a rectangular periodic box. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `KCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Uses pressure coupling during membrane equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Sets production `ntb` and `ntp`. |
| `pressure_coupling` | `anisotropic` only | `anisotropic` | Separates pressure scaling along the membrane box axes. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `timestep` | 2.0 fs or less | `2.0` | Written as AMBER `dt` in ps. Values above 2 fs stop the build because hydrogen masses are not repartitioned. |
| `random_seed` | `"random"` or a positive integer | `"random"` | Sets the heating seed; later stages use `ig=-1` and receive a new seed per invocation. |
| `cutoff` | Larger than `lj_force_switch` (Å) | `12.0` | `cut` for every stage. The build stops if half of the shortest box edge is not larger than `cut` + 2 Å (pair-list skin). |
| `lj_force_switch` | Positive and smaller than `cutoff` (Å) | `10.0` | `fswitch` for every stage; the LJ force goes to zero between this distance and `cut`. |

Amber26 manual §3.6 recommends an LJ force switch because the MC barostat with a
hard LJ cutoff can deform lipid bilayers (Gomez et al., *J. Comput. Chem.* 2022).
In sander, `fswitch` switches to `vdwmeth=0` (no long-range dispersion correction).
The force switch alone costs about 20% (manual), and the 12 Å cutoff adds more.
Not yet run with `pmemd.cuda`.

This leaf supports only `ff19SB + OPC`, the pair validated with the Lipid21
membrane build. Config validation rejects `ff99SB-ILDN + TIP3P` and
`ff14SB + TIP3P` because those membrane/Lipid21 combinations have not been
validated here.

Check `protein_restraint_mask` against the protein residues and
`lipid_restraint_mask` against the lipids. The default protein mask excludes
Lipid21 `PA,PC,PE,OL,CHL`, water, and bulk ions. Update it for additional ligands
or lipid types. Bound-ion/water restraints are not added automatically.

`equilibration_steps` is the total across all three stages. Set
`equilibration_heavy_steps` and `equilibration_backbone_steps`; the remainder is
unrestrained. Every stage needs at least one step. If the two stage settings are
omitted, each defaults to 40% of the total. Resolved step counts are recorded in
`resolved_config.toml`.

The default 1 ns equilibration does not establish membrane convergence. Extend
equilibration based on membrane area, thickness, and protein-state checks.

### Numeric options

`cutoff`, `lj_force_switch`, and the equilibration split keys are described
above.

| Key | Default | Unit | Stage | Effect of changing it |
| --- | ---: | --- | --- | --- |
| `xy_padding` | 20.0 | Å | Build | Minimum distance between the protein x/y bounds and the box edges; larger values add lipids and atoms. |
| `water_padding` | 25.0 | Å | Build | Minimum distance between the protein z bounds and the box edges; larger values thicken the water layers. |
| `protein_lipid_distance` | 2.0 | Å | Build | Lipids within this distance of protein heavy atoms are removed as whole molecules; larger values leave more empty space around the protein. |
| `salt_concentration` | 150.0 | mM | Build | Salt pairs = round(WAT count × concentration (M) / 55.5). |
| `temperature` | 300.0 | K | Heating target, equilibration, production | Sets `temp0`. |
| `pressure` | 1.0 | bar | NPT stages | Sets `pres0`. |
| `minimization_steps` | 10000 | cycles | Both minimizations | Sets `maxcyc`. |
| `minimization_steepest_steps` | 5000 | cycles | Not used | Both minimizations use `ntmin=2` (steepest descent only), so it is not applied (Amber26 manual, `ntmin`). The key remains for the shared config checker. |
| `heating_initial_temperature` | 20.0 | K | Heating | `tempi` and the start of the `TEMP0` ramp. |
| `heating_steps` | 250000 | steps | Heating | Ramp length (500 ps at 2 fs). |
| `production_steps` | 50000000 | steps | All production | Total production length (100 ns); must be divisible by `production_segments`. |
| `production_segments` | 10 | count | Production | Number of engine runs. |
| `trajectory_interval_steps` | 5000 | steps | Dynamics from heating on | Sets `ntwx`; the default writes one frame per 10 ps, 1,000 frames per segment. |
| `energy_interval_steps` | 5000 | steps | Dynamics from heating on | Sets `ntpr`. |
| `restart_interval_steps` | 5000 | steps | Dynamics from heating on | Sets `ntwr`. |

`gamma_ln=1.0` ps⁻¹ and `taup=2.0` ps are fixed values outside the config.

With the defaults, the engine runs 16 times (two minimizations, heating, three
equilibrations, and ten production segments) for 0.5 + 1 + 100 = 101.5 ns of
dynamics. Each run is one `pmemd.cuda` process on one GPU, in order. Run time
depends on the GPU and the atom count. A full run ends with
`Production segments: work/001 through work/010`. For judging the result, see
the membrane checks in the tutorial
[3_Simulation README](../../../1_Simulation/1_MD/1.3_Membrane_Protein/3_Simulation/README.md#main-outputs-and-completion-check).

### Common problems

Shared messages are listed in the [parent README](../README.md#common-problems).

| Message | Action |
| --- | --- |
| `NumPy is required.` | Install NumPy from `requirements.txt`. |
| `Membrane packing failed (helpers/build_membrane.py). See work/build_membrane.log` | Read the last error in the log. For cholesterol-placement failures, increase `xy_padding` or lower the cholesterol fraction. |
| `Config error: box ... is too small for cutoff=...` | Increase the padding or reduce `cutoff` so that half the shortest box edge exceeds `cutoff` + 2 Å. |
| `Run preflight: staged membrane input missing` | The `WORK_DIR` was not built by this template's `build.sh`. Build in a new `WORK_DIR`. |
