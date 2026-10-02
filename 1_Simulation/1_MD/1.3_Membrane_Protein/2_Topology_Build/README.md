# Stage 2: topology build / 2단계: topology build

## 한국어

1단계 coordinate에 ff19SB, Lipid21과 OPC를 적용해 `system.parm7`과 `system.rst7`을 만듭니다.
Lipid21의 modular residue `PA`·`PC`·`PE`·`OL`과 `CHL`은 `leaprc.lipid21`이 읽습니다.

### 파일 역할

| 파일 | 역할 |
| --- | --- |
| `run.sh` | Coordinate를 `work/`로 복사하고 tleap을 실행합니다. |
| `prepare_tleap.py` | `CRYST1` box와 WAT 수를 읽어 tleap input을 만듭니다. `run.sh`가 자동으로 호출합니다. |
| `tleap.in` | Force field, box placeholder, neutralization과 KCl 추가를 정의한 template입니다. |

~~~bash
cd 1_Simulation/1_MD/1.3_Membrane_Protein/2_Topology_Build
./run.sh ../1_Coordinate_Build/work/system-coordinates.pdb
~~~

### 주요 option

`prepare_tleap.py`는 PDB의 `CRYST1`을 그대로 사용합니다.
그러지 않으면 평형화된 patch의 x·y 주기가 변할 수 있습니다.

0.15 M KCl pair 수는 total box volume이 아니라 water 분자 수로 계산합니다.

~~~text
KCl pairs = round(number of WAT × 0.15 / 55.5)
~~~

기본 KcsA coordinate에는 pore water를 포함해 약 28,000개의 WAT가 있으며, 76 KCl pairs가 생성됩니다.
Coordinate 크기나 water 수가 달라지면 값도 자동으로 바뀌니다.
`addionsrand`는 tleap 실행마다 다른 water를 선택할 수 있으므로
ion 초기 위치와 `system.rst7` checksum은 고정되지 않습니다.

주요 output은 `work/system.parm7`, `work/system.rst7`, `work/system.pdb`와 `work/leap.log`입니다.
`leap.log`에서 unknown residue, missing heavy atom, parameter error와 `Errors = 0`을 확인합니다.
Chain C-terminus의 `OXT`를 tleap이 추가하는 message는 예상된 결과입니다.
Initial energy에서 `VDWAALS = *************`가 보이면
simulation을 진행하지 않고 1단계 coordinate를 다시 확인합니다.

## English

This stage applies ff19SB, Lipid21, and OPC to the stage-1 coordinates.
`prepare_tleap.py` transfers the PDB `CRYST1` dimensions to a generated tleap
input and calculates 0.15 M KCl pairs from the number of water molecules. The
default KcsA system contains about 28,000 waters and receives 76 KCl pairs.
Because `addionsrand` selects solvent molecules anew for each tleap invocation,
the initial ion positions and restart checksum are not fixed.

Outputs are `work/system.parm7`, `work/system.rst7`, `work/system.pdb`, and
`work/leap.log`. Check for unknown residues, missing heavy atoms, parameter
errors, and `Errors = 0`. Do not proceed if the initial energy reports an
overflow such as `VDWAALS = *************`.

### 동시 실행과 input 변경

Coordinate build, topology build와 simulation은 membrane tutorial root 옆의 `.writers/` registry를 공유합니다. 앞 단계의 work를 읽는 동안 그 directory를 다시 생성하는 작업은 거부합니다.

Build는 기존 생성 output을 재작성하지 않습니다. 새 structure나 설정으로 계산하려면 새 directory에 tutorial을 복사해 시작합니다. Simulation 단계의 run이 topology, initial coordinate file과 stage input을 SHA256으로 확인합니다.

정상 종료, command 실패와 INT/TERM에서는 자식 process의 종료를 확인한 뒤 자기 lock만 해제합니다. SIGKILL이나 node 장애로 남은 lock은 자동 삭제하지 않습니다. Error에 표시된 lock과 `owner.json`의 host, PID, command, scope를 확인하고 scheduler와 해당 host에서 모든 writer와 자식 process가 종료됐는지 확인한 뒤 그 lock directory만 수동 제거합니다. PID가 로컬에서 보이지 않는다는 이유만으로 제거하지 않습니다. `.gate/`도 같은 확인이 필요합니다.

지원하는 `--dry-run`과 `--help`는 보호나 identity 파일을 생성하지 않습니다. 진행 중인 work를 이동하거나 identity를 수정해 재사용하지 않습니다. 보호는 로컬 filesystem과 로컬 자식 process로 검증했으며 network filesystem, remote MPI와 다른 node의 writer 종료는 미검증입니다.

### Concurrent runs and input changes

Coordinate build, topology build and simulation share the `.writers/` registry beside the membrane tutorial root. A downstream reader prevents a builder from rewriting its input directory.

Build preserves existing generated outputs. Start a new tutorial copy for changed structures or settings. The simulation runner checks topology, initial coordinates and stage inputs with SHA256.

Normal exit, command failure and INT/TERM release only the owned lock after child termination is verified. Locks left by SIGKILL or node failure are retained. Inspect the reported lock and its `owner.json` host, PID, command and scopes; confirm through the scheduler and owning host that all writers and children stopped before manually removing only that lock directory. A PID missing locally is not sufficient. Apply the same checks to `.gate/`.

Supported `--dry-run` and `--help` do not create writer or identity files. Do not move active work trees or edit identities to reuse results. Protection was tested on a local filesystem with local child processes; network filesystems, remote MPI and termination of writers on other nodes remain unverified.
