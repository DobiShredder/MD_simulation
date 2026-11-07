# Ratchet MD with PLUMED ABMD / PLUMED ABMD ratchet MD

## 한국어

PDB 1UAO 첫 NMR model의 residue 1–10 Cα distance를 PLUMED `ABMD` ratchet MD로
증가시키고, 그 trajectory에서 umbrella window seed를 추출합니다.

PLUMED `ABMD`는 목표값과 CV 차이로 정의한 ρ를 이용합니다. 목표 방향으로 ρ가 줄어드는
thermal fluctuation은 그대로 두고, 반대 방향 움직임에만 bias를 겁니다. 기본값은
`TO=3.0 nm`, `KAPPA=100`입니다. `KAPPA`는 일반 harmonic restraint와 definition이
다릅니다. `ratchet.end_to_end_min`도 distance가 아니라 PLUMED의 ρ minimum입니다.

### 파일 역할

| 파일 | 역할 |
| --- | --- |
| `run.sh` | 공통 topology를 읽고 minimization, heating, equilibration과 ABMD production을 실행합니다. |
| `inputs/plumed.dat` | Molecule reconstruction, terminal distance와 ABMD bias를 정의합니다. |
| `inputs/ratchet.in` | PLUMED를 활성화한 1 ns NPT AMBER production input입니다. |
| `anal.py` | Cpptraj distance에서 ordered first-crossing frame을 찾고 restart seed를 저장합니다. |

### 실행

상위 directory의 preparation을 먼저 실행합니다.

```bash
cd 1_Simulation/2_US
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./prepare.sh structure/chignolin.pdb
cd rmd
./run.sh
python3 anal.py
```

`run.sh`는 minimization, 200 ps NVT heating, 100 ps NPT equilibration과
1 ns ratchet MD를 실행합니다. 기본 engine은 PLUMED가 연결된 `pmemd.cuda`이며
`AMBER_ENGINE`으로 바꿉니다. `run.sh`는 `inputs/plumed.dat`을 `work/`에 복사한 뒤
AMBER에 넘깁니다. NPT 종료 density가 0.90–1.10 g/cm³ 범위를 벗어나면 ratchet MD를
시작하지 않습니다.

`--dry-run`은 shared input이 있으면 local `work/`가 없어도 실행할 command와 working
directory를 표시합니다. Engine을 실행하거나 파일을 만들지 않습니다.

Ratchet MD가 완료된 `work`에서 다시 실행하면 engine을 실행하지 않고
`Skipping completed ratchet MD`와 다음 command `python3 anal.py`를 출력한 뒤
정상 종료합니다. 실행 상태와 재실행은 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

### 주요 output

| 파일 | 내용 |
| --- | --- |
| `work/ratchet.nc`, `work/ratchet.rst7` | Ratchet MD trajectory와 restart |
| `work/ratchet.dat` | PLUMED distance, bias와 ρ minimum |
| `work/seeds/seed_NNN.rst7` | `anal.py`가 고른 window별 seed |
| `work/seeds/seeds.tsv` | Seed 선택 정보 |

`anal.py`는 cpptraj으로 `:1@CA`–`:10@CA` distance를 계산하고 각 window center의
first-crossing frame을 선택합니다. 허용 오차 0.75 Å 안의 frame이 없으면 종료합니다.

`ratchet.nc`는 1 ps(`ntwx=500`)마다 기록해 1,000 frame이고, `ratchet.dat`도
1 ps(`STRIDE=500`)마다 기록합니다. 정상 종료하면 `run.sh`와 `anal.py`의 마지막
줄이 각각 다음과 같습니다.

```text
Ratchet MD trajectory: work/ratchet.nc
Created 19 US seed restarts: work/seeds
```

다음은 [`../us/`](../us/README.md)의 `build.sh`입니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `WHOLEMOLECULES ENTITY0=1-138` | Protein atom 1–138을 PBC에 걸쳐 다시 잇습니다. |
| `DISTANCE ATOMS=5,133 NOPBC` | 현재 topology의 terminal Cα atom index입니다. `WHOLEMOLECULES` 뒤에 계산합니다. Topology가 바뀌면 index도 바꿉니다. |
| `ABMD TO=3.0` | End-to-end distance target이며 PLUMED 기본 length unit인 nm를 사용합니다. |
| `KAPPA=100` | Target 반대 방향의 ρ 증가를 억제하는 ratchet strength입니다. Harmonic distance force constant와 직접 비교하지 않습니다. |
| `plumed=1`, `plumedfile='plumed.dat'` | AMBER에서 PLUMED bias를 활성화합니다. |
| `&ewald netfrc=0` | Positional restraint(`ntr=1`)를 쓰는 `min-solvent.in`, `heat.in`, `equil.in`에서 PME net-force 제거를 끕니다. AMBER manual이 `ntr=1`과 함께 권장합니다. |
| `max_error_angstrom=0.75` | `anal.py`가 target center와 seed frame 사이에 허용하는 고정 distance 차이(Å)입니다. |

### 주의

NPT 중 box-change error, temperature·energy 급등, NaN 또는 SHAKE failure가
발생하면 equilibration을 나누지 않습니다. 상위 `inputs/tleap.in`의 periodic
box, `min-all.out`과 `heat.out`을 먼저 확인합니다.

ABMD trajectory는 seed 생성에만 사용합니다. Equilibrium PMF와 kinetics는
이 trajectory에서 계산하지 않습니다.

### 자주 생기는 문제

공통 message는 [상위 README](../README.md#자주-생기는-문제)에 있습니다.

| Message | 조치 |
| --- | --- |
| `NPT density is outside 0.90-1.10 g/cm^3` | `work/equil.out`의 `Density` 추세와 상위 `inputs/tleap.in`의 box를 확인합니다. |
| `1 ns ratchet MD failed.` | `work/ratchet.out`과 `work/engine.ratchet.log`를 봅니다. PLUMED가 연결되지 않은 engine이면 이 stage에서 실패합니다. |
| `No frame is within the 0.750 Å tolerance of center ...` | Ratchet MD가 해당 distance에 도달하지 못했습니다. `work/ratchet.dat`의 distance 범위를 확인합니다. |
| `Output directory already exists: work/seeds` | 기존 seed를 쓰려면 그대로 `../us/`로 진행하고, 다시 만들려면 `work/seeds`를 옮깁니다. |

## English

Ratchet MD with PLUMED ABMD increases the residue 1–10 Cα distance of the first
1UAO NMR model, and umbrella-window seeds are extracted from that trajectory.

ABMD acts on ρ, the squared difference between the CV and its target. Thermal
fluctuations that reduce ρ are kept, and only backward progress is biased. The
training defaults are `TO=3.0 nm` and `KAPPA=100`. Because ABMD acts on ρ, its
KAPPA does not have the same dimensional convention as an ordinary AMBER
harmonic-distance restraint. The reported `ratchet.end_to_end_min` component is
the PLUMED ρ minimum, not a minimum distance.

### File roles

| File | Role |
| --- | --- |
| `run.sh` | Reads the shared topology and runs minimization, heating, equilibration, and ABMD production. |
| `inputs/plumed.dat` | Defines molecule reconstruction, the terminal distance, and the ABMD bias. |
| `inputs/ratchet.in` | PLUMED-enabled 1 ns NPT AMBER production input. |
| `anal.py` | Finds ordered first-crossing frames from cpptraj distances and writes restart seeds. |

### Running

Run the parent-directory preparation first.

```bash
cd 1_Simulation/2_US
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./prepare.sh structure/chignolin.pdb
cd rmd
./run.sh
python3 anal.py
```

`run.sh` performs minimization, 200 ps NVT heating, 100 ps NPT equilibration,
and 1 ns ratchet MD with a PLUMED-enabled `pmemd.cuda`; `AMBER_ENGINE` selects
another executable. The PLUMED input is copied into `work/` before AMBER reads it.
Ratchet MD does not start when the final NPT density is outside
0.90–1.10 g/cm³.

With shared inputs available, `--dry-run` prints the commands and intended working
directory even when local `work/` does not exist. It neither runs the engine nor
creates files.

Rerunning after a completed ratchet MD skips the engine, prints
`Skipping completed ratchet MD` and the next command, `python3 anal.py`, and
exits 0. See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state and reruns.

### Main outputs

| File | Content |
| --- | --- |
| `work/ratchet.nc`, `work/ratchet.rst7` | Ratchet-MD trajectory and restart |
| `work/ratchet.dat` | PLUMED distance, bias, and ρ minimum |
| `work/seeds/seed_NNN.rst7` | Seed for each window, selected by `anal.py` |
| `work/seeds/seeds.tsv` | Seed selection record |

`anal.py` computes the `:1@CA`–`:10@CA` distance with cpptraj and selects the
first-crossing frame for each window center. It exits when no frame lies within
the 0.75 Å tolerance.

`ratchet.nc` is written every 1 ps (`ntwx=500`), giving 1,000 frames, and
`ratchet.dat` is also written every 1 ps (`STRIDE=500`). On success, `run.sh`
and `anal.py` end with these lines, respectively:

```text
Ratchet MD trajectory: work/ratchet.nc
Created 19 US seed restarts: work/seeds
```

Continue with `build.sh` in [`../us/`](../us/README.md).

### Key options

| Option | Meaning |
| --- | --- |
| `WHOLEMOLECULES ENTITY0=1-138` | Reconnects protein atoms 1–138 across PBC. |
| `DISTANCE ATOMS=5,133 NOPBC` | Terminal Cα atom indices for the current topology, evaluated after `WHOLEMOLECULES`. Update them when the topology changes. |
| `ABMD TO=3.0` | End-to-end distance target in nm, the PLUMED default length unit. |
| `KAPPA=100` | Ratchet strength that damps ρ increases away from the target. Not directly comparable with a harmonic distance force constant. |
| `plumed=1`, `plumedfile='plumed.dat'` | Activates the PLUMED bias in AMBER. |
| `&ewald netfrc=0` | Turns off PME net-force removal in `min-solvent.in`, `heat.in`, and `equil.in`, which use positional restraints (`ntr=1`), as the AMBER manual recommends. |
| `max_error_angstrom=0.75` | Fixed distance tolerance (Å) between a target center and its seed frame in `anal.py`. |

### Cautions

NPT box-change errors, temperature or energy spikes, NaNs, or SHAKE failure are
handled by checking the periodic box in the parent `inputs/tleap.in`,
`min-all.out`, and `heat.out` rather than splitting equilibration into short jobs.

The biased pathway is used for seed generation, not for an equilibrium PMF or
kinetics.

### Common problems

Shared messages are listed in the [parent README](../README.md#common-problems).

| Message | Action |
| --- | --- |
| `NPT density is outside 0.90-1.10 g/cm^3` | Check the `Density` trend in `work/equil.out` and the box in the parent `inputs/tleap.in`. |
| `1 ns ratchet MD failed.` | Read `work/ratchet.out` and `work/engine.ratchet.log`. An engine without PLUMED fails at this stage. |
| `No frame is within the 0.750 Å tolerance of center ...` | Ratchet MD did not reach that distance. Check the distance range in `work/ratchet.dat`. |
| `Output directory already exists: work/seeds` | To use the existing seeds, continue to `../us/`; to regenerate them, move `work/seeds` aside. |
