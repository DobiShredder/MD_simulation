# REUS template

## 한국어

Reaction coordinate의 각 umbrella center를 replica state로 두고 AMBER
Hamiltonian replica exchange(`-rem 3`)로 인접 state를 교환합니다. 각 replica는 자기
harmonic window를 sampling합니다. `windows.tsv`에는 center를 Å 단위로 한 줄에
하나씩 적고 `config.toml`에는 두 AMBER atom mask, force constant와 exchange
interval을 지정합니다. Reaction coordinate는 두 mask 사이의 거리입니다.

### 파일 역할

| 파일 | 역할 |
| --- | --- |
| `download.sh` | `download.sh PDB_ID`로 source PDB를 받습니다. |
| `build.sh` | LEaP system, `work/states.tsv`, window별 MD input과 restraint를 만듭니다. |
| `run.sh` | Window별 preproduction과 `pmemd.cuda.MPI -rem 3` replica exchange를 순서대로 실행합니다. |
| `config.toml` | Force field, box, stage 길이, atom mask, force constant와 exchange interval 설정입니다. |
| `windows.tsv` | Umbrella center 목록(Å)입니다. |
| `helpers/` | `build.sh` 또는 `run.sh`가 자동 호출하는 leaf-local 내부 code이며 직접 실행하지 않습니다. `generate_inputs.py`는 LEaP input과 resolved 설정을, `make_window_replicas.py`는 window별 MD input과 restraint를 만듭니다. |

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`(NumPy, ParmEd, Python 3.11 미만이면 tomli)로
설치합니다. AMBER(`tleap`, `pmemd.cuda`, `pmemd.cuda.MPI`)와 MPI는
[family README의 준비 사항](../README.md#준비-사항)을 참고합니다.

### 실행

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
```

Build는 두 mask가 각각 atom을 하나 이상 선택하고 서로 겹치지 않는지 확인한 뒤
`work/states.tsv`와 window directory를 만듭니다.

`AMBER_ENGINE`이 설정되어 있으면 이를 사용하며, 없으면
`work/resolved_config.toml`의 `run.engine`을 읽습니다. 허용하는 executable
이름은 `pmemd.cuda`이며 설치 경로를 지정할 수 있습니다. Exchange production에는
`AMBER_MPI_ENGINE` 또는 `run.mpi_engine`을 사용하며 executable 이름은
`pmemd.cuda.MPI`입니다. 기존 resolved config에 `run.mpi_engine`이 없으면
`AMBER_MPI_ENGINE`을 지정하거나 새 `WORK_DIR`에서 build합니다. 빈 override,
누락된 engine 설정과 지원하지 않는 executable은 기본값으로 대체하지 않고
error로 중단합니다.

`build.sh`는 window 생성과 모든 검사를 마친 뒤 마지막에 `work/build.done`을
씁니다. 이 파일이 없으면 `run.sh`와 `run.sh --dry-run`은 시작하지 않습니다.
실패한 build의 `work`는 옮긴 뒤 `./build.sh`를 다시 실행합니다.

실행 상태, 실패 후 재실행, 동시 실행 보호는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을
참고합니다.

### 계산 resource와 길이

| 항목 | 규칙 |
| --- | --- |
| Replica 수 | `windows.tsv`의 center 수입니다. 기본 20개입니다. |
| Pre-production | `pmemd.cuda` process 하나가 window별 minimization, heating, equilibration을 순서대로 실행합니다. |
| Production MPI rank | Window당 1개입니다. `MPI_PROCESSES`가 window 수와 다르면 시작 전에 거부합니다. |
| GPU | `run.sh`는 GPU를 지정하지 않습니다. `pmemd.cuda.MPI`는 `CUDA_VISIBLE_DEVICES`에 보이는 GPU를 rank에 나눠 씁니다(Amber26 manual 24.6.5, p. 506). GPU 1개로도 실행되지만 모든 rank가 나눠 쓰므로 느립니다. |
| Launcher 설정 | `MPI_LAUNCHER`(기본 `mpirun`), `MPI_OPTIONS`(launcher option, node 배치), `AMBER_OPTIONS`(모든 pmemd 호출에 추가)를 씁니다. `AMBER_OPTIONS`는 input identity에 기록되므로 실행 도중 바꾸지 않습니다. |

기본 config(2 fs)에서 계산 길이는 다음과 같습니다.

| Stage | Steps | Window당 길이 |
| --- | --- | --- |
| Heating / NPT equilibration | 250,000 / 500,000 | 0.5 ns / 1 ns |
| Production segment | `nstlim=1000` × `numexchg=5000` | 10 ns |
| Production 전체 | 20 segments | 200 ns(20 windows 합계 4 µs) |

Segment마다 exchange를 5,000번 시도하며 인접 pair 하나는 약 2,500번
시도됩니다(Amber26 manual 27.4.4.2, p. 582).

### Reaction coordinate mask

`atom_mask_1`과 `atom_mask_2`는 각각 atom 하나 또는 atom group을 선택합니다.
Build는 선택 결과에 따라 각 window의 `distance.RST`를 다르게 씁니다.

| Mask 선택 | `distance.RST` | 거리 기준점 |
| --- | --- | --- |
| atom 1개 | `iat=a,b` | 해당 atom 위치 |
| atom 2개 이상 | `iat=-1` + `igr1=...` 또는 `igr2=...` | group의 center of mass |

한쪽만 group이면 `iat=a,-1`처럼 섞어서 씁니다. Group 위치는 AMBER `ir6`
기본값 0에 따라 center of mass로 계산합니다(Amber26 manual 31.1.1, p. 670,
674). 예를 들어 `atom_mask_1 = ":1-3@CA"`는 세 Cα의 center of mass를 씁니다.
`sander`는 group당 200 atoms, `pmemd`는 system atom 수까지 허용합니다. AmberTools
26 `sander`에서 group 거리 restraint가 center-of-mass 거리와 일치함을
확인했습니다. `pmemd.cuda`의 group restraint 실행은 미검증입니다. `DUMPAVE`
output은 group 여부와 관계없이 time과 거리 두 column입니다.

### Restraint input 경로

Equilibration의 `DISANG`과 `DUMPAVE`는 각 replica directory의 `distance.RST`와
`restraint.equilibrate.dat`를 가리킵니다. Build는 production segment마다
`production.NNN.template.in`을 만듭니다. Exchange production은 group file로 이
directory에서 실행되므로 `run.sh`가 segment 시작 직전 `@DISANG@`과
`@DUMPAVE@`를 `work/<replica>/distance.RST`와
`work/<replica>/restraint.production.NNN.dat`로 바꿔 `production.NNN.in`을
씁니다.

### 주요 output

- `work/states.tsv`: window와 center의 최종 mapping
- `work/system.parm7`, `work/system.rst7`: 모든 replica가 직접 참조하는 공통 topology와 coordinate file
- `work/<replica>/`: replica별 engine input, restraint, seed와 restart
- `work/<replica>/production.NNN.nc`: segment별 trajectory
- `work/<replica>/restraint.production.NNN.dat`: segment별 restraint coordinate 기록
- `work/exchange.NNN.log`: segment별 exchange log
- `work/mpirun.production.NNN.log`: segment별 MPI stdout/stderr

Segment가 끝날 때마다 `Completed: production.NNN (work)`가 출력되고
`work/.production.NNN.complete`가 생깁니다. 모든 segment가 끝나면 마지막 줄은
`Completed REUS production: work`입니다. 기본값에서 window별
`production.NNN.nc`는 segment당 1,000 frame(5,000,000 steps ÷
`trajectory_interval_steps` 5,000), `restraint.production.NNN.dat`는 500 step마다
한 줄씩 약 10,000줄입니다. `--preparation-only`는
`Preparation output: work/<replica>/equilibrate.rst7`로 끝납니다.

### Exchange 품질 해석

Template에는 `anal.py`가 없으므로 AMBER H-REMD remlog인
`work/exchange.NNN.log`를 직접 읽습니다. 일반 판단 기준은
[family README의 Exchange 품질 해석](../README.md#exchange-품질-해석)을 따릅니다.
Remlog의 각 `# exchange N` block에는 replica 행이 하나씩 있습니다(Amber26
manual 27.4.5, pp. 587–588).

| Column | 의미 |
| --- | --- |
| `Rep#`, `Neibr#` | 1부터 시작하는 replica와 이번 시도의 상대입니다. Group file 순서이므로 1이 `work/000`, 즉 가장 작은 center입니다. |
| `PotE(x_1)`, `PotE(x_2)` | 현재 구조와 교환 후보 구조의 potential energy(kcal/mol)입니다. |
| `Success` | 이번 시도의 성공(`T`)/실패(`F`)입니다. |
| `Success rate (i,i+1)` | 이 replica와 다음 replica 사이의 누적 acceptance입니다. |

- 각 segment는 새 실행이므로 success rate는 segment마다 다시 누적됩니다.
  마지막 `# exchange` block의 값을 그 segment의 pair acceptance로 봅니다.
- H-REMD는 구조를 교환하고 각 replica는 자기 Hamiltonian을 유지합니다. 따라서
  `work/NNN/`의 trajectory와 `restraint.production.NNN.dat`는 한 window의
  sampling이며 PMF input으로 바로 쓸 수 있습니다. 한 구조가 window를 이동한
  경로는 cpptraj `remlog ... crdidx`로 재구성합니다(Amber26 manual 38.13.30,
  pp. 927–928).
- Window overlap은 인접 window의 `restraint.production.NNN.dat` 두 번째
  column(거리, Å) histogram으로 확인합니다. Histogram 사이에 빈 구간이 있으면 그
  pair의 acceptance도 0에 가깝고 PMF에 공백이 생깁니다.

cpptraj `remlog`는 segment log 하나에서 acceptance와 round trip을 계산합니다.

```bash
cpptraj <<'EOF'
readdata work/exchange.001.log as remlog nosearch name rem
remlog rem stats statsout rem.stats.dat reptime rem.reptime.dat acceptout rem.accept.dat
EOF
```

`acceptout`은 replica별 위/아래 acceptance(%), `statsout`은 round trip 수,
`reptime`은 각 coordinate가 window마다 머문 시간 비율입니다. 이 command는
AmberTools 26 cpptraj에서 합성 H-REMD log로 확인했으며 실제
`pmemd.cuda.MPI` log 읽기는 미검증입니다. Overlap histogram과 WHAM 계산 방식은
[7.1 analysis tutorial](../../../2_Analysis/7_Enhanced_Sampling/7.1_Umbrella_Sampling/README.md)을
참고합니다. 그 script는 tutorial의 `us/work/NNN/distance.dat`를 읽으므로 template
output 경로에 맞게 바꿔야 합니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Window equilibration에 적용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Exchange production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | Window seed와 stage별 `ig`를 정합니다. 아래 seed 규칙을 따릅니다. |

### 숫자 option

| Key | 기본값 | Unit | Stage | 효과 |
| --- | ---: | --- | --- | --- |
| `build.solute_box_distance` | 14.0 | Å | build | LEaP solvation에서 solute와 box 경계 사이 최소 거리입니다. |
| `build.salt_concentration` | 150.0 | mM | build | Neutralization 뒤 추가할 bulk salt 농도입니다. |
| `run.temperature` | 300.0 | K | MD | 모든 window의 `temp0`와 heating 목표 temperature입니다. |
| `run.pressure` | 1.0 | bar | NPT stage | `pres0`입니다. |
| `run.timestep` | 2.0 | fs | 모든 MD | AMBER `dt`(ps)로 씁니다. Hydrogen mass repartitioning이 없으므로 2.0보다 크면 거부합니다. |
| `run.minimization_steps` / `minimization_steepest_steps` | 5000 / 2500 | step | minimization | `maxcyc` / `ncyc`입니다. |
| `run.heating_initial_temperature` | 20.0 | K | heating | `tempi`와 `&wt TEMP0`의 시작값입니다. |
| `run.heating_steps` | 250000 | step | heating | Heating `nstlim`입니다. |
| `run.equilibration_steps` | 500000 | step | equilibration | Window NPT equilibration의 `nstlim`입니다. |
| `run.production_steps` | 100000000 | step | production | Window당 전체 production입니다. Segment 수로 나누어떨어져야 합니다. |
| `run.production_segments` | 20 | 개 | production | Restart 가능한 segment 수입니다. Segment 길이는 `exchange_interval_steps`로 나누어떨어져야 합니다. |
| `run.trajectory_interval_steps` | 5000 | step | MD | `ntwx`입니다. |
| `run.energy_interval_steps` | 5000 | step | MD | `ntpr`입니다. |
| `run.restart_interval_steps` | 5000 | step | MD | `ntwr`입니다. |
| `umbrella.force_constant` | 1.0 | kcal mol⁻¹ Å⁻² | 모든 stage | `distance.RST`의 `rk2`, `rk3`입니다. 아래 window 절을 참고합니다. |
| `umbrella.exchange_interval_steps` | 1000 | step | production | Exchange 사이 MD step(`nstlim`)입니다. `numexchg`는 segment step ÷ 이 값입니다. |
| `umbrella.distance_output_interval_steps` | 500 | step | equilibration, production | `&wt type='DUMPFREQ'`로 `DUMPAVE` 기록 간격을 정합니다. |

Segment 1은 `equilibrate.rst7`, segment N은 같은 window directory의
`production.(N-1).rst7`에서 `irest=1`로 이어집니다. Segment마다
`exchange.NNN.log`가 따로 생기며, 끊긴 계산은 `./run.sh --segments N-20`으로
이어서 실행합니다.

### Window와 force constant

기본 center는 6–24 Å 양 끝을 포함하는 20개이며 spacing은
`18/19 ≈ 0.947368 Å`입니다. State table과 restraint center는 소수점 8자리로
기록합니다.

`windows_file`은 항상 명시적인 center 목록을 읽으며 `auto`/`file` mode가
아닙니다. Blank line과 `#`로 시작하는 comment line을 제외하고 각 행에는 center
하나만 적습니다. Center 목록은 비어 있지 않고 중복 없이 오름차순이어야 합니다.
각 행이 한 exchange state가 됩니다. Replica 수는 2 이상의 짝수여야 하며
`build.sh`와 `run.sh`는 홀수 schedule을 자동 조정하지 않고 거부합니다.
`run.sh --dry-run`도 같은 검사를 합니다.

기본 `force_constant = 1.0`은 AMBER `rk`(E = rk(r − r₀)², kcal mol⁻¹ Å⁻²)입니다.
기본 0.947 Å 간격에서 300 K window 폭은 약 0.55 Å이고 예상 인접 교환 확률은 약
0.22입니다(Gaussian 예측, 미검증). Window 간격을 바꾸면 force constant도 함께
조정합니다.

### Seed 규칙

`"random"`이면 window마다 무작위 seed를 만들어 heating `ig`에 쓰고,
equilibration과 production segment는 `ig=-1`로 실행 시각에서 seed를 정합니다.
정수이면 window seed는 `정수 + 7919 × window index`입니다. Langevin
dynamics(`ntt=3`)는 restart마다 다른 `ig`를 써야 하므로 stage마다 1,000,000을
더합니다. Heating은 +0, equilibration은 +1,000,000, production segment N은
+(2+N)×1,000,000입니다.

### Engine option 직접 지정

Config key가 없는 AMBER option은 `[amber.<stage>.<namelist>]` table로 지정합니다. Stage 우선순위, 값 형식과 거부되는 keyword는 [3_Templates README](../../README.md#engine-option-직접-지정)를 따릅니다.

```toml
[amber.md.cntrl]
gamma_ln = 2.0

[amber.production.cntrl]
iwrap = 1
```

| Stage | Input |
| --- | --- |
| `minimization` | `minimize.in` |
| `heating` | `heat.in` |
| `equilibration` | `equilibrate.in` |
| `production` | `production.NNN.template.in` |

모든 window에 같은 값을 씁니다. Window별 값은 지정할 수 없습니다.

### 문제 해결

| Message 또는 증상 | 원인 | 조치 |
| --- | --- | --- |
| `Mask must select at least one atom: ...` 또는 `The two reaction-coordinate masks must not select the same atom` | Mask가 비었거나 두 mask가 겹칩니다. | `work/system.parm7` 기준 residue 번호와 atom 이름으로 mask를 고치고 새 `WORK_DIR`에서 build합니다. |
| `Replica exchange requires at least two and an even number of windows: ...`(build), `... states: ...`(run) 또는 `window centers must be non-empty, unique, and increasing` | `windows.tsv`의 center 수가 홀수이거나 순서가 틀립니다. | Center를 오름차순 짝수 개로 맞춥니다. |
| `Build did not complete: work/build.done is missing; ...` | Build가 중간에 실패했습니다. | Build error를 확인하고 `mv work work.old` 후 다시 build합니다. |
| `MPI_PROCESSES must equal the window count: N` | Rank 수가 window 수와 다릅니다. | `MPI_PROCESSES`를 지우거나 N으로 둡니다. |
| `REUS segment N failed: work/mpirun.production.NNN.log, work/exchange.NNN.log` | MPI, GPU 또는 engine error입니다. | `run.sh`가 출력한 log 끝부분과 각 window의 `production.NNN.out`을 확인합니다. 남은 partial output은 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구) 절차로 옮깁니다. |
| 특정 pair의 success rate가 0에 가까움 | 두 window의 distance 분포가 겹치지 않습니다. | 새 `WORK_DIR`에서 그 사이에 center를 추가하거나 `force_constant`를 낮춥니다. |

## English

Each umbrella center on the reaction coordinate is a replica state, and AMBER
Hamiltonian replica exchange (`-rem 3`) swaps neighboring states while every replica
samples its harmonic window. List centers in Å, one per line, in `windows.tsv`,
and set the two AMBER atom masks, force constant and exchange interval in
`config.toml`. The reaction coordinate is the distance between the two masks.

### File roles

| File | Role |
| --- | --- |
| `download.sh` | Downloads a source PDB with `download.sh PDB_ID`. |
| `build.sh` | Builds the LEaP system, `work/states.tsv`, per-window MD inputs and restraints. |
| `run.sh` | Runs per-window preproduction and `pmemd.cuda.MPI -rem 3` replica exchange in order. |
| `config.toml` | Force field, box, stage lengths, atom masks, force constant and exchange interval. |
| `windows.tsv` | Umbrella center list (Å). |
| `helpers/` | Leaf-local internal code called automatically by `build.sh` or `run.sh`; not an entry point. `generate_inputs.py` writes LEaP inputs and resolved settings, and `make_window_replicas.py` writes per-window MD inputs and restraints. |

This directory can be copied and used on its own. Install its Python
dependencies (NumPy, ParmEd, and tomli below Python 3.11) from the local
`requirements.txt` after copying it. For AMBER (`tleap`, `pmemd.cuda`,
`pmemd.cuda.MPI`) and MPI, see the
[family README prerequisites](../README.md#prerequisites).

### Run

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
```

The build checks that each mask selects at least one atom and that the masks do
not overlap, then writes `work/states.tsv` and the window directories.

`AMBER_ENGINE` overrides `run.engine` in `work/resolved_config.toml`. The
accepted executable name is `pmemd.cuda`; installation paths are accepted.
Exchange production uses `AMBER_MPI_ENGINE` or `run.mpi_engine`, with
executable name `pmemd.cuda.MPI`. If an older resolved config lacks
`run.mpi_engine`, set `AMBER_MPI_ENGINE` or build in a new `WORK_DIR`. Empty
overrides, missing engine settings and unsupported executables fail instead of
falling back to a default.

`build.sh` writes `work/build.done` as its last step, after window generation
and every check. Without it, `run.sh` and `run.sh --dry-run` do not start. Move
the `work` of a failed build aside and rerun `./build.sh`.

See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state, reruns after failure and
concurrent-run protection.

### Resources and length

| Item | Rule |
| --- | --- |
| Replica count | Number of centers in `windows.tsv`; 20 by default. |
| Pre-production | One `pmemd.cuda` process runs minimization, heating and equilibration for each window in turn. |
| Production MPI ranks | One per window. A different `MPI_PROCESSES` is rejected before launch. |
| GPUs | `run.sh` does not assign GPUs. `pmemd.cuda.MPI` distributes ranks over the GPUs visible in `CUDA_VISIBLE_DEVICES` (Amber26 manual 24.6.5, p. 506). One GPU works but is slow because every rank shares it. |
| Launcher settings | `MPI_LAUNCHER` (default `mpirun`), `MPI_OPTIONS` (launcher options, node placement) and `AMBER_OPTIONS` (appended to every pmemd call). `AMBER_OPTIONS` is recorded in the input identity, so do not change it mid-run. |

Default lengths at 2 fs:

| Stage | Steps | Length per window |
| --- | --- | --- |
| Heating / NPT equilibration | 250,000 / 500,000 | 0.5 ns / 1 ns |
| Production segment | `nstlim=1000` × `numexchg=5000` | 10 ns |
| Full production | 20 segments | 200 ns (4 µs over 20 windows) |

Each segment makes 5,000 exchange attempts, about 2,500 per neighbor pair
(Amber26 manual 27.4.4.2, p. 582).

### Reaction-coordinate masks

`atom_mask_1` and `atom_mask_2` each select one atom or an atom group. The build
writes each window's `distance.RST` according to the selection.

| Mask selects | `distance.RST` | Distance reference |
| --- | --- | --- |
| one atom | `iat=a,b` | that atom |
| two or more atoms | `iat=-1` + `igr1=...` or `igr2=...` | group center of mass |

Mixed selections are allowed, for example `iat=a,-1`. The group position is the
center of mass because AMBER `ir6` defaults to 0 (Amber26 manual 31.1.1,
pp. 670, 674). For example, `atom_mask_1 = ":1-3@CA"` uses the center of mass of
three Cα atoms. `sander` allows up to 200 atoms per group and `pmemd` up to the system atom
count.
With AmberTools 26 `sander`, the group restraint matched the center-of-mass
distance. Group restraints in `pmemd.cuda` are unverified. The `DUMPAVE` output
keeps two columns, time and distance, for atoms and groups alike.

### Restraint input paths

Equilibration resolves `DISANG` and `DUMPAVE` to `distance.RST` and
`restraint.equilibrate.dat` within each replica directory. The build writes one
`production.NNN.template.in` per production segment. Exchange production runs
from this directory through the group file, so `run.sh` replaces `@DISANG@` and
`@DUMPAVE@` with `work/<replica>/distance.RST` and
`work/<replica>/restraint.production.NNN.dat` and writes `production.NNN.in`
just before the segment starts.

### Main outputs

- `work/states.tsv`: final window-to-center mapping
- `work/system.parm7`, `work/system.rst7`: shared topology and coordinate file referenced directly by every replica
- `work/<replica>/`: per-replica engine inputs, restraints, seeds and restarts
- `work/<replica>/production.NNN.nc`: per-segment trajectory
- `work/<replica>/restraint.production.NNN.dat`: per-segment restraint-coordinate record
- `work/exchange.NNN.log`: exchange log for each segment
- `work/mpirun.production.NNN.log`: MPI stdout/stderr for each segment

Each finished segment prints `Completed: production.NNN (work)` and creates
`work/.production.NNN.complete`. After the last segment the final line is
`Completed REUS production: work`. With the defaults each window's
`production.NNN.nc` holds 1,000 frames per segment (5,000,000 steps ÷
`trajectory_interval_steps` 5,000), and `restraint.production.NNN.dat` about
10,000 rows, one every 500 steps. `--preparation-only` ends with
`Preparation output: work/<replica>/equilibrate.rst7`.

### Reading exchange quality

The template has no `anal.py`; read the AMBER H-REMD remlog
`work/exchange.NNN.log` directly. General criteria are in the
[family README](../README.md#reading-exchange-quality). Each `# exchange N`
block has one row per replica (Amber26 manual 27.4.5, pp. 587–588).

| Column | Meaning |
| --- | --- |
| `Rep#`, `Neibr#` | Replica number starting at 1 and its partner in this attempt. Group-file order makes 1 the `work/000` window, the smallest center. |
| `PotE(x_1)`, `PotE(x_2)` | Potential energy (kcal/mol) of the current and the proposed structure. |
| `Success` | Accepted (`T`) or rejected (`F`) in this attempt. |
| `Success rate (i,i+1)` | Cumulative acceptance between this replica and the next. |

- Every segment is a new run, so success rates restart in each segment. Use the
  last `# exchange` block as that segment's pair acceptance.
- H-REMD swaps structures while each replica keeps its Hamiltonian. The
  trajectory and `restraint.production.NNN.dat` in `work/NNN/` therefore sample
  one window and can go straight into a PMF. Reconstruct how a structure moved
  across windows with cpptraj `remlog ... crdidx` (Amber26 manual 38.13.30,
  pp. 927–928).
- Check window overlap with histograms of the second column (distance, Å) of
  neighboring windows' `restraint.production.NNN.dat`. A gap between histograms
  goes with near-zero acceptance for that pair and a gap in the PMF.

cpptraj `remlog` computes acceptance and round trips from one segment log.

```bash
cpptraj <<'EOF'
readdata work/exchange.001.log as remlog nosearch name rem
remlog rem stats statsout rem.stats.dat reptime rem.reptime.dat acceptout rem.accept.dat
EOF
```

`acceptout` gives up/down acceptance (%) per replica, `statsout` the round
trips, and `reptime` the fraction of time each coordinate spent in each window.
The command was checked with AmberTools 26 cpptraj on a synthetic H-REMD log;
reading a real `pmemd.cuda.MPI` log is unverified. For overlap histograms and
WHAM, see the
[7.1 analysis tutorial](../../../2_Analysis/7_Enhanced_Sampling/7.1_Umbrella_Sampling/README.md);
its scripts read the tutorial's `us/work/NNN/distance.dat`, so adapt the paths
to the template outputs.

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to window equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Sets exchange-production `ntb` and `ntp`. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | Sets window seeds and per-stage `ig`; see the seed rule below. |

### Numeric options

| Key | Default | Unit | Stage | Effect |
| --- | ---: | --- | --- | --- |
| `build.solute_box_distance` | 14.0 | Å | build | Minimum solute-to-box-edge distance in LEaP solvation. |
| `build.salt_concentration` | 150.0 | mM | build | Bulk salt added after neutralization. |
| `run.temperature` | 300.0 | K | MD | `temp0` of every window and the heating target. |
| `run.pressure` | 1.0 | bar | NPT stages | `pres0`. |
| `run.timestep` | 2.0 | fs | all MD | Written as AMBER `dt` (ps). Values above 2.0 are rejected because hydrogen masses are not repartitioned. |
| `run.minimization_steps` / `minimization_steepest_steps` | 5000 / 2500 | steps | minimization | `maxcyc` / `ncyc`. |
| `run.heating_initial_temperature` | 20.0 | K | heating | Start value of `tempi` and the `&wt TEMP0` ramp. |
| `run.heating_steps` | 250000 | steps | heating | Heating `nstlim`. |
| `run.equilibration_steps` | 500000 | steps | equilibration | `nstlim` of window NPT equilibration. |
| `run.production_steps` | 100000000 | steps | production | Total production per window; must divide by the segment count. |
| `run.production_segments` | 20 | count | production | Number of restartable segments; each segment must divide by `exchange_interval_steps`. |
| `run.trajectory_interval_steps` | 5000 | steps | MD | `ntwx`. |
| `run.energy_interval_steps` | 5000 | steps | MD | `ntpr`. |
| `run.restart_interval_steps` | 5000 | steps | MD | `ntwr`. |
| `umbrella.force_constant` | 1.0 | kcal mol⁻¹ Å⁻² | all stages | `rk2`, `rk3` in `distance.RST`; see the window section below. |
| `umbrella.exchange_interval_steps` | 1000 | steps | production | MD steps between exchanges (`nstlim`); `numexchg` is segment steps ÷ this value. |
| `umbrella.distance_output_interval_steps` | 500 | steps | equilibration, production | `DUMPAVE` interval set through `&wt type='DUMPFREQ'`. |

Segment 1 starts from `equilibrate.rst7` and segment N from
`production.(N-1).rst7` in the same window directory, with `irest=1`. Each
segment writes its own `exchange.NNN.log`; resume an interrupted run with
`./run.sh --segments N-20`.

### Windows and force constant

The default has 20 centers including both 6 and 24 Å, spaced by
`18/19 ≈ 0.947368 Å`. State tables and restraint centers use eight decimal
places.

`windows_file` always supplies an explicit center list and is not an
`auto`/`file` mode. After blank lines and full-line `#` comments are skipped,
each row must contain exactly one center. The list must be nonempty, unique and
increasing. Each row becomes one exchange state. The replica count must be even
and at least two; `build.sh` and `run.sh` reject odd schedules without adjusting
them, and `run.sh --dry-run` applies the same check.

The default `force_constant = 1.0` is the AMBER `rk` (E = rk(r − r₀)²,
kcal mol⁻¹ Å⁻²). At the default 0.947 Å spacing, 300 K windows are about 0.55 Å
wide and the predicted neighbor exchange acceptance is about 0.22 (Gaussian
estimate, unverified). Adjust the force constant together with the window
spacing.

### Seed rule

With `"random"`, each window gets a random seed for heating `ig`, and
equilibration and production segments use `ig=-1` (wall-clock seed). With an
integer, the window seed is `integer + 7919 × window index`. Langevin dynamics
(`ntt=3`) needs a different `ig` on each restart, so each stage adds 1,000,000:
heating +0, equilibration +1,000,000, and production segment N
+(2+N)×1,000,000.

### Engine option passthrough

AMBER options without a config key go into `[amber.<stage>.<namelist>]` tables. Stage precedence, value formats and refused keywords are described in the [3_Templates README](../../README.md#engine-option-passthrough).

```toml
[amber.md.cntrl]
gamma_ln = 2.0

[amber.production.cntrl]
iwrap = 1
```

| Stage | Input |
| --- | --- |
| `minimization` | `minimize.in` |
| `heating` | `heat.in` |
| `equilibration` | `equilibrate.in` |
| `production` | `production.NNN.template.in` |

Every window gets the same values; per-window values are not supported.

### Troubleshooting

| Message or symptom | Cause | Action |
| --- | --- | --- |
| `Mask must select at least one atom: ...` or `The two reaction-coordinate masks must not select the same atom` | A mask is empty or the masks overlap. | Fix the masks using residue numbers and atom names in `work/system.parm7`, then build in a new `WORK_DIR`. |
| `Replica exchange requires at least two and an even number of windows: ...` (build), `... states: ...` (run), or `window centers must be non-empty, unique, and increasing` | `windows.tsv` has an odd count or bad order. | Provide an even number of increasing centers. |
| `Build did not complete: work/build.done is missing; ...` | The build failed partway. | Read the build error, `mv work work.old`, and rebuild. |
| `MPI_PROCESSES must equal the window count: N` | The rank count differs from the window count. | Unset `MPI_PROCESSES` or set it to N. |
| `REUS segment N failed: work/mpirun.production.NNN.log, work/exchange.NNN.log` | MPI, GPU or engine error. | Read the log tail printed by `run.sh` and each window's `production.NNN.out`. Move retained partial output as described in the [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery). |
| One pair's success rate stays near 0 | The two windows' distance distributions do not overlap. | In a new `WORK_DIR`, add a center between them or lower `force_constant`. |
