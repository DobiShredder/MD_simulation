# AMBER umbrella windows / AMBER umbrella window

## 한국어

Ratchet MD restart를 6–24 Å umbrella window의 seed로 사용합니다. 모든
window는 같은 `system.parm7`을 사용합니다. `windows.tsv`에는 center(Å)와
AMBER NMR-style `rk2=rk3`(kcal mol⁻¹ Å⁻²)을 기록합니다. 다른 engine의 force
constant를 옮길 때는 energy definition을 확인합니다.

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

```bash
cd 1_Simulation/2_US/us
./build.sh
./run.sh --window 1
./run.sh
```

`build.sh`는 `../rmd/work/seeds/`에서 `work/NNN/`을 만듭니다. 기존
window directory가 있으면 종료합니다. 각 window의 계산 순서는 아래와
같습니다.

1. Distance restraint가 활성화된 minimization
2. Protein heavy-atom restraint와 distance restraint를 사용한 200 ps NVT heating
3. Distance restraint를 사용한 100 ps NPT equilibration
4. Distance restraint를 사용한 1 ns NPT production

Minimization, heating 또는 equilibration의 `*.out`과 `*.rst7`이 모두 있고 성공 완료 증거가 있으면
해당 stage를 건너뜁니다. 완료 증거가 없거나 필수 output이 누락되면 기존 결과를 보존하고 중단합니다.
기존 `production.out`이 있는 window는 덮어쓰지 않고 시작 전에 중단합니다.
`inputs/continue.in`은 production restart에서 좌표와 velocity를 이어받는
1 ns continuation input입니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `iat=2,132` | Terminal Cα pair입니다. Topology가 바뀌면 atom index를 다시 계산합니다. |
| `r2=r3=CENTER` | Flat-bottom 폭이 없는 harmonic center이며 `build.sh`가 `windows.tsv` 값으로 치환합니다. |
| `rk2=rk3=FORCE` | 중심 양쪽의 force constant이며 기본값은 10 kcal mol⁻¹ Å⁻²입니다. |
| `DISANG=restraint.RST` | 모든 minimization·heating·equilibration·production stage에서 window restraint를 읽습니다. |
| `--window N` | 하나의 window만 실행합니다. 생략하면 모든 window를 순서대로 처리합니다. |

Production distance는 `distance.dat`에 1 ps 간격으로 기록됩니다. PMF 계산은
equilibration 제거, time correlation, neighboring histogram overlap과 반복
계산을 포함합니다. 기본 production은 window당 1 ns입니다.

## English

Ordered ratchet-MD restart frames seed windows from 6 to 24 Å. Every window
uses the same topology. `windows.tsv` stores the center in Å and AMBER
NMR-style `rk2=rk3` in kcal mol⁻¹ Å⁻². Check the energy definition before
transferring force constants from another engine.

The harmonic restraint enriches sampling near each center without forbidding
excursions. Center spacing and force constants must produce neighboring
histogram overlap before the PMF offsets can be connected.

`windows.tsv` defines centers and strengths. `build.sh` combines the shared
topology, ordered seeds, and `restraint.RST.template`; `run.sh` executes the
four restrained stages. `iat=2,132` selects the terminal Cα pair,
`r2=r3` sets the center, `rk2=rk3` sets its strength, and `DISANG` keeps the
restraint active. `--window N` limits execution to one window.

`build.sh` creates `work/NNN/` only after validating every seed and
refuses to overwrite an existing build. Each window runs restrained
minimization, 200 ps NVT heating, 100 ps NPT equilibration, and 1 ns NPT
production. A preparation stage is skipped only with successful completion evidence and all required outputs; partial results are preserved and rejected. A window with an existing `production.out`
is rejected before any production output is overwritten.

`inputs/continue.in` inherits coordinates and velocities from a production
restart. Production distances are written to `distance.dat` every 1 ps. PMF
analysis covers equilibration removal, time correlation, neighboring overlap,
endpoint coverage, and replicate uncertainty. Production is 1 ns per window.

`run.sh`는 `us/inputs/`의 stage input을 직접 읽습니다. Shared work에 input을 복사하지 않아 서로 다른 window의 run이 shared input을 다시 쓰지 않습니다.

### 동시 실행과 input 변경

Preparation, rMD, seed analysis, window build와 window run은 상위 `work.writers/` registry를 공유합니다. 같은 window나 seed output을 쓰는 작업은 거부하고, 서로 다른 window의 run은 함께 실행할 수 있습니다.

Run은 재사용할 결과의 input을 SHA256으로 비교합니다. Topology, 최초 coordinate file, stage input, predecessor restart와 restraint가 바뀌거나 기존 결과에 identity 기록이 없으면 파일을 보존하고 거부합니다. 이 tutorial은 고정 경로를 사용하므로 변경된 계산은 새 directory에 tutorial을 복사해 시작합니다.

정상 종료, command 실패와 INT/TERM에서는 자식 process의 종료를 확인한 뒤 자기 lock만 해제합니다. SIGKILL이나 node 장애로 남은 lock은 자동 삭제하지 않습니다. Error에 표시된 lock과 `owner.json`의 host, PID, command, scope를 확인하고 scheduler와 해당 host에서 모든 writer와 자식 process가 종료됐는지 확인한 뒤 그 lock directory만 수동 제거합니다. PID가 로컬에서 보이지 않는다는 이유만으로 제거하지 않습니다. `.gate/`도 같은 확인이 필요합니다.

지원하는 `--dry-run`과 `--help`는 보호나 identity 파일을 생성하지 않습니다. 진행 중인 work를 이동하거나 identity를 수정해 재사용하지 않습니다. 보호는 로컬 filesystem과 로컬 자식 process로 검증했으며 network filesystem, remote MPI와 다른 node의 writer 종료는 미검증입니다.

`run.sh` reads stage inputs directly from `us/inputs/`. It does not copy inputs into shared work, so independent windows do not rewrite shared input files.

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
