# KcsA AMBER simulation / KcsA AMBER 시뮬레이션

## 한국어

2단계의 `work/system.parm7`과 `work/system.rst7`을 input으로 사용합니다.

### 파일 역할

| 파일 | 역할 |
| --- | --- |
| `run.sh` | Input preflight와 두 minimization, heating, equilibration, production을 순서대로 실행합니다. |
| `inputs/min-environment.in` | Protein과 filter K+ heavy atom을 고정하고 lipid·water·bulk ion을 minimize합니다. |
| `inputs/min-all.in` | 전체 system restraint를 제거한 minimization입니다. |
| `inputs/heat.in` | 20→310 K heating을 진행하고 velocity를 생성합니다. |
| `inputs/equil.in` | 약한 protein/filter restraint를 둔 100 ps anisotropic NPT equilibration입니다. |
| `inputs/production.in` | Restraint 없는 1 ns anisotropic NPT production입니다. |

~~~bash
cd 1_Simulation/1_MD/1.3_Membrane_Protein/3_Simulation
./run.sh
~~~

Protein과 filter ion을 minimization, heating을 진행하고 나서
100 ps equilibration과 1 ns production을 실행합니다.
기본값은 310 K와 anisotropic pressure coupling입니다.
기본 engine은 `pmemd.cuda`입니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `ntp=2`, `barostat=2` | Monte Carlo barostat로 x·y·z box dimension을 anisotropic하게 조절합니다. |
| `temp0=310`, `ntt=3`, `gamma_ln=1.0` | 310 K Langevin thermostat 설정입니다. |
| `restraintmask=':1-415 & !@H='` | KcsA 408 residues와 filter K+ 7개 heavy atom을 초기 stage에서 restraint합니다. Topology residue 순서가 바뀌면 수정합니다. |
| `ntc=2`, `ntf=2`, `dt=0.002` | 수소 bond SHAKE와 2 fs timestep을 사용합니다. |
| `ntmin=2`, `dx0=0.0001` | 초기 protein side-chain contact를 완화하도록 두 minimization에서 작은 step의 steepest descent만 사용합니다. |

1 ns는 어디까지나 튜토리얼을 위한 시간일 뿐, 대부분의 경우 훨씬 긴 계산을 수행해야 합니다.

## English

The stage-2 topology and restart are used as inputs. Protein and filter ions are
restrained during minimization and heating, followed by 100 ps equilibration and
1 ns production at 310 K with anisotropic pressure coupling.

`run.sh` executes environment minimization, unrestrained minimization, heating,
equilibration, and production using the matching files under `inputs/`.
`ntp=2` with `barostat=2` enables anisotropic Monte Carlo pressure coupling;
`ntt=3` and `gamma_ln=1.0` define the Langevin thermostat. The initial
`:1-415 & !@H=` mask covers KcsA and seven filter ions and must be updated if
topology residue ordering changes. SHAKE permits the 2 fs timestep.
Both minimizations use steepest descent (`ntmin=2`) with `dx0=0.0001` to
relax initial side-chain contacts before dynamics.

The default engine is `pmemd.cuda`; `AMBER_ENGINE` overrides it. The 1 ns
production run is a tutorial-scale duration; most membrane studies require
substantially longer simulations.

### 동시 실행과 input 변경

Coordinate build, topology build와 simulation은 membrane tutorial root 옆의 `.writers/` registry를 공유합니다. 앞 단계의 work를 읽는 동안 그 directory를 다시 생성하는 작업은 거부합니다.

Run은 topology, 최초 coordinate file, stage input과 predecessor restart를 SHA256으로 확인합니다. 변경된 input이나 identity가 없는 기존 결과는 보존하고 거부합니다. 변경된 계산은 새 directory에 tutorial을 복사해 시작합니다.

정상 종료, command 실패와 INT/TERM에서는 자식 process의 종료를 확인한 뒤 자기 lock만 해제합니다. SIGKILL이나 node 장애로 남은 lock은 자동 삭제하지 않습니다. Error에 표시된 lock과 `owner.json`의 host, PID, command, scope를 확인하고 scheduler와 해당 host에서 모든 writer와 자식 process가 종료됐는지 확인한 뒤 그 lock directory만 수동 제거합니다. PID가 로컬에서 보이지 않는다는 이유만으로 제거하지 않습니다. `.gate/`도 같은 확인이 필요합니다.

지원하는 `--dry-run`과 `--help`는 보호나 identity 파일을 생성하지 않습니다. 진행 중인 work를 이동하거나 identity를 수정해 재사용하지 않습니다. 보호는 로컬 filesystem과 로컬 자식 process로 검증했으며 network filesystem, remote MPI와 다른 node의 writer 종료는 미검증입니다.

### Concurrent runs and input changes

Coordinate build, topology build and simulation share the `.writers/` registry beside the membrane tutorial root. A downstream reader prevents a builder from rewriting its input directory.

Run checks topology, initial coordinates, stage inputs and predecessor restarts with SHA256. Changed inputs and results without identities are preserved and rejected. Start changed calculations in a new tutorial copy.

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
