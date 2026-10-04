# Ratchet MD with PLUMED ABMD / PLUMED ABMD ratchet MD

## 한국어

PDB 1UAO의 첫 NMR model에서 residue 1–10 Cα distance를 증가시킵니다.
기본 index는 terminal Cα atom 2·132와 protein atom 1–138입니다. PLUMED는
`WHOLEMOLECULES` 적용 후 `NOPBC` distance를 계산합니다. Topology가 바뀌면
index도 바꿉니다.

PLUMED `ABMD`는 목표값과 CV 차이로 정의한 ρ를 이용합니다. 기본값은
`TO=3.0 nm`, `KAPPA=100`입니다. `KAPPA`는 일반 harmonic restraint와
definition이 다릅니다. `ratchet.end_to_end_min`도 distance가 아니라 PLUMED의
ρ minimum입니다.

### 파일 역할

| 파일 | 역할 |
| --- | --- |
| `run.sh` | 공통 topology를 읽고 minimization, heating, equilibration과 ABMD production을 실행합니다. |
| `inputs/plumed.dat` | Molecule reconstruction, terminal distance와 ABMD bias를 정의합니다. |
| `inputs/ratchet.in` | PLUMED를 활성화한 1 ns NPT AMBER production input입니다. |
| `anal.py` | Cpptraj distance에서 ordered first-crossing frame을 찾고 restart seed를 저장합니다. |

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
1 ns ratchet MD를 실행합니다. 기본 engine은 PLUMED가 연결된
`pmemd.cuda`입니다. NPT 종료 density가 0.90–1.10 g/cm³ 범위를 벗어나면
ratchet MD를 시작하지 않습니다. Output은 `work/ratchet.nc`,
`work/ratchet.rst7`과 `work/ratchet.dat`입니다. `run.sh`는
`inputs/plumed.dat`을 `work/`에 복사한 뒤 AMBER에 넘깁니다.

NPT 중 box-change error, temperature·energy 급등, NaN 또는 SHAKE failure가
발생하면 equilibration을 나누지 않습니다. 상위 `tleap.in`의 periodic
box, `min-all.out`과 `heat.out`을 먼저 확인합니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `DISTANCE ATOMS=2,132 NOPBC` | 현재 topology의 terminal Cα atom index입니다. `WHOLEMOLECULES` 뒤에 계산합니다. |
| `ABMD TO=3.0` | End-to-end distance target이며 PLUMED 기본 length unit인 nm를 사용합니다. |
| `KAPPA=100` | Target 반대 방향의 ρ 증가를 억제하는 ratchet strength입니다. Harmonic distance force constant와 직접 비교하지 않습니다. |
| `plumed=1`, `plumedfile='plumed.dat'` | AMBER에서 PLUMED bias를 활성화합니다. |
| `max_error_angstrom=0.75` | `anal.py`가 target center와 seed frame 사이에 허용하는 고정 distance 차이(Å)입니다. |

`anal.py`는 cpptraj으로 `:1@CA`–`:10@CA` distance를 계산하고 각 window
center의 first-crossing frame을 선택합니다. 허용 오차는 0.75 Å입니다. Seed는
`work/seeds/seed_NNN.rst7`, 선택 정보는 `seeds.tsv`에 저장됩니다. 오차 범위
안의 frame이 없으면 종료합니다.

ABMD trajectory는 seed 생성에만 사용합니다. Equilibrium PMF와 kinetics는
이 trajectory에서 계산하지 않습니다.

`--dry-run`은 shared input이 있으면 local `work/`가 없어도 실행할 command와 working directory를 표시합니다. Engine을 실행하거나 파일을 만들지 않습니다.

## English

Ratchet MD increases the terminal Cα distance of the first 1UAO model. The
default indices are Cα atoms 2 and 132 and protein atoms 1–138.
`WHOLEMOLECULES` is applied before the `NOPBC` distance. Update these indices
when the topology changes.

PLUMED ABMD restrains backward progress in ρ, the squared difference between
the CV and its target. The training defaults are `TO=3.0 nm` and `KAPPA=100`.
Because ABMD acts on ρ, its KAPPA does not have the same dimensional convention
as an ordinary AMBER harmonic-distance restraint. The reported `_min`
component is the PLUMED ρ minimum, not a minimum distance.

`run.sh` handles the AMBER stages and activates `inputs/plumed.dat` through
`plumed=1`. The PLUMED file reconstructs the protein, evaluates
`DISTANCE ATOMS=2,132 NOPBC`, and applies `ABMD TO=3.0 KAPPA=100` in PLUMED
units. `anal.py` uses a fixed 0.75 Å tolerance when selecting first-crossing
seeds. `AMBER_ENGINE` selects the PLUMED-enabled executable when the default
`pmemd.cuda` command is not used.

`run.sh` performs minimization, 200 ps NVT heating, 100 ps NPT equilibration,
and 1 ns ratchet MD with a PLUMED-enabled `pmemd.cuda`. It stops before ratchet
MD when the final NPT density is outside 0.90–1.10 g/cm³. NPT box-change errors
are handled by checking the initial periodic box, minimization, and heating
rather than splitting an unsuitable equilibration into short jobs.

The PLUMED input is copied into `work/`. `anal.py` selects ordered
first-crossing frames within 0.75 Å and writes AMBER restart seeds. It exits
when a requested window was not sampled. The biased pathway is used for seed
generation, not for an equilibrium PMF or kinetics.

With shared inputs available, `--dry-run` prints the commands and intended working directory even when local `work/` does not exist. It neither runs the engine nor creates files.

### 동시 실행과 input 변경

Preparation, rMD, seed analysis, window build와 window run은 상위 `work.writers/` registry를 공유합니다. 같은 window나 seed output을 쓰는 작업은 거부하고, 서로 다른 window의 run은 함께 실행할 수 있습니다.

Run은 재사용할 결과의 input을 SHA256으로 비교합니다. Topology, 최초 coordinate file, stage input, predecessor restart와 restraint가 바뀌거나 기존 결과에 identity 기록이 없으면 파일을 보존하고 거부합니다. 이 tutorial은 고정 경로를 사용하므로 변경된 계산은 새 directory에 tutorial을 복사해 시작합니다.

정상 종료, command 실패와 INT/TERM에서는 자식 process의 종료를 확인한 뒤 자기 lock만 해제합니다. SIGKILL이나 node 장애로 남은 lock은 자동 삭제하지 않습니다. Error에 표시된 lock과 `owner.json`의 host, PID, command, scope를 확인하고 scheduler와 해당 host에서 모든 writer와 자식 process가 종료됐는지 확인한 뒤 그 lock directory만 수동 제거합니다. PID가 로컬에서 보이지 않는다는 이유만으로 제거하지 않습니다. `.gate/`도 같은 확인이 필요합니다.

지원하는 `--dry-run`과 `--help`는 보호나 identity 파일을 생성하지 않습니다. 진행 중인 work를 이동하거나 identity를 수정해 재사용하지 않습니다. 보호는 로컬 filesystem과 로컬 자식 process로 검증했으며 network filesystem, remote MPI와 다른 node의 writer 종료는 미검증입니다.

### Concurrent runs and input changes

Preparation, rMD, seed analysis, window build and window runs share the parent `work.writers/` registry. Writers to the same window or seed output are rejected; independent windows may run concurrently.

Run compares inputs for result reuse with SHA256. Changed topology, initial coordinates, stage input, predecessor restart or restraint, and results without identity records, are preserved and rejected. This tutorial uses fixed paths; start changed calculations in a new tutorial copy.

Normal exit, command failure and INT/TERM release only the owned lock after child termination is verified. Locks left by SIGKILL or node failure are retained. Inspect the reported lock and its `owner.json` host, PID, command and scopes; confirm through the scheduler and owning host that all writers and children stopped before manually removing only that lock directory. A PID missing locally is not sufficient. Apply the same checks to `.gate/`.

Supported `--dry-run` and `--help` do not create writer or identity files. Do not move active work trees or edit identities to reuse results. Protection was tested on a local filesystem with local child processes; network filesystems, remote MPI and termination of writers on other nodes remain unverified.

### Stage 완료 판정 / Stage completion

Input identity는 입력이 같은지 확인하며 engine의 성공 종료를 증명하지 않습니다.
Runner가 engine의 성공 종료와 필수 output을 확인한 뒤 만든 완료 증거가 있어야
stage를 재사용합니다. Output이 남았지만 완료 증거가 없거나 필수 output이
누락·비어 있으면 기존 결과를 보존하고 중단합니다. 기존 결과를 소급 인증하지
않습니다. 새 계산은 생성된 `work/`를 포함하지 않는 새 tutorial copy에서 시작합니다.
`ntwx=0`인 AMBER stage는 trajectory를 완료 조건으로 요구하지 않습니다.
지원되는 continuation은 기존 restart/state 전달 방식을 따릅니다.

Input identity checks unchanged inputs; it does not prove a successful engine exit.
A stage is reused only with completion evidence written after a successful engine
exit and required-output checks. Outputs without that evidence, or missing/empty
required outputs, are preserved and rejected. Existing results are not certified
retroactively. Start a new tutorial copy without generated `work/` directories for
a new calculation. AMBER stages with `ntwx=0` do not require a trajectory for
completion. Supported continuation retains its existing restart/state handoff.
