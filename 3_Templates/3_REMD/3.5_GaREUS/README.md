# GaREUS template

## 한국어

REUS의 umbrella-state 교환에 system 전체의 dual-boost GaMD를 결합합니다.
Reaction-coordinate mask, center, force와 exchange interval은 REUS와 같습니다.
각 mask는 atom 하나(`iat`) 또는 atom group(`igr1`/`igr2`, center of mass)을
선택할 수 있습니다. 자세한 규칙은 [REUS README](../3.4_REUS/README.md#reaction-coordinate-mask)를
참고합니다.
한 reference replica에서 만든 `gamd-restart.dat`를 모든 window에 복사하므로
production 시작 시 같은 boost parameter를 사용합니다.

### 파일 역할

| 파일 | 역할 |
| --- | --- |
| `download.sh` | `download.sh PDB_ID`로 source PDB를 받습니다. |
| `build.sh` | Topology, window와 GaMD input을 생성합니다. REUS와 같은 window/restraint generator에 GaMD parameter-preparation input을 추가합니다. |
| `run.sh` | 공통 preproduction, window equilibration, 공통 GaMD preparation과 AMBER `-rem 3` GaREUS production을 실행합니다. 실제 실행에는 `--allow-unverified`가 필요합니다. |
| `config.toml` | Force field, box, stage 길이, umbrella center 목록을 포함한 `[umbrella]`와 `[gamd]` 설정입니다. |
| `helpers/` | `build.sh` 또는 `run.sh`가 자동 호출하는 leaf-local 내부 code이며 직접 실행하지 않습니다. `generate_inputs.py`는 LEaP input과 resolved 설정을, `make_window_replicas.py`는 window별 MD input과 restraint를 만듭니다. |

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`(NumPy, ParmEd, Python 3.11 미만이면 tomli)로
설치합니다. AMBER(`tleap`, `pmemd.cuda`, `pmemd.cuda.MPI`)와 MPI는
[family README의 준비 사항](../README.md#준비-사항)을 참고합니다.

### 실행

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh --allow-unverified
```

`gamd-restart.dat`은 filename이 고정되어 있고 multipmemd group file은 모든
replica를 이 directory에서 실행합니다. Amber 26 GPU multipmemd에서 replica별
GaMD state read/write가 분리되는지는 미검증이므로 실제 실행에는
`--allow-unverified`가 필요합니다. `--dry-run`은 이 argument 없이 실행됩니다.

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
| Replica 수 | `umbrella.centers`의 center 수입니다. 기본 20개입니다. |
| Pre-production | `pmemd.cuda` process 하나가 shared stage, window별 equilibration, reference window의 GaMD preparation을 순서대로 실행합니다. |
| Production MPI rank | Window당 1개입니다. `MPI_PROCESSES`가 window 수와 다르면 시작 전에 거부합니다. |
| GPU | `run.sh`는 GPU를 지정하지 않습니다. `pmemd.cuda.MPI`는 `CUDA_VISIBLE_DEVICES`에 보이는 GPU를 rank에 나눠 씁니다(Amber26 manual 24.6.5, p. 506). GPU 1개로도 실행되지만 모든 rank가 나눠 쓰므로 느립니다. |
| Launcher 설정 | `MPI_LAUNCHER`(기본 `mpirun`), `MPI_OPTIONS`(launcher option, node 배치), `AMBER_OPTIONS`(모든 pmemd 호출에 추가)를 씁니다. `AMBER_OPTIONS`는 input identity에 기록되므로 실행 도중 바꾸지 않습니다. |

기본 config(2 fs)에서 계산 길이는 다음과 같습니다.

| Stage | Steps | 길이 |
| --- | --- | --- |
| Shared heating / NPT equilibration | 250,000 / 250,000 | 한 번만 0.5 ns / 0.5 ns |
| Window NVT equilibration | 250,000 | Window당 0.5 ns |
| GaMD preparation | `ntcmd` 1,000,000 + `nteb` 1,000,000 | Reference window에서 한 번 4 ns |
| Production segment | `nstlim=1000` × `numexchg=5000` | Window당 10 ns |
| Production 전체 | 20 segments | Window당 200 ns(20 windows 합계 4 µs) |

Segment마다 exchange를 5,000번 시도하며 인접 pair 하나는 약 2,500번
시도됩니다(Amber26 manual 27.4.4.2, p. 582).

### 공통 NPT stage와 window NVT stage

Production이 NVT이면 모든 window의 부피가 같아야 합니다. AMBER manual(REMD 절)에
따라 원래 system을 한 번 constant pressure로 안정화한 뒤 window equilibration을
시작합니다.

| 순서 | Stage | 위치 | Ensemble | 길이 config |
| --- | --- | --- | --- | --- |
| 1 | minimization | `work/shared` | 고정 box | `minimization_steps` |
| 2 | heating | `work/shared` | NVT | `heating_steps` |
| 3 | equilibration | `work/shared` | `equilibration_ensemble`(NPT) | `equilibration_steps` (기본 250,000) |
| 4 | window equilibration | `work/NNN` | NVT, window restraint | `window_equilibration_steps` (기본 250,000) |
| 5 | GaMD preparation | reference window | `production_ensemble` | `[gamd]` |

1–3은 window restraint 없이 한 번 실행합니다. 모든 window는
`work/shared/equilibrate.rst7`의 box와 velocity에서 4를 시작합니다. 기본값에서
한 window가 거치는 equilibration은 250,000 + 250,000 = 500,000 steps입니다. 4는
config와 관계없이 NVT입니다. Build는 `equilibration_ensemble`이 `NPT`가 아니면
거부합니다.

Window equilibration과 GaMD preparation은 replica directory 안에서 실행되므로
`DISANG=distance.RST`와 `DUMPAVE=restraint.equilibrate.dat` 또는
`restraint.gamd_prepare.dat`를 씁니다. Build는 production segment마다
`production.NNN.template.in`을 만듭니다. Exchange production은 group file로 이
directory에서 실행되므로 `run.sh`가 segment 시작 직전 `@DISANG@`과
`@DUMPAVE@`를 `work/<replica>/distance.RST`와
`work/<replica>/restraint.production.NNN.dat`로 바꿔 `production.NNN.in`을
씁니다.

### GaMD state 이어받기

기본 20개 window는 6–25 Å이며 replica 009에서 공통 GaMD state를 준비합니다.
준비가 끝나면 각 replica에 `gamd-restart.dat`와 `prepared.gamd.rst` snapshot을
둡니다. 첫 production segment는 `prepared.gamd.rst`, segment N은
`production.(N-1).gamd.rst`에서 GaMD state를 이어받습니다. 각 segment가 끝나면
`gamd-restart.dat`를 `production.NNN.gamd.rst`로 복사합니다.
`gamd-restart.dat`는 segment 동안 갱신되는 engine output입니다. MD restart,
window restraint와 GaMD state 중 하나라도 partial이면 production을 덮어쓰지
않습니다.

### 주요 output

- `work/states.tsv`: window와 center의 최종 mapping
- `work/system.parm7`, `work/system.rst7`: 모든 replica가 직접 참조하는 공통 topology와 coordinate file
- `work/shared/`: 공통 minimization, heating, NPT equilibration output
- `work/<replica>/production.NNN.nc`, `restraint.production.NNN.dat`, `gamd.production.NNN.log`: segment별 trajectory, restraint 기록과 GaMD log
- `work/<replica>/prepared.gamd.rst`, `production.NNN.gamd.rst`: GaMD state snapshot
- `work/exchange.NNN.log`: segment별 exchange log
- `work/mpirun.production.NNN.log`: segment별 MPI stdout/stderr

Segment가 끝날 때마다 `Completed: production.NNN (work)`가 출력되고
`work/.production.NNN.complete`가 생깁니다. 모든 segment가 끝나면 마지막 줄은
`Completed GaREUS production: work`입니다. 기본값에서 window별
`production.NNN.nc`와 `gamd.production.NNN.log`는 segment당 1,000 frame/행
(5,000,000 steps ÷ `trajectory_interval_steps` 5,000)입니다. GaMD log는 `ntwx`마다
기록됩니다(Amber26 manual 26.3, p. 524). `--preparation-only`는
`Preparation output: work/<replica>/production_start.rst7 and gamd-restart.dat`로
끝납니다.

### Exchange 품질 해석

Remlog 형식, column 의미, segment별 success rate와 window overlap 확인은
[REUS README](../3.4_REUS/README.md#exchange-품질-해석)와 같습니다. 일반 판단
기준은 [family README의 Exchange 품질 해석](../README.md#exchange-품질-해석)을
따릅니다. GaREUS에서는 다음을 함께 확인합니다.

- 모든 window가 같은 `gamd-restart.dat`에서 시작했는지 확인합니다. `run.sh`는
  복사 후 `cmp`로 비교하며, 다르면 production을 시작하지 않습니다.
- `restraint.production.NNN.dat` histogram은 boost가 걸린 ensemble의 분포입니다.
  PMF는 umbrella bias와 GaMD boost를 모두 reweighting해야 하며, 방법은
  [7.3 analysis tutorial](../../../2_Analysis/7_Enhanced_Sampling/7.3_GaREUS_Reweighting/README.md)을
  참고합니다. 그 script는 tutorial의 단일 production file 이름을 읽으므로
  template의 segment별 file에 맞게 경로를 바꿔야 합니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | 공통 equilibration(`work/shared/equilibrate.in`)에 적용합니다. Window equilibration은 항상 NVT입니다. |
| `production_ensemble` | `NVT`, `NPT` | `NVT` | GaMD exchange production의 `ntb`와 `ntp`를 설정합니다. |
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
| `run.heating_steps` | 250000 | step | shared heating | Heating `nstlim`입니다. |
| `run.equilibration_steps` | 250000 | step | shared equilibration | Box 부피를 정하는 shared NPT stage의 `nstlim`입니다. |
| `run.window_equilibration_steps` | 250000 | step | window equilibration | Restraint를 건 window NVT stage의 `nstlim`입니다. |
| `run.production_steps` | 100000000 | step | production | Window당 전체 production입니다. Segment 수로 나누어떨어져야 합니다. |
| `run.production_segments` | 20 | 개 | production | Restart 가능한 segment 수입니다. Segment 길이는 `exchange_interval_steps`로 나누어떨어져야 합니다. |
| `run.trajectory_interval_steps` | 5000 | step | MD | `ntwx`이며 GaMD log 간격도 정합니다. |
| `run.energy_interval_steps` | 5000 | step | MD | `ntpr`입니다. |
| `run.restart_interval_steps` | 5000 | step | MD | `ntwr`입니다. |
| `umbrella.force_constant` | 1.0 | kcal mol⁻¹ Å⁻² | window stage | `distance.RST`의 `rk2`, `rk3`입니다. |
| `umbrella.exchange_interval_steps` | 1000 | step | production | Exchange 사이 MD step(`nstlim`)입니다. `numexchg`는 segment step ÷ 이 값입니다. |
| `umbrella.distance_output_interval_steps` | 500 | step | window stage | `&wt type='DUMPFREQ'`로 `DUMPAVE` 기록 간격을 정합니다. |
| `gamd.reference_replica` | 9 | window index | GaMD preparation | 공통 GaMD state를 만들 window입니다(0부터, 기본 `work/009`). Build가 0부터 window 수−1 범위를 검사합니다. |
| `gamd.conventional_preparation_steps` | 200000 | step | GaMD preparation | `ntcmdprep`입니다. Potential 통계를 모으지 않는 cMD 구간입니다. |
| `gamd.conventional_statistics_steps` | 1000000 | step | GaMD preparation | `ntcmd`입니다. `ntcmdprep` 이후 Vmax, Vmin, Vavg, σV를 모읍니다. |
| `gamd.boost_preparation_steps` | 200000 | step | GaMD preparation | `ntebprep`입니다. Boost를 건 뒤 통계를 갱신하지 않는 구간입니다. |
| `gamd.boost_statistics_steps` | 1000000 | step | GaMD preparation | `nteb`입니다. 통계와 E, k0를 갱신합니다. Preparation `nstlim`은 `ntcmd + nteb`입니다. |
| `gamd.averaging_interval_steps` | 50000 | step | GaMD preparation, production | `ntave`입니다. 위 네 step 값은 이 값의 배수여야 합니다(Amber26 manual 26.3, p. 526). |
| `gamd.sigma0` | 6.0 | kcal/mol | GaMD preparation, production | `sigma0P`와 `sigma0D`에 같은 값을 씁니다. Boost potential 표준편차의 상한입니다. |

Segment마다 `exchange.NNN.log`가 따로 생기며, 끊긴 계산은
`./run.sh --allow-unverified --segments N-20`으로 이어서 실행합니다.

### Window와 force constant

`umbrella.centers`는 center를 Å 단위로 나열한 TOML array이며 `auto`/`file`
mode가 없습니다. 기본값은 `[6.0, 7.0, ..., 25.0]`입니다. 값은 양수이고 중복 없이
오름차순이어야 하며, 각 값이 한 exchange state가 됩니다. Replica 수는 2 이상의
짝수여야 하며 `build.sh`와 `run.sh`는 홀수 schedule을 자동 조정하지 않고
거부합니다. `run.sh --dry-run`도 같은 검사를 합니다. Center는 `build.sh`만
읽으므로 build 뒤 center를 바꾸면 새 `WORK_DIR`에서 다시 build합니다.

기본 `force_constant = 1.0`(AMBER `rk`)은 1 Å 간격에서 예상 인접 교환 확률 약
0.2입니다(미검증).

### Seed 규칙

`"random"`이면 공통 heating에 무작위 seed를 쓰고, 나머지 stage는 `ig=-1`로
실행 시각에서 seed를 정합니다. 정수이면 window seed는
`정수 + 7919 × window index`이고 공통 seed는 `정수 + 7919 × window 수`입니다.
Langevin dynamics(`ntt=3`)는 restart마다 다른 `ig`를 써야 하므로 stage마다
1,000,000을 더합니다. 공통 heating은 +0, 공통 equilibration과 window
equilibration은 각 seed에 +1,000,000, GaMD preparation은 +2,000,000,
production segment N은 +(2+N)×1,000,000입니다.

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
| `production` | `gamd_prepare.in`, `production.NNN.template.in` |

GaMD parameter preparation(`gamd_prepare.in`)도 production stage입니다. 모든 window에 같은 값을 씁니다.

### 문제 해결

| Message 또는 증상 | 원인 | 조치 |
| --- | --- | --- |
| `Error: actual execution requires ./run.sh --allow-unverified.` | 검증 범위를 확인하는 opt-in이 없습니다. | 위 실행 절의 미검증 내용을 읽고 `--allow-unverified`를 붙입니다. |
| `Config error: gamd.reference_replica must be a window index from 0 to N` | Reference window index가 범위 밖입니다. | `umbrella.centers` 순서 기준 0부터 시작하는 index로 고칩니다. |
| `Build did not complete: work/build.done is missing; ...` | Build가 중간에 실패했습니다. Mask와 `umbrella.centers` error는 [REUS README](../3.4_REUS/README.md#문제-해결)와 같습니다. | Build error를 확인하고 `mv work work.old` 후 다시 build합니다. |
| `GaMD parameter preparation failed: work/NNN/gamd_prepare.out` | Reference window의 GaMD preparation이 실패했습니다. | `gamd_prepare.out`, `engine.gamd_prepare.log`와 `gamd.prepare.log`를 확인합니다. |
| `GaREUS segment N failed: work/mpirun.production.NNN.log, work/exchange.NNN.log` | MPI, GPU 또는 engine error입니다. | `run.sh`가 출력한 log 끝부분과 각 window의 `production.NNN.out`을 확인합니다. 남은 partial output은 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구) 절차로 옮깁니다. |
| `GaMD continuation state missing: work/NNN/gamd-restart.dat` | Segment 뒤 GaMD state가 없습니다. | 그 segment output을 partial로 보고 GUIDE 부록 절차로 옮긴 뒤 다시 실행합니다. |

## English

GaREUS combines REUS umbrella-state exchange with a system-wide dual-boost
GaMD. Reaction-coordinate masks, centers, force and exchange interval follow
REUS. Each mask selects one atom (`iat`) or an atom group (`igr1`/`igr2`, center
of mass); see the [REUS README](../3.4_REUS/README.md#reaction-coordinate-masks)
for the rules. One reference replica prepares `gamd-restart.dat`, which is copied to all
windows, so production starts with the same boost parameters everywhere.

### File roles

| File | Role |
| --- | --- |
| `download.sh` | Downloads a source PDB with `download.sh PDB_ID`. |
| `build.sh` | Creates the topology, windows and GaMD inputs. It extends the REUS window/restraint generator with GaMD parameter-preparation input. |
| `run.sh` | Runs shared preproduction, window equilibration, shared GaMD preparation and AMBER `-rem 3` GaREUS production. Actual execution requires `--allow-unverified`. |
| `config.toml` | Force field, box, stage lengths, `[umbrella]` settings including the center list, and `[gamd]` settings. |
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
./run.sh --allow-unverified
```

`gamd-restart.dat` has a fixed filename, and the multipmemd group file runs
every replica from this directory. Separate per-replica GaMD state reads and
writes with Amber 26 GPU multipmemd are unverified, so actual execution requires
`--allow-unverified`. `--dry-run` works without it.

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
| Replica count | Number of values in `umbrella.centers`; 20 by default. |
| Pre-production | One `pmemd.cuda` process runs the shared stages, each window's equilibration and the GaMD preparation in the reference window, in turn. |
| Production MPI ranks | One per window. A different `MPI_PROCESSES` is rejected before launch. |
| GPUs | `run.sh` does not assign GPUs. `pmemd.cuda.MPI` distributes ranks over the GPUs visible in `CUDA_VISIBLE_DEVICES` (Amber26 manual 24.6.5, p. 506). One GPU works but is slow because every rank shares it. |
| Launcher settings | `MPI_LAUNCHER` (default `mpirun`), `MPI_OPTIONS` (launcher options, node placement) and `AMBER_OPTIONS` (appended to every pmemd call). `AMBER_OPTIONS` is recorded in the input identity, so do not change it mid-run. |

Default lengths at 2 fs:

| Stage | Steps | Length |
| --- | --- | --- |
| Shared heating / NPT equilibration | 250,000 / 250,000 | once, 0.5 ns / 0.5 ns |
| Window NVT equilibration | 250,000 | 0.5 ns per window |
| GaMD preparation | `ntcmd` 1,000,000 + `nteb` 1,000,000 | 4 ns once, in the reference window |
| Production segment | `nstlim=1000` × `numexchg=5000` | 10 ns per window |
| Full production | 20 segments | 200 ns per window (4 µs over 20 windows) |

Each segment makes 5,000 exchange attempts, about 2,500 per neighbor pair
(Amber26 manual 27.4.4.2, p. 582).

### Shared NPT stage and window NVT stage

With NVT production every window must share one volume. Following the AMBER
manual (REMD section), the original system is stabilized once at constant
pressure before window equilibration starts.

| Order | Stage | Location | Ensemble | Length key |
| --- | --- | --- | --- | --- |
| 1 | minimization | `work/shared` | fixed box | `minimization_steps` |
| 2 | heating | `work/shared` | NVT | `heating_steps` |
| 3 | equilibration | `work/shared` | `equilibration_ensemble` (NPT) | `equilibration_steps` (default 250,000) |
| 4 | window equilibration | `work/NNN` | NVT, window restraint | `window_equilibration_steps` (default 250,000) |
| 5 | GaMD preparation | reference window | `production_ensemble` | `[gamd]` |

Stages 1–3 run once without window restraints. Every window starts stage 4 from
the box and velocities in `work/shared/equilibrate.rst7`. With the defaults,
each window sees 250,000 + 250,000 = 500,000 equilibration steps. Stage 4 is
NVT regardless of the config, and the build rejects an `equilibration_ensemble`
other than `NPT`.

Window equilibration and GaMD preparation run inside each replica directory, so
they use `DISANG=distance.RST` and `DUMPAVE=restraint.equilibrate.dat` or
`restraint.gamd_prepare.dat`. The build writes one
`production.NNN.template.in` per production segment. Exchange production runs
from this directory through the group file, so `run.sh` replaces `@DISANG@` and
`@DUMPAVE@` with `work/<replica>/distance.RST` and
`work/<replica>/restraint.production.NNN.dat` and writes `production.NNN.in`
just before the segment starts.

### GaMD state continuation

The default has 20 windows from 6 to 25 Å and prepares the shared GaMD state in
replica 009. After preparation, each replica holds `gamd-restart.dat` and a
`prepared.gamd.rst` snapshot. The first production segment continues GaMD state
from `prepared.gamd.rst`, and segment N from `production.(N-1).gamd.rst`. After
each segment, `gamd-restart.dat` is copied to `production.NNN.gamd.rst`.
`gamd-restart.dat` is the evolving engine output during a segment. Partial MD
restart, window restraint or GaMD state is not overwritten.

### Main outputs

- `work/states.tsv`: final window-to-center mapping
- `work/system.parm7`, `work/system.rst7`: shared topology and coordinate file referenced directly by every replica
- `work/shared/`: shared minimization, heating and NPT equilibration outputs
- `work/<replica>/production.NNN.nc`, `restraint.production.NNN.dat`, `gamd.production.NNN.log`: per-segment trajectory, restraint record and GaMD log
- `work/<replica>/prepared.gamd.rst`, `production.NNN.gamd.rst`: GaMD state snapshots
- `work/exchange.NNN.log`: exchange log for each segment
- `work/mpirun.production.NNN.log`: MPI stdout/stderr for each segment

Each finished segment prints `Completed: production.NNN (work)` and creates
`work/.production.NNN.complete`. After the last segment the final line is
`Completed GaREUS production: work`. With the defaults each window's
`production.NNN.nc` and `gamd.production.NNN.log` hold 1,000 frames/rows per
segment (5,000,000 steps ÷ `trajectory_interval_steps` 5,000); the GaMD log is
written every `ntwx` steps (Amber26 manual 26.3, p. 524). `--preparation-only`
ends with `Preparation output: work/<replica>/production_start.rst7 and gamd-restart.dat`.

### Reading exchange quality

The remlog format, column meanings, per-segment success rates and the window
overlap check are the same as in the
[REUS README](../3.4_REUS/README.md#reading-exchange-quality). General criteria
are in the [family README](../README.md#reading-exchange-quality). For GaREUS
also check the following.

- Every window must start from the same `gamd-restart.dat`. `run.sh` compares
  the copies with `cmp` and does not start production if they differ.
- Histograms of `restraint.production.NNN.dat` describe the boosted ensemble. A
  PMF has to reweight both the umbrella bias and the GaMD boost; see the
  [7.3 analysis tutorial](../../../2_Analysis/7_Enhanced_Sampling/7.3_GaREUS_Reweighting/README.md).
  Its scripts read the tutorial's single-production file names, so adapt the
  paths to the template's per-segment files.

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to the shared equilibration (`work/shared/equilibrate.in`). Window equilibration is always NVT. |
| `production_ensemble` | `NVT`, `NPT` | `NVT` | Sets GaMD exchange-production `ntb` and `ntp`. |
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
| `run.heating_steps` | 250000 | steps | shared heating | Heating `nstlim`. |
| `run.equilibration_steps` | 250000 | steps | shared equilibration | `nstlim` of the shared NPT stage that fixes the box volume. |
| `run.window_equilibration_steps` | 250000 | steps | window equilibration | `nstlim` of the restrained window NVT stage. |
| `run.production_steps` | 100000000 | steps | production | Total production per window; must divide by the segment count. |
| `run.production_segments` | 20 | count | production | Number of restartable segments; each segment must divide by `exchange_interval_steps`. |
| `run.trajectory_interval_steps` | 5000 | steps | MD | `ntwx`; also sets the GaMD log interval. |
| `run.energy_interval_steps` | 5000 | steps | MD | `ntpr`. |
| `run.restart_interval_steps` | 5000 | steps | MD | `ntwr`. |
| `umbrella.force_constant` | 1.0 | kcal mol⁻¹ Å⁻² | window stages | `rk2`, `rk3` in `distance.RST`. |
| `umbrella.exchange_interval_steps` | 1000 | steps | production | MD steps between exchanges (`nstlim`); `numexchg` is segment steps ÷ this value. |
| `umbrella.distance_output_interval_steps` | 500 | steps | window stages | `DUMPAVE` interval set through `&wt type='DUMPFREQ'`. |
| `gamd.reference_replica` | 9 | window index | GaMD preparation | Window that prepares the shared GaMD state (0-based; `work/009` by default). The build checks the range 0 to window count − 1. |
| `gamd.conventional_preparation_steps` | 200000 | steps | GaMD preparation | `ntcmdprep`: cMD without collecting potential statistics. |
| `gamd.conventional_statistics_steps` | 1000000 | steps | GaMD preparation | `ntcmd`: collects Vmax, Vmin, Vavg and σV after `ntcmdprep`. |
| `gamd.boost_preparation_steps` | 200000 | steps | GaMD preparation | `ntebprep`: boosted MD without updating the statistics. |
| `gamd.boost_statistics_steps` | 1000000 | steps | GaMD preparation | `nteb`: updates the statistics, E and k0. Preparation `nstlim` is `ntcmd + nteb`. |
| `gamd.averaging_interval_steps` | 50000 | steps | GaMD preparation, production | `ntave`. The four step counts above must be multiples of it (Amber26 manual 26.3, p. 526). |
| `gamd.sigma0` | 6.0 | kcal/mol | GaMD preparation, production | Used for both `sigma0P` and `sigma0D`; upper limit of the boost-potential standard deviation. |

Each segment writes its own `exchange.NNN.log`; resume an interrupted run with
`./run.sh --allow-unverified --segments N-20`.

### Windows and force constant

`umbrella.centers` is a TOML array of centers in Å; there is no `auto`/`file`
mode. The default is `[6.0, 7.0, ..., 25.0]`. Values must be positive, unique
and increasing, and each value becomes one exchange state. The replica count
must be even and at least two; `build.sh` and `run.sh` reject odd schedules
without adjusting them, and `run.sh --dry-run` applies the same check. Only
`build.sh` reads the centers, so rebuild in a new `WORK_DIR` after changing them.

The default `force_constant = 1.0` (AMBER `rk`) gives a predicted neighbor
acceptance of about 0.2 at 1 Å spacing (unverified).

### Seed rule

With `"random"`, shared heating gets a random seed and every other stage uses
`ig=-1` (wall-clock seed). With an integer, the window seed is
`integer + 7919 × window index` and the shared seed is
`integer + 7919 × window count`. Langevin dynamics (`ntt=3`) needs a different
`ig` on each restart, so each stage adds 1,000,000: shared heating +0, shared
and window equilibration +1,000,000 on their own seed, GaMD preparation
+2,000,000, and production segment N +(2+N)×1,000,000.

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
| `production` | `gamd_prepare.in`, `production.NNN.template.in` |

GaMD parameter preparation (`gamd_prepare.in`) is a production stage. Every window gets the same values.

### Troubleshooting

| Message or symptom | Cause | Action |
| --- | --- | --- |
| `Error: actual execution requires ./run.sh --allow-unverified.` | The opt-in for the unverified scope is missing. | Read the unverified item in the run section and add `--allow-unverified`. |
| `Config error: gamd.reference_replica must be a window index from 0 to N` | The reference window index is out of range. | Use a 0-based index in `umbrella.centers` order. |
| `Build did not complete: work/build.done is missing; ...` | The build failed partway. Mask and `umbrella.centers` errors match the [REUS README](../3.4_REUS/README.md#troubleshooting). | Read the build error, `mv work work.old`, and rebuild. |
| `GaMD parameter preparation failed: work/NNN/gamd_prepare.out` | GaMD preparation in the reference window failed. | Check `gamd_prepare.out`, `engine.gamd_prepare.log` and `gamd.prepare.log`. |
| `GaREUS segment N failed: work/mpirun.production.NNN.log, work/exchange.NNN.log` | MPI, GPU or engine error. | Read the log tail printed by `run.sh` and each window's `production.NNN.out`. Move retained partial output as described in the [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery). |
| `GaMD continuation state missing: work/NNN/gamd-restart.dat` | The GaMD state is missing after a segment. | Treat that segment's output as partial, move it as described in the GUIDE appendix, and rerun. |
