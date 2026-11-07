# T-REMD template

## 한국어

사용자가 준비한 protein PDB로 AMBER temperature replica exchange를 구성합니다.
`build.sh`는 configured protein/water system을 만든 뒤 topology의 solute/ion atom 수와 water
molecule 수를 읽어 300–450 K ladder를 자동 생성합니다. 기본 목표 neighboring
exchange probability는 0.20이며 예측값은 initial schedule을 정하는 근사치입니다.

### 파일 역할

| 파일 | 역할 |
| --- | --- |
| `download.sh` | RCSB PDB ID로 structure를 `structure/`에 받습니다. |
| `build.sh` | Solvated system, temperature schedule과 replica별 AMBER input을 만듭니다. |
| `run.sh` | Replica별 pre-production과 `pmemd.cuda.MPI -rem 1` production segment를 실행합니다. |
| `config.toml` | Force field, box, salt, stage 길이와 temperature ladder 설정입니다. |
| `helpers/` | `build.sh` 또는 `run.sh`가 자동 호출하는 leaf-local 내부 code이며 직접 실행하지 않습니다. |

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`(NumPy, ParmEd, Python 3.11 미만이면 tomli)로
설치합니다. AMBER(`tleap`, `pmemd.cuda`, `pmemd.cuda.MPI`)와 MPI는
[family README의 준비 사항](../README.md#준비-사항)을 참고합니다.

### 실행

```bash
./download.sh 1UBQ
./build.sh structure/1UBQ.pdb
./run.sh --dry-run
./run.sh
```

`pmemd.cuda`가 preproduction을 실행합니다. 기본 `production_ensemble = "NVT"`에서는
`work/shared`에서 minimization, heating, NPT equilibration을 한 번 실행한 뒤 각
replica가 그 box에서 NVT equilibration을 합니다(아래 순서 참고). Heating은
`minimize.rst7`을 `-c`와 positional restraint의 `-ref` input으로 함께
사용합니다. Production은 `pmemd.cuda.MPI -rem 1`로 실행합니다.

`AMBER_ENGINE`이 설정되어 있으면 이를 사용하며, 없으면 `work/resolved_config.toml`의
`run.engine`을 읽습니다. 허용하는 executable 이름은 `pmemd.cuda`이며 설치 경로를
지정할 수 있습니다. Exchange production에는 `AMBER_MPI_ENGINE` 또는
`run.mpi_engine`을 사용하며 executable 이름은 `pmemd.cuda.MPI`입니다. 빈
override, 누락된 engine 설정과 지원하지 않는 executable은 기본값으로 대체하지
않고 error로 중단합니다.

실행 상태, 실패 후 재실행, 동시 실행 보호는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을
참고합니다.

### 계산 resource와 길이

| 항목 | 규칙 |
| --- | --- |
| Replica 수 | `work/states.tsv`의 행 수입니다. 1UBQ 기본 설정에서는 68개입니다. |
| Pre-production | `pmemd.cuda` process 하나가 shared stage와 replica별 stage를 순서대로 실행합니다. |
| Production MPI rank | Replica당 1개입니다. `MPI_PROCESSES`가 replica 수와 다르면 시작 전에 거부합니다. |
| GPU | `run.sh`는 GPU를 지정하지 않습니다. `pmemd.cuda.MPI`는 `CUDA_VISIBLE_DEVICES`에 보이는 GPU를 rank에 나눠 씁니다(Amber26 manual 24.6.5, p. 506). GPU 1개로도 실행되지만 모든 rank가 나눠 쓰므로 느립니다. |
| Launcher 설정 | `MPI_LAUNCHER`(기본 `mpirun`), `MPI_OPTIONS`(launcher option, node 배치), `AMBER_OPTIONS`(모든 pmemd 호출에 추가)를 씁니다. `AMBER_OPTIONS`는 input identity에 기록되므로 실행 도중 바꾸지 않습니다. |

기본 config(2 fs)에서 계산 길이는 다음과 같습니다.

| Stage | Steps | Replica당 길이 |
| --- | --- | --- |
| Shared heating / NPT equilibration | 250,000 / 500,000 | 한 번만 0.5 ns / 1 ns |
| Replica NVT equilibration | 500,000 | 1 ns |
| Production segment | `nstlim=1000` × `numexchg=5000` | 10 ns |
| Production 전체 | 10 segments | 100 ns(68 replicas 합계 6.8 µs) |

Segment마다 exchange를 5,000번 시도합니다. AMBER는 짝수/홀수 pair를 번갈아
시도하므로 인접 pair 하나는 segment당 약 2,500번 시도됩니다(Amber26 manual
27.4.4.2, p. 582).

### 주요 output

- `work/states.tsv`: 실제 replica 수, temperature와 seed
- `work/system_counts.tsv`: predictor에 넣은 atom/water 수와 `used_target_exchange_probability`
- `work/resolved_config.toml`: 적용된 설정
- `work/system.parm7`, `work/system.rst7`: 모든 replica가 직접 참조하는 공통 topology와 coordinate file
- `work/NNN/production.NNN.in`, `production.NNN.nc`: replica별 segment input과 trajectory
- `work/exchange.NNN.log`: segment별 exchange log
- `work/mpirun.production.NNN.log`: segment별 MPI stdout/stderr

Segment가 끝날 때마다 `Completed: production.NNN (work)`가 출력되고
`work/.production.NNN.complete`가 생깁니다. 모든 segment가 끝나면 마지막 줄은
`Completed T-REMD production: work`입니다. 기본값에서 replica별
`production.NNN.nc`는 segment당 1,000 frame(5,000,000 steps ÷
`trajectory_interval_steps` 5,000)입니다. `--preparation-only`는
`Preparation output: work/<replica>/equilibrate.rst7`로 끝납니다.

### Exchange 품질 해석

Template에는 `anal.py`가 없으므로 AMBER remlog인 `work/exchange.NNN.log`를 직접
읽습니다. 일반 판단 기준은
[family README의 Exchange 품질 해석](../README.md#exchange-품질-해석)을 따릅니다.
T-REMD remlog는 `# exchange N` block마다 replica 행을 하나씩 씁니다(Amber26
manual 27.4.4.2, p. 582).

| Column | 의미 |
| --- | --- |
| `Rep#` | 1부터 시작하는 replica 번호입니다. Group file 순서이므로 1이 `work/000`입니다. |
| `Velocity Scaling` | 교환이 성공하면 velocity scaling factor, 실패하면 `-1.00`입니다. |
| `Temp0`, `NewTemp0` | 교환 시도 전후 target temperature(K)입니다. |
| `Success rate (i,i+1)` | 그 행 `Temp0`와 바로 위 temperature 사이의 누적 acceptance입니다. 가장 높은 temperature 행은 보통 0입니다. |

- 각 segment는 새 `pmemd.cuda.MPI` 실행이므로 success rate는 segment마다 다시
  누적됩니다. 마지막 `# exchange` block의 값을 그 segment의 pair acceptance로
  봅니다. 초기 block의 값은 시도 횟수가 적어 크게 흔들립니다.
- Replica 번호는 그대로이고 temperature가 교환됩니다. 한 replica의 `Temp0`를
  exchange 순서로 따라가면 ladder 이동과 round trip을 셀 수 있습니다.
- Segment 2부터는 이전 segment restart에 저장된 target temperature가 mdin
  `temp0`보다 우선합니다(p. 582). 따라서 `work/NNN/`은 replica identity이며
  temperature별 trajectory가 아닙니다. 특정 temperature의 frame은 cpptraj
  `trajin ... remdtraj remdtrajtemp 300`으로 고릅니다(Amber26 manual 38.11.4,
  pp. 792–793).

cpptraj `remlog`는 segment log 하나에서 acceptance, round trip과 state별 체류
시간을 계산합니다(Amber26 manual 38.13.30, pp. 927–928).

```bash
cpptraj <<'EOF'
readdata work/exchange.001.log as remlog nosearch name rem
remlog rem stats statsout rem.stats.dat reptime rem.reptime.dat acceptout rem.accept.dat
EOF
```

`acceptout`은 replica별 위/아래 acceptance(%), `statsout`은 round trip 수,
`reptime`은 각 coordinate가 state마다 머문 시간 비율입니다. 이 command는
AmberTools 26 cpptraj에서 H-REMD 형식 합성 log로만 확인했습니다. T-REMD
`pmemd.cuda.MPI` log 읽기는 미검증입니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | `NVT` production에서는 공통 equilibration(`work/shared/equilibrate.in`), `NPT` production에서는 각 replica equilibration에 적용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NVT` | Replica production의 `ntb`와 `ntp`를 설정합니다. `NVT`이면 아래 공통 NPT stage를 먼저 실행합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | Replica seed와 stage별 `ig`를 정합니다. 아래 seed 규칙을 따릅니다. |

| `temperature_mode` | 사용하는 설정 | 무시하는 설정 | 생성 결과 |
| --- | --- | --- | --- |
| `auto` (기본값) | `minimum_temperature`, `maximum_temperature`, `target_exchange_probability`, `generator_tolerance` | `temperature_file` | 전체 solvated system을 predictor에 넣어 `work/states.tsv`를 생성합니다. 1UBQ 기본값(300–450 K, p=0.20)은 67 state가 나와 p≈0.210, 68 state로 조정됩니다(AmberTools build 확인). |
| `file` | `temperature_file` | Auto ladder 설정 | File 값을 순서대로 `work/states.tsv`에 기록합니다. |

### 숫자 option

| Key | 기본값 | Unit | Stage | 효과 |
| --- | ---: | --- | --- | --- |
| `build.solute_box_distance` | 14.0 | Å | build | LEaP solvation에서 solute와 box 경계 사이 최소 거리입니다. |
| `build.salt_concentration` | 150.0 | mM | build | Neutralization 뒤 추가할 bulk salt 농도입니다. |
| `run.temperature` | 300.0 | K | build | 첫 state temperature와 같아야 합니다. Replica `temp0`는 `work/states.tsv`에서 읽습니다. |
| `run.pressure` | 1.0 | bar | NPT stage | `pres0`입니다. |
| `run.timestep` | 2.0 | fs | 모든 MD | AMBER `dt`(ps)로 씁니다. Hydrogen mass repartitioning이 없으므로 2.0보다 크면 거부합니다. |
| `run.minimization_steps` / `minimization_steepest_steps` | 5000 / 2500 | step | minimization | `maxcyc` / `ncyc`입니다. |
| `run.heating_initial_temperature` | 20.0 | K | heating | `tempi`와 `&wt TEMP0`의 시작값입니다. |
| `run.heating_steps` | 250000 | step | heating | Heating `nstlim`입니다. |
| `run.equilibration_steps` | 500000 | step | equilibration | Shared NPT와 replica NVT equilibration의 `nstlim`입니다. |
| `run.production_steps` | 50000000 | step | production | Replica당 전체 production입니다. Segment 수로 나누어떨어져야 합니다. |
| `run.production_segments` | 10 | 개 | production | Restart 가능한 segment 수입니다. Segment 길이는 `exchange_interval_steps`로 나누어떨어져야 합니다. |
| `run.trajectory_interval_steps` | 5000 | step | MD | `ntwx`입니다. |
| `run.energy_interval_steps` | 5000 | step | MD | `ntpr`입니다. |
| `run.restart_interval_steps` | 5000 | step | MD | `ntwr`입니다. |
| `replica_exchange.minimum_temperature` / `maximum_temperature` | 300.0 / 450.0 | K | build(auto) | Auto ladder의 양 끝입니다. |
| `replica_exchange.target_exchange_probability` | 0.20 | — | build(auto) | Predictor의 목표 인접 acceptance입니다. 높이면 replica가 늘어납니다. |
| `replica_exchange.generator_tolerance` | 0.0001 | — | build(auto) | 예측 pair probability와 목표값의 허용 차이입니다. |
| `replica_exchange.exchange_interval_steps` | 1000 | step | production | Exchange 사이 MD step(`nstlim`)입니다. `numexchg`는 segment step ÷ 이 값입니다. |

### Replica 수와 temperature ladder

Replica 수는 2 이상의 짝수여야 합니다. Auto mode에서 predictor가 홀수 N개
state를 내면 온도 범위와 predictor 계산식은 그대로 두고 target exchange
probability를 올려 N+1개로 맞춥니다. N+1개가 되는 값 중 가장 큰 값을 쓰므로
모든 인접 pair의 예상 교환 확률이 거의 같아집니다. 실제로 쓴 값은 build 출력과
`work/system_counts.tsv`의 `used_target_exchange_probability`에 남습니다.

Auto ladder의 water 수는 first-pass LEaP build에서 셉니다. `build.sh --dry-run`은
auto predictor를 실행하지 않으므로 auto replica 수는 실제 build에서 정해집니다.

File mode의 홀수 schedule은 자동으로 바꾸지 않고 LEaP 실행 전에 거부합니다.
`run.sh --dry-run`도 `work/states.tsv`의 count를 검사합니다. Temperature file은
사용자가 생성해야 합니다. 공백, comma, semicolon, `|`를 구분자로 사용할 수
있고 `#` 뒤는 comment입니다. 값은 finite 양수이고 중복 없이 오름차순이어야
하며, 둘 이상이어야 하고 첫 값은 `run.temperature`와 같아야 합니다. `nan`,
`inf`, `-inf`와 float 범위를 넘는 값은 topology와 input을 저장하기 전에 file
경로와 함께 거부합니다.

### Seed 규칙

`"random"`이면 replica마다 무작위 seed를 만들어 heating `ig`에 쓰고,
equilibration과 production segment는 `ig=-1`로 실행 시각에서 seed를 정합니다.
정수이면 replica seed는 `정수 + 7919 × replica index`입니다. Langevin
dynamics(`ntt=3`)는 restart마다 다른 `ig`를 써야 하므로 stage마다 1,000,000을
더합니다. Heating은 +0, equilibration은 +1,000,000, production segment N은
+(2+N)×1,000,000입니다. 이를 위해 build는 segment마다
`work/<replica>/production.NNN.in`을 만듭니다.

### Production ensemble

기본값은 일반적인 T-REMD 구성인 `production_ensemble = "NVT"`입니다. 450 K 근처
replica를 1 bar NPT로 실행하면 water density가 크게 바뀌어 계산이 불안정할 수
있습니다. NVT replica exchange는 모든 replica의 부피가 같아야 하므로 원래
system을 한 번 constant pressure로 안정화한 뒤 각 replica equilibration을
시작합니다(Amber26 manual, REMD 절, p. 576).

| 순서 | Stage | 위치 | 온도 | Ensemble | 길이 |
| --- | --- | --- | --- | --- | --- |
| 1 | minimization | `work/shared` | — | 고정 box | 5,000 cycles |
| 2 | heating | `work/shared` | 20 K → 첫 replica 온도 | NVT | `heating_steps` |
| 3 | equilibration | `work/shared` | 첫 replica 온도 | NPT | `equilibration_steps` |
| 4 | equilibration | `work/NNN` | replica 온도 | NVT | `equilibration_steps` |
| 5 | production | `work/NNN` | replica 온도 | NVT | `production_steps` |

모든 replica는 `work/shared/equilibrate.rst7`의 box에서 4를 시작합니다. 4는
replica 온도에서 처음 equilibration하는 단계라 3과 같은 길이를 씁니다. 공통
seed는 `"random"`이면 무작위, 정수이면 `정수 + 7919 × replica 수`입니다.

`production_ensemble = "NPT"`로 바꾸면 `work/shared` 없이 replica마다
minimization, heating, NPT equilibration을 따로 실행하고 production도 NPT로
실행합니다.

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
| `production` | `production.NNN.in` |

모든 replica에 같은 값을 씁니다. Replica별 값은 지정할 수 없습니다.

### 문제 해결

| Message 또는 증상 | 원인 | 조치 |
| --- | --- | --- |
| `Config error: Replica exchange requires an even number of temperatures: ...` | File mode temperature 수가 홀수입니다. | Temperature를 하나 추가하거나 빼고 다시 build합니다. |
| `Config error: timestep must be 2.0 fs or less without hydrogen mass repartitioning` | `run.timestep`이 2 fs보다 큽니다. | 2.0 이하로 둡니다. |
| `MPI_PROCESSES must equal the replica count: N` | Rank 수가 replica 수와 다릅니다. | `MPI_PROCESSES`를 지우거나 N으로 둡니다. |
| `Executable not found: ...` | `pmemd.cuda`, `pmemd.cuda.MPI` 또는 launcher가 `PATH`에 없습니다. | AMBER 환경을 load하거나 `AMBER_ENGINE`, `AMBER_MPI_ENGINE`, `MPI_LAUNCHER`를 지정합니다. |
| `T-REMD segment N failed: work/mpirun.production.NNN.log, work/exchange.NNN.log` | MPI, GPU 또는 engine error입니다. | `run.sh`가 출력한 log 끝부분과 각 replica의 `production.NNN.out`을 확인합니다. 남은 partial output은 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구) 절차로 옮깁니다. |
| 특정 pair의 success rate가 0에 가까움 | 그 구간 temperature 간격이 넓습니다. | 새 `WORK_DIR`에서 `target_exchange_probability`를 높이거나 file mode로 그 구간에 temperature를 추가합니다. |

## English

This template builds AMBER temperature replica exchange from a user-prepared
protein PDB. In automatic mode, `build.sh` builds the configured protein/water
system and passes its solute/ion atom and water-molecule counts to the offline
temperature predictor. The default range is 300–450 K with a target neighboring
exchange probability of 0.20; the prediction only sets an initial schedule.

### File roles

| File | Role |
| --- | --- |
| `download.sh` | Downloads a structure by RCSB PDB ID into `structure/`. |
| `build.sh` | Builds the solvated system, temperature schedule and per-replica AMBER inputs. |
| `run.sh` | Runs per-replica pre-production and `pmemd.cuda.MPI -rem 1` production segments. |
| `config.toml` | Force field, box, salt, stage lengths and temperature-ladder settings. |
| `helpers/` | Leaf-local internal code called automatically by `build.sh` or `run.sh`; not an entry point. |

This directory can be copied and used on its own. Install its Python
dependencies (NumPy, ParmEd, and tomli below Python 3.11) from the local
`requirements.txt` after copying it. For AMBER (`tleap`, `pmemd.cuda`,
`pmemd.cuda.MPI`) and MPI, see the
[family README prerequisites](../README.md#prerequisites).

### Run

```bash
./download.sh 1UBQ
./build.sh structure/1UBQ.pdb
./run.sh --dry-run
./run.sh
```

`pmemd.cuda` runs preproduction. With the default
`production_ensemble = "NVT"`, minimization, heating and NPT equilibration run
once in `work/shared`, then each replica equilibrates at NVT in that box (see the
order below). Heating uses `minimize.rst7` for both `-c` and the
positional-restraint `-ref` input. Production uses `pmemd.cuda.MPI -rem 1`.

`AMBER_ENGINE` overrides `run.engine` in `work/resolved_config.toml`. The
accepted executable name is `pmemd.cuda`; installation paths are accepted.
Exchange production uses `AMBER_MPI_ENGINE` or `run.mpi_engine`, with
executable name `pmemd.cuda.MPI`. Empty overrides, missing engine settings and
unsupported executables fail instead of falling back to a default.

See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state, reruns after failure and
concurrent-run protection.

### Resources and length

| Item | Rule |
| --- | --- |
| Replica count | Rows in `work/states.tsv`; 68 for the default 1UBQ setup. |
| Pre-production | One `pmemd.cuda` process runs the shared stages and then each replica stage in turn. |
| Production MPI ranks | One per replica. A different `MPI_PROCESSES` is rejected before launch. |
| GPUs | `run.sh` does not assign GPUs. `pmemd.cuda.MPI` distributes ranks over the GPUs visible in `CUDA_VISIBLE_DEVICES` (Amber26 manual 24.6.5, p. 506). One GPU works but is slow because every rank shares it. |
| Launcher settings | `MPI_LAUNCHER` (default `mpirun`), `MPI_OPTIONS` (launcher options, node placement) and `AMBER_OPTIONS` (appended to every pmemd call). `AMBER_OPTIONS` is recorded in the input identity, so do not change it mid-run. |

Default lengths at 2 fs:

| Stage | Steps | Length per replica |
| --- | --- | --- |
| Shared heating / NPT equilibration | 250,000 / 500,000 | once, 0.5 ns / 1 ns |
| Replica NVT equilibration | 500,000 | 1 ns |
| Production segment | `nstlim=1000` × `numexchg=5000` | 10 ns |
| Full production | 10 segments | 100 ns (6.8 µs over 68 replicas) |

Each segment makes 5,000 exchange attempts. AMBER alternates even and odd
pairs, so each neighbor pair is attempted about 2,500 times per segment
(Amber26 manual 27.4.4.2, p. 582).

### Main outputs

- `work/states.tsv`: applied replica count, temperatures and seeds
- `work/system_counts.tsv`: atom/water counts given to the predictor and `used_target_exchange_probability`
- `work/resolved_config.toml`: applied settings
- `work/system.parm7`, `work/system.rst7`: shared topology and coordinate file referenced directly by every replica
- `work/NNN/production.NNN.in`, `production.NNN.nc`: per-replica segment inputs and trajectories
- `work/exchange.NNN.log`: exchange log for each segment
- `work/mpirun.production.NNN.log`: MPI stdout/stderr for each segment

Each finished segment prints `Completed: production.NNN (work)` and creates
`work/.production.NNN.complete`. After the last segment the final line is
`Completed T-REMD production: work`. With the defaults each replica's
`production.NNN.nc` holds 1,000 frames per segment (5,000,000 steps ÷
`trajectory_interval_steps` 5,000). `--preparation-only` ends with
`Preparation output: work/<replica>/equilibrate.rst7`.

### Reading exchange quality

The template has no `anal.py`; read the AMBER remlog `work/exchange.NNN.log`
directly. General criteria are in the
[family README](../README.md#reading-exchange-quality). The T-REMD remlog
writes one row per replica in each `# exchange N` block (Amber26 manual
27.4.4.2, p. 582).

| Column | Meaning |
| --- | --- |
| `Rep#` | Replica number starting at 1, in group-file order, so 1 is `work/000`. |
| `Velocity Scaling` | Velocity scaling factor after an accepted swap; `-1.00` after a rejected one. |
| `Temp0`, `NewTemp0` | Target temperature (K) before and after the attempt. |
| `Success rate (i,i+1)` | Cumulative acceptance between this row's `Temp0` and the next higher temperature. The highest-temperature row is usually 0. |

- Every segment is a new `pmemd.cuda.MPI` run, so success rates restart in each
  segment. Use the last `# exchange` block as that segment's pair acceptance;
  early blocks fluctuate because few attempts have been made.
- Replica numbers stay fixed and temperatures move. Follow one replica's
  `Temp0` through the exchanges to see ladder travel and round trips.
- From segment 2 on, the target temperature stored in the previous restart
  overrides the mdin `temp0` (p. 582). `work/NNN/` is therefore a replica
  identity, not a per-temperature trajectory. Select frames at one temperature
  with cpptraj `trajin ... remdtraj remdtrajtemp 300` (Amber26 manual 38.11.4,
  pp. 792–793).

cpptraj `remlog` computes acceptance, round trips and residence per state from
one segment log (Amber26 manual 38.13.30, pp. 927–928).

```bash
cpptraj <<'EOF'
readdata work/exchange.001.log as remlog nosearch name rem
remlog rem stats statsout rem.stats.dat reptime rem.reptime.dat acceptout rem.accept.dat
EOF
```

`acceptout` gives up/down acceptance (%) per replica, `statsout` the round
trips, and `reptime` the fraction of time each coordinate spent in each state.
The command was checked with AmberTools 26 cpptraj on a synthetic H-REMD-format
log only; reading a T-REMD `pmemd.cuda.MPI` log is unverified.

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to the shared equilibration (`work/shared/equilibrate.in`) with `NVT` production, and to each replica's equilibration with `NPT` production. |
| `production_ensemble` | `NVT`, `NPT` | `NVT` | Sets replica-production `ntb` and `ntp`. `NVT` adds the shared NPT stage below. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | Sets replica seeds and per-stage `ig`; see the seed rule below. |

| `temperature_mode` | Settings used | Settings ignored | Result |
| --- | --- | --- | --- |
| `auto` (default) | `minimum_temperature`, `maximum_temperature`, `target_exchange_probability`, `generator_tolerance` | `temperature_file` | Runs the predictor on the full solvated system and writes `work/states.tsv`. For 1UBQ the defaults (300–450 K, p=0.20) give 67 states, adjusted to 68 at p≈0.210 (checked with an AmberTools build). |
| `file` | `temperature_file` | Auto-ladder settings | Copies the file values in order into `work/states.tsv`. |

### Numeric options

| Key | Default | Unit | Stage | Effect |
| --- | ---: | --- | --- | --- |
| `build.solute_box_distance` | 14.0 | Å | build | Minimum solute-to-box-edge distance in LEaP solvation. |
| `build.salt_concentration` | 150.0 | mM | build | Bulk salt added after neutralization. |
| `run.temperature` | 300.0 | K | build | Must equal the first state temperature. Replica `temp0` comes from `work/states.tsv`. |
| `run.pressure` | 1.0 | bar | NPT stages | `pres0`. |
| `run.timestep` | 2.0 | fs | all MD | Written as AMBER `dt` (ps). Values above 2.0 are rejected because hydrogen masses are not repartitioned. |
| `run.minimization_steps` / `minimization_steepest_steps` | 5000 / 2500 | steps | minimization | `maxcyc` / `ncyc`. |
| `run.heating_initial_temperature` | 20.0 | K | heating | Start value of `tempi` and the `&wt TEMP0` ramp. |
| `run.heating_steps` | 250000 | steps | heating | Heating `nstlim`. |
| `run.equilibration_steps` | 500000 | steps | equilibration | `nstlim` of the shared NPT and replica NVT equilibration. |
| `run.production_steps` | 50000000 | steps | production | Total production per replica; must divide by the segment count. |
| `run.production_segments` | 10 | count | production | Number of restartable segments; each segment must divide by `exchange_interval_steps`. |
| `run.trajectory_interval_steps` | 5000 | steps | MD | `ntwx`. |
| `run.energy_interval_steps` | 5000 | steps | MD | `ntpr`. |
| `run.restart_interval_steps` | 5000 | steps | MD | `ntwr`. |
| `replica_exchange.minimum_temperature` / `maximum_temperature` | 300.0 / 450.0 | K | build (auto) | Ends of the auto ladder. |
| `replica_exchange.target_exchange_probability` | 0.20 | — | build (auto) | Predictor target for neighbor acceptance; raising it adds replicas. |
| `replica_exchange.generator_tolerance` | 0.0001 | — | build (auto) | Allowed difference between predicted pair probability and target. |
| `replica_exchange.exchange_interval_steps` | 1000 | steps | production | MD steps between exchanges (`nstlim`); `numexchg` is segment steps ÷ this value. |

### Replica count and temperature ladder

The replica count must be even and at least two. When the auto predictor returns
an odd count N, the temperature range and predictor algorithm are kept and the
target exchange probability is raised to give N+1 states. The largest target
that still gives N+1 is used, so every neighbor pair has nearly the same
predicted probability. The value used is printed by the build and stored as
`used_target_exchange_probability` in `work/system_counts.tsv`.

The auto ladder counts waters from a first-pass LEaP build. `build.sh --dry-run`
does not run the auto predictor, so the auto replica count is set by the actual
build.

Odd file schedules are rejected before LEaP, not adjusted. `run.sh --dry-run`
also checks the `work/states.tsv` count. The user must create the temperature
file. It accepts whitespace, commas, semicolons and `|` as separators; text
after `#` is a comment. It must contain at least two unique, increasing, finite
positive values, and its first value must equal `run.temperature`. `nan`, `inf`,
`-inf` and values outside the float range are rejected with the file path
before topology or inputs are saved.

### Seed rule

With `"random"`, each replica gets a random seed for heating `ig`, and
equilibration and production segments use `ig=-1` (wall-clock seed). With an
integer, the replica seed is `integer + 7919 × replica index`. Langevin dynamics
(`ntt=3`) needs a different `ig` on each restart, so each stage adds 1,000,000:
heating +0, equilibration +1,000,000, and production segment N
+(2+N)×1,000,000. The build therefore writes one
`work/<replica>/production.NNN.in` per segment.

### Production ensemble

The default is `production_ensemble = "NVT"`, the standard T-REMD setup. Running
replicas near 450 K at 1 bar NPT can change the water density strongly and make
the run unstable. NVT replica exchange needs every replica at the same volume,
so the original system is stabilized once at constant pressure before replica
equilibration starts (Amber26 manual, REMD section, p. 576). The order is:

| Order | Stage | Location | Temperature | Ensemble | Length |
| --- | --- | --- | --- | --- | --- |
| 1 | minimization | `work/shared` | — | fixed box | 5,000 cycles |
| 2 | heating | `work/shared` | 20 K → first replica | NVT | `heating_steps` |
| 3 | equilibration | `work/shared` | first replica | NPT | `equilibration_steps` |
| 4 | equilibration | `work/NNN` | replica | NVT | `equilibration_steps` |
| 5 | production | `work/NNN` | replica | NVT | `production_steps` |

Every replica starts stage 4 from the box in `work/shared/equilibrate.rst7`.
Stage 4 is the first equilibration at the replica temperature, so it uses the
same length as stage 3. The shared seed is random for `"random"` and
`integer + 7919 × replica count` for an integer.

With `production_ensemble = "NPT"`, there is no `work/shared`: each replica is
minimized, heated and NPT-equilibrated separately, and production also runs at
NPT.

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
| `production` | `production.NNN.in` |

Every replica gets the same values; per-replica values are not supported.

### Troubleshooting

| Message or symptom | Cause | Action |
| --- | --- | --- |
| `Config error: Replica exchange requires an even number of temperatures: ...` | The file-mode schedule has an odd count. | Add or remove one temperature and rebuild. |
| `Config error: timestep must be 2.0 fs or less without hydrogen mass repartitioning` | `run.timestep` exceeds 2 fs. | Set it to 2.0 or less. |
| `MPI_PROCESSES must equal the replica count: N` | The rank count differs from the replica count. | Unset `MPI_PROCESSES` or set it to N. |
| `Executable not found: ...` | `pmemd.cuda`, `pmemd.cuda.MPI` or the launcher is not on `PATH`. | Load the AMBER environment or set `AMBER_ENGINE`, `AMBER_MPI_ENGINE` or `MPI_LAUNCHER`. |
| `T-REMD segment N failed: work/mpirun.production.NNN.log, work/exchange.NNN.log` | MPI, GPU or engine error. | Read the log tail printed by `run.sh` and each replica's `production.NNN.out`. Move retained partial output as described in the [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery). |
| One pair's success rate stays near 0 | The temperature gap in that region is too wide. | In a new `WORK_DIR`, raise `target_exchange_probability` or add temperatures there in file mode. |
