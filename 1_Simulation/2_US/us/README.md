# AMBER umbrella windows / AMBER umbrella window

## 한국어

Ratchet MD restart를 seed로 6–24 Å 범위의 19개 umbrella window를 실행합니다.
모든 window는 같은 `system.parm7`을 사용합니다.

각 window의 harmonic restraint는 중심 주변 sampling을 늘리지만 window 밖의
구조를 금지하지는 않습니다. Neighboring histogram이 겹쳐야 PMF offset을
연결할 수 있으므로 center 간격과 force constant는 함께 조정합니다.

### 파일 역할

| 파일 | 역할 |
| --- | --- |
| `windows.tsv` | Window center(Å)와 force constant를 증가 순서로 정의합니다. |
| `build.sh` | 공통 topology와 ratchet seed를 검증하고 window directory와 `restraint.RST`를 만듭니다. |
| `inputs/restraint.RST.template` | AMBER NMR-style distance restraint의 atom index와 형태를 정의합니다. |
| `run.sh` | 선택한 window 또는 모든 window의 네 stage를 실행합니다. |
| `inputs/continue.in` | 완료된 production restart에서 1 ns를 추가하는 continuation input입니다. |

### 실행

[`../rmd/`](../rmd/README.md)에서 seed를 만든 뒤 실행합니다.

```bash
cd 1_Simulation/2_US/us
./build.sh
./run.sh --window 1
./run.sh
```

`build.sh`는 `../rmd/work/seeds/`에서 `work/NNN/`을 만듭니다. 모든 seed를 검증한 뒤에만
만들고, 기존 window directory가 있으면 종료합니다. 각 window의 계산 순서는 아래와 같습니다.

1. Distance restraint가 활성화된 minimization
2. Protein heavy-atom restraint와 distance restraint를 사용한 200 ps NVT heating
3. Distance restraint를 사용한 100 ps NPT equilibration
4. Distance restraint를 사용한 1 ns NPT production

`run.sh`는 `us/inputs/`의 stage input을 직접 읽으며 shared work에 복사하지 않습니다.
Production까지 완료된 window는 `Skipping completed window NNN`을 출력하고 다시 실행하지
않으므로, 실패 뒤 같은 command를 다시 실행하면 남은 window부터 이어갑니다. 서로 다른
window의 `run.sh`는 함께 실행할 수 있습니다. 실행 상태와 partial output 처리는
[GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

### Continuation

`inputs/continue.in`은 production restart에서 좌표와 velocity를 이어받는
1 ns continuation input입니다. `run.sh`는 이 input을 실행하지 않습니다.
완료된 window directory에서 직접 실행합니다.

```bash
cd work/001
pmemd.cuda -O -i ../../inputs/continue.in -o continue.out \
    -p system.parm7 -c production.rst7 -r continue.rst7 \
    -x continue.nc -inf continue.info
```

이 수동 실행은 writer lock과 input identity 기록을 사용하지 않습니다.
Distance는 `distance-cont.dat`에 기록되며 `2_Analysis/7_Enhanced_Sampling/7.1_Umbrella_Sampling`은
이 파일을 읽지 않습니다.

### 주요 output

Production distance는 각 window의 `distance.dat`에 1 ps(`DUMPFREQ` 500 steps) 간격으로
기록되어 window당 약 1,000 row입니다. `production.nc`는 10 ps(`ntwx=5000`)마다 기록해
100 frame입니다. 기본 production은 window당 1 ns입니다. PMF 계산은 equilibration 제거, time
correlation, neighboring histogram overlap, endpoint coverage와 반복 계산의
uncertainty를 포함합니다.

정상 종료하면 `build.sh`는 `Created 19 umbrella windows using the same topology: work`를,
전체 `run.sh`는 마지막 줄에 `Completed 19 umbrella-window run(s): work`를 출력합니다.
`--window N`으로 실행하면 숫자는 1입니다. 다음은
[US PMF analysis](../../../2_Analysis/7_Enhanced_Sampling/7.1_Umbrella_Sampling/README.md)입니다.

### 주요 option

`windows.tsv`에는 center(Å)와 AMBER NMR-style `rk2=rk3`(kcal mol⁻¹ Å⁻²)을
기록합니다. 다른 engine의 force constant를 옮길 때는 energy definition을 확인합니다.

| Option | 의미 |
| --- | --- |
| `iat=5,133` | Terminal Cα pair입니다. Topology가 바뀌면 atom index를 다시 계산합니다. |
| `r2=r3=CENTER` | Flat-bottom 폭이 없는 harmonic center이며 `build.sh`가 `windows.tsv` 값으로 치환합니다. |
| `rk2=rk3=FORCE` | 중심 양쪽의 force constant이며 기본값은 1.0 kcal mol⁻¹ Å⁻²입니다. 1 Å 간격에서 300 K window 폭은 약 0.55 Å로 인접 histogram이 겹칩니다. 이전 값 10은 폭 약 0.17 Å로 거의 겹치지 않았습니다. |
| `DISANG=restraint.RST` | 모든 minimization·heating·equilibration·production stage에서 window restraint를 읽습니다. |
| `&ewald netfrc=0` | Heavy-atom positional restraint(`ntr=1`)를 쓰는 `heat.in`에서 PME net-force 제거를 끕니다. AMBER manual이 `ntr=1`과 함께 권장합니다. |
| `--window N` | 하나의 window만 실행합니다. 생략하면 모든 window를 순서대로 처리합니다. |

### 자주 생기는 문제

공통 message는 [상위 README](../README.md#자주-생기는-문제)에 있습니다.

| Message | 조치 |
| --- | --- |
| `Seed metadata not found: ../rmd/work/seeds/seeds.tsv` | `../rmd/`에서 `run.sh`와 `anal.py`를 먼저 실행합니다. |
| `Window output already exists: work` | 이미 build했습니다. 그대로 `run.sh`를 실행하거나, 다시 만들려면 `work`를 옮깁니다. |
| `Run ./build.sh first.` | `build.sh`를 먼저 실행합니다. |
| `Partial <stage> output is retained for window NNN` | Message의 `mv` command로 해당 window의 남은 파일만 옮긴 뒤 같은 command를 다시 실행합니다. 완료된 window는 건너뜁니다. |

## English

Ordered ratchet-MD restart frames seed 19 umbrella windows from 6 to 24 Å. Every
window uses the same `system.parm7`.

The harmonic restraint enriches sampling near each center without forbidding
excursions. Center spacing and force constants must produce neighboring
histogram overlap before the PMF offsets can be connected, so adjust them
together.

### File roles

| File | Role |
| --- | --- |
| `windows.tsv` | Defines window centers (Å) and force constants in increasing order. |
| `build.sh` | Validates the shared topology and ratchet seeds and writes the window directories and `restraint.RST`. |
| `inputs/restraint.RST.template` | Atom indices and form of the AMBER NMR-style distance restraint. |
| `run.sh` | Runs the four stages of one selected window or all windows. |
| `inputs/continue.in` | Continuation input that adds 1 ns from a completed production restart. |

### Running

Run after creating seeds in [`../rmd/`](../rmd/README.md).

```bash
cd 1_Simulation/2_US/us
./build.sh
./run.sh --window 1
./run.sh
```

`build.sh` creates `work/NNN/` from `../rmd/work/seeds/` only after validating
every seed, and refuses to overwrite an existing build. Each window runs:

1. Minimization with the distance restraint active
2. 200 ps NVT heating with protein heavy-atom and distance restraints
3. 100 ps NPT equilibration with the distance restraint
4. 1 ns NPT production with the distance restraint

`run.sh` reads stage inputs directly from `us/inputs/` and does not copy them into
shared work. A window whose production completed prints
`Skipping completed window NNN` and is not rerun, so rerunning the same command
after a failure resumes with the remaining windows. `run.sh` for different
windows can run together. See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state and
partial-output handling.

### Continuation

`inputs/continue.in` inherits coordinates and velocities from a production
restart for 1 ns more. `run.sh` does not run it; start it manually in a completed
window directory:

```bash
cd work/001
pmemd.cuda -O -i ../../inputs/continue.in -o continue.out \
    -p system.parm7 -c production.rst7 -r continue.rst7 \
    -x continue.nc -inf continue.info
```

This manual run has no writer lock or input-identity record. It writes
distances to `distance-cont.dat`, which the
`2_Analysis/7_Enhanced_Sampling/7.1_Umbrella_Sampling` analysis does not read.

### Main outputs

Production distances are written to each window's `distance.dat` every 1 ps
(`DUMPFREQ` of 500 steps), giving about 1,000 rows per window. `production.nc` is
written every 10 ps (`ntwx=5000`), giving 100 frames. Production is 1 ns per
window by default. PMF analysis covers equilibration
removal, time correlation, neighboring overlap, endpoint coverage, and replicate
uncertainty.

On success, `build.sh` prints
`Created 19 umbrella windows using the same topology: work`, and a full `run.sh`
ends with `Completed 19 umbrella-window run(s): work`; with `--window N` the
count is 1. Continue with the
[US PMF analysis](../../../2_Analysis/7_Enhanced_Sampling/7.1_Umbrella_Sampling/README.md).

### Key options

`windows.tsv` stores the center in Å and AMBER NMR-style `rk2=rk3` in
kcal mol⁻¹ Å⁻². Check the energy definition before transferring force constants
from another engine.

| Option | Meaning |
| --- | --- |
| `iat=5,133` | Terminal Cα pair. Recompute the atom indices when the topology changes. |
| `r2=r3=CENTER` | Harmonic center without a flat bottom; `build.sh` substitutes the `windows.tsv` value. |
| `rk2=rk3=FORCE` | Force constant on both sides, default 1.0 kcal mol⁻¹ Å⁻². At 1 Å spacing, 300 K windows are about 0.55 Å wide and neighboring histograms overlap. The previous value of 10 gave about 0.17 Å windows with almost no overlap. |
| `DISANG=restraint.RST` | Reads the window restraint in every minimization, heating, equilibration, and production stage. |
| `&ewald netfrc=0` | Turns off PME net-force removal in `heat.in`, which uses heavy-atom positional restraints (`ntr=1`), as the AMBER manual recommends. |
| `--window N` | Runs a single window. Without it, all windows are processed in order. |

### Common problems

Shared messages are listed in the [parent README](../README.md#common-problems).

| Message | Action |
| --- | --- |
| `Seed metadata not found: ../rmd/work/seeds/seeds.tsv` | Run `run.sh` and `anal.py` in `../rmd/` first. |
| `Window output already exists: work` | The windows are already built. Run `run.sh`, or move `work` aside to rebuild. |
| `Run ./build.sh first.` | Run `build.sh` first. |
| `Partial <stage> output is retained for window NNN` | Move only that window's retained files with the `mv` command in the message and rerun the same command. Completed windows are skipped. |
