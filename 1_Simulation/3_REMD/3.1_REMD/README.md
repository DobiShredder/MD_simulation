# Temperature REMD

## 한국어

Chignolin(PDB 1UAO)을 ff19SB/OPC로 만들고 18-replica T-REMD를 실행합니다.
Temperature는 300–373 K이며 replica당 production은 1 ns입니다.

T-REMD는 모든 replica에 같은 Hamiltonian을 사용하고 bath temperature만
바꿉니다. 높은 temperature replica는 barrier를 더 쉽게 넘고, 교환을 통해
그 configuration이 낮은 temperature ensemble로 이동합니다. Conventional MD는
한 temperature에서 barrier를 직접 넘어야 합니다. 분석에서는 walker가
temperature ladder를 왕복하는지와 300 K ensemble을 분리해 확인합니다.

### Script 역할

| 파일 | 역할 |
| --- | --- |
| `download.sh` | 1UAO PDB/mmCIF를 받고 checksum을 기록합니다. |
| `prepare.py` | 1UAO의 첫 NMR model을 simulation PDB로 정리합니다. |
| `build.sh` | ff19SB/OPC topology를 만들고 bundled state file의 temperature·seed로 replica input을 생성합니다. |
| `run.sh` | Replica별 heating/equilibration과 `pmemd.cuda.MPI` exchange calculation을 실행합니다. |
| `anal.py` | `remlog`에서 acceptance, state 방문, round trip과 temperature occupancy를 계산합니다. |

### 실행

Engine과 MPI 준비는 [family README의 준비 사항](../README.md#준비-사항)을
따릅니다. 이 예제는 AMBER 26 `tleap`, `pmemd.cuda`, `pmemd.cuda.MPI`, MPI
launcher와 Python 3 표준 library만 사용합니다.

```bash
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./build.sh structure/chignolin.pdb
./run.sh
python3 anal.py
```

`AMBER_ENGINE`, `AMBER_MPI_ENGINE`과 `MPI_LAUNCHER`로 executable을
바꿀 수 있습니다. MPI process 수는 bundled state 수와 같은 18로 고정됩니다.

Heating은 각 replica의 `minimize.rst7`을 `-c`와 positional restraint의 `-ref`
input으로 함께 사용합니다.

실행 상태, 실패 후 재실행, 동시 실행 보호는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을
참고합니다.

### 계산 resource와 길이

| Stage | 실행 방식 | Replica당 길이 | 18 replica 합계 |
| --- | --- | --- | --- |
| minimization | `pmemd.cuda`, replica를 하나씩 순서대로 | 5,000 cycles | — |
| heating 20 K → `temp0` (NVT) | `pmemd.cuda`, 순서대로 | 100,000 steps = 200 ps | 3.6 ns |
| equilibration (NPT) | `pmemd.cuda`, 순서대로 | 50,000 steps = 100 ps | 1.8 ns |
| production (NPT, `-rem 1`) | `mpirun -np 18 pmemd.cuda.MPI -ng 18` | 500 steps × 1,000 exchanges = 1 ns | 18 ns |

Pre-production은 GPU 하나로 replica를 차례로 계산합니다. Production은 replica당
MPI rank 하나, 즉 18 rank가 동시에 필요합니다. `run.sh`는 rank를 GPU에 배정하지
않으므로 scheduler, MPI launcher 설정 또는 `CUDA_VISIBLE_DEVICES`가 GPU 배치를
정합니다. GPU 하나로도 test할 수 있지만 18 rank가 같은 GPU를 나눠 쓰므로
느립니다.

### Output

- `work/NNN/production.nc`
- `work/exchange.log`
- `work/exchange_summary.tsv`
- `work/replica_visits.tsv`
- `work/temperature_occupancy.tsv`

정상 종료하면 `run.sh`가 `Completed 1 ns T-REMD: work`를 출력하고
`work/.production.complete`를 만듭니다. 각 `work/NNN/production.nc`에는
100 frame(500,000 steps ÷ `ntwx=5000`)이 있고, `work/exchange.log`에는
`# exchange 1`부터 `# exchange 1000`까지 block이 있습니다. 다음 단계인
`python3 anal.py`는 마지막에 `Exchange and temperature-visit summary: work`를
출력합니다.

T-REMD에서는 replica가 temperature를 교환하므로 `work/NNN/production.nc`는 한
temperature의 ensemble이 아니라 walker 하나의 trajectory입니다. 300 K
ensemble은 cpptraj `trajin ... remdtraj remdtrajtemp 300.0`(Amber 26 manual
cpptraj `trajin`)으로 다시 모읍니다. 이 command는 이 tutorial에서 실행해 보지
않았습니다(미검증).

`round_trips`는 처음 도달한 endpoint에서 반대 endpoint를 방문한 뒤 처음
endpoint로 돌아온 cycle 수입니다. 편도 이동과 같은 endpoint의 반복 방문은
왕복으로 세지 않습니다.

### Exchange 품질 해석

일반 기준은 [family README](../README.md#exchange-품질-해석)에 있습니다. 이
예제에서는 다음 file을 봅니다.

| File | Column | 확인할 내용 |
| --- | --- | --- |
| `exchange_summary.tsv` | `state_a`, `state_b`, `attempts`, `accepted`, `ratio` | 0-based 인접 temperature pair별 acceptance입니다. AMBER가 짝수/홀수 pair를 번갈아 시도하므로 pair당 약 500회 시도합니다. 0에 가까운 pair가 없어야 합니다. |
| `replica_visits.tsv` | `replica`, `min_state`, `max_state`, `round_trips` | Walker별 최저·최고 state와 왕복 횟수입니다. 여러 walker가 `0`과 `17`에 모두 닿아야 합니다. |
| `temperature_occupancy.tsv` | `replica`, `state`, `temperature_K`, `visits`, `fraction` | Walker가 각 temperature에 머문 exchange 기록의 비율입니다. 한쪽 끝에만 몰린 walker는 ladder가 끊긴 곳을 가리킵니다. |

`work/exchange.log`의 column은 `Rep#`, `Velocity Scaling`, `T`, `Eptot`,
`Temp0`, `NewTemp0`, `Success rate (i,i+1)`, `ResStruct#`입니다. `Velocity
Scaling`이 `-1.00`이면 교환이 reject된 것입니다. 마지막 `Success rate`는
누적 평균이므로 pair별 값은 `exchange_summary.tsv`에서 읽습니다.

기본 ladder는 예측 acceptance 0.20을 목표로 만들었습니다. ff19SB/OPC의 실제
값은 이와 다를 수 있습니다. 1 ns 교육용 계산에서는 round trip이 0이어도
실행 오류가 아닙니다. Acceptance와 round trip만으로 수렴을 판단하지 않습니다.

### 문제 해결

| Message 또는 증상 | 원인 | 조치 |
| --- | --- | --- |
| `Run ./build.sh first.` | `work/states.tsv`가 없습니다. | `./build.sh structure/chignolin.pdb`를 먼저 실행합니다. |
| `AMBER T-REMD requires at least two and an even number of states` | `states.tsv`의 state 수가 홀수이거나 2보다 작습니다. | Temperature를 하나 더하거나 빼서 짝수로 맞춥니다. |
| `Executable not found: pmemd.cuda.MPI` | AMBER environment가 load되지 않았거나 MPI build가 없습니다. | AMBER의 `amber.sh`를 source하거나 `AMBER_MPI_ENGINE`, `MPI_LAUNCHER`를 지정합니다. |
| `T-REMD production failed: work/mpirun.production.log, work/exchange.log` | 18 rank를 띄우지 못했거나 일부 replica가 중단되었습니다. | 출력된 `Missing/Unfinished replica output`과 `mpirun.production.log`를 보고 할당한 rank·GPU 수를 맞춥니다. |
| `Build output already exists and was retained` | 이전 build가 `work`에 남아 있습니다. | `mv work work.old` 후 다시 build합니다. |
| `exchange_summary.tsv`에서 일부 `ratio`가 0에 가까움 | 그 구간의 temperature 간격이 넓습니다. | `3_Templates/3_REMD/3.1_T-REMD`에서 replica를 늘리거나 ladder를 다시 만듭니다. |

그 밖의 partial output과 lock 처리는 GUIDE 부록을 따릅니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `-rem 1` | AMBER temperature REMD mode를 선택합니다. |
| `temp0=@TEMP@` | `states.tsv`의 replica별 target temperature로 치환됩니다. |
| `nstlim=500`, `numexchg=1000` | REMD에서 `nstlim`은 교환 사이의 step 수입니다. 500 steps(1 ps)마다 1,000회 교환하여 총 1 ns가 됩니다. |
| `dt=0.002` | Timestep 2 fs입니다. `ntc=2`, `ntf=2`로 hydrogen bond length를 고정합니다. |
| `ntt=3`, `gamma_ln=1.0` | Langevin thermostat와 collision frequency 1.0 ps⁻¹입니다. |
| `ntb=2`, `ntp=1`, `barostat=2`, `pres0=1.0` | Equilibration과 production을 Monte Carlo barostat, 1 bar NPT로 계산합니다. |
| `restraint_wt=5.0` | Heating에서 water·ion이 아닌 heavy atom에 거는 positional restraint(kcal mol⁻¹ Å⁻²)입니다. |
| `ntwx=5000`, `ntpr=5000` | 10 ps마다 trajectory frame과 energy를 기록합니다. Production은 replica당 100 frame입니다. |
| `cut=10.0` | Direct-space nonbonded cutoff 10 Å입니다. |
| `ig=@SEED@` | `states.tsv`의 replica seed로 치환됩니다. Langevin restart마다 다른 `ig`를 쓰도록 heating은 seed, equilibration은 seed+1,000,000, production은 seed+3,000,000을 사용합니다. |
| `build.sh INPUT.pdb` | 첫 argument의 PDB와 Chignolin용 `inputs/states.tsv`로 replica를 만듭니다. |
| `AMBER_MPI_ENGINE`, `MPI_LAUNCHER` | MPI executable과 launcher command를 바꿉니다. |

### Temperature ladder

기본 `inputs/states.tsv`는 OPC Chignolin의 140개 solute/ion atom과 1,755개
water molecule을 사용해 목표 인접 교환확률 0.20으로 계산한 18-replica
file입니다. 마지막 373 K state는 상한을 정확히 포함하므로 바로 아래 state와의
예측 acceptance가 목표값보다 높습니다.

```text
replica<TAB>temperature_K<TAB>seed
000<TAB>300.00000000<TAB>104729
001<TAB>304.15429688<TAB>112648
```

Replica ID는 `000`부터 시작하는 세 자리 고유 값이고 temperature는 행 순서대로
증가해야 합니다. `build.sh`는 bundled file을 `work/states.tsv`로 복사하며,
`run.sh`는 이 file에서 temperature와 replica 수를 읽습니다.

AMBER T-REMD는 최소 2개의 짝수 replica가 필요합니다. `build.sh`는
`inputs/states.tsv`, `run.sh`는 `work/states.tsv`의 state 수를 LEaP 또는 MD
실행 전에 검사하고 홀수 table을 자동 조정하지 않고 거부합니다.
`run.sh --dry-run`도 같은 검사를 적용합니다.

새 system에서는
[remd-temperature-generator](https://virtualchemistry.org/remd-temperature-generator/)에
실제 protein atom 수, water molecule 수, constraint, NPT temperature 범위와
목표 exchange probability를 입력해 `states.tsv`의 temperature를 정합니다.
이 predictor는 OPLS/AA와 GROMACS 자료로 보정되었으므로 ff19SB/AMBER에서
동일한 acceptance를 보장하지 않습니다. 짧은 pilot run의 adjacent acceptance와
round trip을 보고 replica 수와 temperature 간격을 다시 조정합니다. 다른
system과 temperature ladder는 `3_Templates/3_REMD/3.1_T-REMD`에서 설정합니다.

## English

This example builds ff19SB/OPC Chignolin (PDB 1UAO) and runs 18-replica T-REMD
from 300 to 373 K with 1 ns of production per replica.

T-REMD keeps one Hamiltonian and varies only the bath temperature.
High-temperature replicas cross barriers more readily, and accepted swaps move
those configurations down to the low-temperature ensemble. Conventional MD has
to cross barriers at a single temperature. The analysis checks whether walkers
travel the ladder and examines the 300 K ensemble separately.

### Script roles

| File | Role |
| --- | --- |
| `download.sh` | Downloads the 1UAO PDB/mmCIF and records checksums. |
| `prepare.py` | Cleans the first 1UAO NMR model into a simulation PDB. |
| `build.sh` | Builds the ff19SB/OPC topology and writes replica inputs from the bundled state file's temperatures and seeds. |
| `run.sh` | Runs per-replica heating/equilibration and the `pmemd.cuda.MPI` exchange calculation. |
| `anal.py` | Computes acceptance, state visits, round trips and temperature occupancy from `remlog`. |

### Run

Follow the [family README prerequisites](../README.md#prerequisites) for the
engine and MPI. This example needs AMBER 26 `tleap`, `pmemd.cuda`,
`pmemd.cuda.MPI`, an MPI launcher and only the Python 3 standard library.

```bash
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./build.sh structure/chignolin.pdb
./run.sh
python3 anal.py
```

`AMBER_ENGINE`, `AMBER_MPI_ENGINE` and `MPI_LAUNCHER` override the executables.
The runner launches one MPI process for each of the 18 bundled states.

Heating uses each replica's `minimize.rst7` for both `-c` and the
positional-restraint `-ref` input.

See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state, reruns after failure and
concurrent-run protection.

### Resources and length

| Stage | How it runs | Per replica | 18-replica total |
| --- | --- | --- | --- |
| minimization | `pmemd.cuda`, one replica after another | 5,000 cycles | — |
| heating 20 K → `temp0` (NVT) | `pmemd.cuda`, sequential | 100,000 steps = 200 ps | 3.6 ns |
| equilibration (NPT) | `pmemd.cuda`, sequential | 50,000 steps = 100 ps | 1.8 ns |
| production (NPT, `-rem 1`) | `mpirun -np 18 pmemd.cuda.MPI -ng 18` | 500 steps × 1,000 exchanges = 1 ns | 18 ns |

Pre-production runs the replicas one at a time on one GPU. Production needs
one MPI rank per replica, 18 ranks at once. `run.sh` does not assign ranks to
GPUs; the scheduler, MPI launcher settings or `CUDA_VISIBLE_DEVICES` decide the
placement. A single GPU works for testing, but all 18 ranks then share it and
the run is slow.

### Outputs

- `work/NNN/production.nc`
- `work/exchange.log`
- `work/exchange_summary.tsv`
- `work/replica_visits.tsv`
- `work/temperature_occupancy.tsv`

On success `run.sh` prints `Completed 1 ns T-REMD: work` and creates
`work/.production.complete`. Each `work/NNN/production.nc` holds 100 frames
(500,000 steps ÷ `ntwx=5000`), and `work/exchange.log` contains blocks
`# exchange 1` through `# exchange 1000`. The next step, `python3 anal.py`,
ends with `Exchange and temperature-visit summary: work`.

Because T-REMD replicas swap temperatures, `work/NNN/production.nc` is one
walker's trajectory, not a constant-temperature ensemble. Collect the 300 K
ensemble with cpptraj `trajin ... remdtraj remdtrajtemp 300.0` (Amber 26
manual, cpptraj `trajin`). This command has not been run in this tutorial
(unverified).

`round_trips` counts complete cycles from the first endpoint reached, through
the opposite endpoint, and back to the starting endpoint. One-way movement and
repeated visits to the same endpoint do not count.

### Reading exchange quality

General criteria are in the [family README](../README.md#reading-exchange-quality).
This example writes:

| File | Columns | What to check |
| --- | --- | --- |
| `exchange_summary.tsv` | `state_a`, `state_b`, `attempts`, `accepted`, `ratio` | Acceptance of each 0-based neighboring temperature pair. AMBER alternates even and odd pairs, so each pair gets about 500 attempts. No pair should be near zero. |
| `replica_visits.tsv` | `replica`, `min_state`, `max_state`, `round_trips` | Lowest and highest state and round trips per walker. Several walkers should reach both `0` and `17`. |
| `temperature_occupancy.tsv` | `replica`, `state`, `temperature_K`, `visits`, `fraction` | Fraction of exchange records a walker spent at each temperature. Walkers stuck at one end point to a break in the ladder. |

`work/exchange.log` columns are `Rep#`, `Velocity Scaling`, `T`, `Eptot`,
`Temp0`, `NewTemp0`, `Success rate (i,i+1)` and `ResStruct#`. A `Velocity
Scaling` of `-1.00` marks a rejected swap. The last `Success rate` is a running
average, so read per-pair values from `exchange_summary.tsv`.

The bundled ladder targets a predicted acceptance of 0.20; the actual
ff19SB/OPC values can differ. Zero round trips in a 1 ns training run are not a
run error. Acceptance and round trips alone do not establish convergence.

### Troubleshooting

| Message or symptom | Cause | Action |
| --- | --- | --- |
| `Run ./build.sh first.` | `work/states.tsv` is missing. | Run `./build.sh structure/chignolin.pdb` first. |
| `AMBER T-REMD requires at least two and an even number of states` | `states.tsv` has an odd count or fewer than two states. | Add or remove one temperature. |
| `Executable not found: pmemd.cuda.MPI` | AMBER is not loaded or has no MPI build. | Source AMBER's `amber.sh` or set `AMBER_MPI_ENGINE` and `MPI_LAUNCHER`. |
| `T-REMD production failed: work/mpirun.production.log, work/exchange.log` | The 18 ranks did not start, or some replicas stopped. | Read the printed `Missing/Unfinished replica output` lines and `mpirun.production.log`, then match the allocated ranks and GPUs. |
| `Build output already exists and was retained` | An earlier build remains in `work`. | Run `mv work work.old` and build again. |
| Some `ratio` values near zero in `exchange_summary.tsv` | The temperature gap there is too wide. | Add replicas or regenerate the ladder in `3_Templates/3_REMD/3.1_T-REMD`. |

Other partial-output and lock cases follow the GUIDE appendix.

### Key options

| Option | Meaning |
| --- | --- |
| `-rem 1` | Selects AMBER temperature REMD. |
| `temp0=@TEMP@` | Replaced by the replica's target temperature from `states.tsv`. |
| `nstlim=500`, `numexchg=1000` | In AMBER REMD, `nstlim` is the step count between exchange attempts. 1,000 attempts every 500 steps (1 ps) give 1 ns. |
| `dt=0.002` | 2 fs timestep; `ntc=2`, `ntf=2` constrain bonds to hydrogen. |
| `ntt=3`, `gamma_ln=1.0` | Langevin thermostat with a 1.0 ps⁻¹ collision frequency. |
| `ntb=2`, `ntp=1`, `barostat=2`, `pres0=1.0` | Equilibration and production run NPT at 1 bar with the Monte Carlo barostat. |
| `restraint_wt=5.0` | Positional restraint (kcal mol⁻¹ Å⁻²) on non-water, non-ion heavy atoms during heating. |
| `ntwx=5000`, `ntpr=5000` | Write a trajectory frame and energies every 10 ps; production gives 100 frames per replica. |
| `cut=10.0` | 10 Å direct-space nonbonded cutoff. |
| `ig=@SEED@` | Replaced by the replica seed from `states.tsv`. Langevin dynamics needs a different `ig` on each restart, so heating uses the seed, equilibration adds 1,000,000, and production adds 3,000,000. |
| `build.sh INPUT.pdb` | Builds replicas from the PDB in the first argument and the Chignolin `inputs/states.tsv`. |
| `AMBER_MPI_ENGINE`, `MPI_LAUNCHER` | Override the MPI executable and launcher command. |

### Temperature ladder

The bundled `inputs/states.tsv` is precomputed for OPC Chignolin from 140
solute/ion atoms and 1,755 water molecules at a target neighboring exchange
probability of 0.20. The final state is clipped to the exact 373 K upper bound,
so its predicted acceptance with the preceding state is higher than the target.

```text
replica<TAB>temperature_K<TAB>seed
000<TAB>300.00000000<TAB>104729
001<TAB>304.15429688<TAB>112648
```

Replica IDs are unique three-digit values starting at `000`, and temperatures
increase by row. `build.sh` copies the bundled file to `work/states.tsv`, and
`run.sh` reads temperatures and the replica count from it.

AMBER T-REMD requires an even number of at least two replicas. `build.sh` checks
`inputs/states.tsv` and `run.sh` checks `work/states.tsv` before LEaP or MD
execution; odd tables are rejected, not adjusted. `run.sh --dry-run` applies the
same check.

For a new system, generate `states.tsv` temperatures with the
[remd-temperature-generator](https://virtualchemistry.org/remd-temperature-generator/)
using the actual protein-atom and water-molecule counts, constraints, NPT
temperature range and target exchange probability. Its model was calibrated
with OPLS/AA and GROMACS, so it does not guarantee the same acceptance with
ff19SB/AMBER. Adjust the replica count and spacing from adjacent acceptance and
round trips in a short pilot run. Use `3_Templates/3_REMD/3.1_T-REMD` for another
system or temperature ladder.
