# Chignolin Gaussian accelerated MD / Chignolin GaMD

## 한국어

PDB 1UAO의 첫 NMR model을 ff19SB/OPC로 build하고 dual-boost GaMD를
실행합니다. 계산은 minimization, 200 ps heating, 100 ps NPT equilibration,
4 ns GaMD parameter preparation과 1 ns production 순서입니다.

Standard dual-boost GaMD는 total potential과 dihedral potential에 서로 다른
boost를 적용합니다. Dihedral barrier와 전체 potential fluctuation을 함께
완화하지만, 두 component의 합과 distribution을 production log에서 확인해야
reweighting 가능성을 판단할 수 있습니다.

### Script 역할

| 파일 | 역할 |
| --- | --- |
| `download.sh` | 1UAO PDB/mmCIF를 받고 checksum을 기록합니다. |
| `prepare.py` | 첫 NMR model의 138 atoms를 simulation PDB로 정리합니다. |
| `build.sh` | ff19SB/OPC topology와 solvated restart를 만듭니다. |
| `run.sh` | Conventional stage, 4 ns parameter preparation과 production을 실행합니다. |
| `anal.py` | 두 boost component와 total boost의 통계를 TSV로 저장합니다. |

~~~bash
cd 1_Simulation/4_GaMD/4.1_GaMD
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./build.sh structure/chignolin.pdb
./run.sh
python3 anal.py
~~~

`igamd=3`은 total potential과 dihedral potential에 boost를 적용합니다.
`work/gamd-restart.dat`에는 preparation에서 결정한 boost parameter가 저장되고,
production은 `irest_gamd=1`로 이 값을 이어받습니다. Minimization, heating,
equilibration과 parameter preparation의 핵심 output과 성공 완료 증거가 모두 있으면 그 stage를 건너뜁니다. 실패하거나 일부만 있으면 기존 결과를 보존하고 중단하며, production output이
있으면 덮어쓰지 않고 중단합니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `igamd=3` | Total-potential과 dihedral dual boost를 선택합니다. |
| `iE=1` | Lower-bound energy threshold 형식을 사용합니다. |
| `sigma0P=6.0`, `sigma0D=6.0` | Total/dihedral boost의 target standard deviation 상한(kcal/mol)입니다. |
| `ntcmdprep`, `ntcmd` | Initial potential estimate를 준비하는 conventional MD steps와 energy statistics를 수집하는 전체 initial conventional MD steps입니다. |
| `ntebprep`, `nteb` | Boost 도입 준비 steps와 boost를 적용한 GaMD equilibration steps입니다. 네 값을 독립 구간처럼 더하지 않습니다. |
| `ntave=50000` | Energy statistics update에 사용하는 averaging interval입니다. 2 fs 기준 100 ps입니다. |
| `irest_gamd=0/1` | Preparation에서 state를 만들고 production에서 `gamd-restart.dat`을 이어받습니다. |
| `ntwx=5000`, `-gamd` | Trajectory와 boost log를 10 ps 간격으로 맞춥니다. |
| `ntr=1`, `-ref minimize.rst7` | Heating 동안 non-solvent atom을 minimization 구조에 restraint합니다. |

기본 engine은 `pmemd.cuda`이며 `AMBER_ENGINE`으로 executable만 바꿀 수 있습니다.
Heating seed는 이 고정 example에서 `41001`입니다. System별 설정과 여러
production run은 `3_Templates/4_GaMD/4.1_GaMD`에서 구성합니다.
1 ns trajectory와 reweighted PMF는 folding equilibrium 또는 수렴 결과가
아닙니다.

Build는 기존 topology/restart file이 있으면 input을 변경하기 전에 중단하고 파일을 보존합니다. 새 build 전에는 기존 `work/`를 다른 위치에 보관하거나 별도 tutorial 사본을 사용합니다.

공개 analysis entry는 자동으로 `helpers/writer_guard.py`를 호출해 같은 output의 동시 writer를 거부합니다. Engine 실행부터 결과 게시까지 보호하며, signal 종료 시 child가 멈춘 뒤 lock을 해제합니다. Lock을 임의로 삭제해 실행을 재개하지 않습니다.

`download.sh`는 모든 asset과 `SHA256SUMS`를 staging에서 확인한 뒤 `helpers/publish_download.py`로 게시합니다. Transfer, checksum 또는 일반 publication 실패에서는 기존 파일을 보존하며, 관련 없는 preparation 파일도 유지합니다. `structure/.download.pending`가 남으면 prepare/build와 새 download가 거부됩니다. 보존된 staging과 marker를 점검하고, marker만 삭제해 이전 파일과 새 파일을 섞어 사용하지 않습니다.

## English

The first NMR model of PDB 1UAO is built with ff19SB/OPC. The workflow runs
minimization, 200 ps heating, 100 ps NPT equilibration, 4 ns of GaMD parameter
preparation, and one 1 ns dual-boost production run.

Standard dual-boost GaMD accelerates both total and dihedral potentials. The
two boost components and their sum must be inspected before reweighting.
`download.sh`/`prepare.py` select 1UAO, `build.sh` creates the ff19SB/OPC
system, `run.sh` performs preparation and production, and `anal.py`
writes component-wise diagnostics.

`igamd=3`, `iE=1` select lower-bound dual boost. `sigma0P`/`sigma0D` limit the
target boost standard deviations. `ntcmdprep` prepares the initial estimate and
`ntcmd` defines the initial conventional-statistics phase; `ntebprep` prepares
boost introduction and `nteb` defines GaMD equilibration. These are overlapping
schedule controls, not four durations to sum. `ntave=50000` gives a 100 ps
averaging interval. Production uses `irest_gamd=1`; `ntwx=5000` and
`-gamd` provide matched 10 ps records. Heating uses `ntr=1` and explicitly
passes `minimize.rst7` as the positional-restraint reference with `-ref`.

Production continues with `irest_gamd=1`. Completed preparation stages are
reused only with successful completion evidence and all required outputs; partial results are preserved and rejected. Existing production output is never overwritten. `AMBER_ENGINE` changes
only the executable, and the fixed heating seed is `41001`. Use
`3_Templates/4_GaMD/4.1_GaMD` for system-specific or repeated production runs.
The 1 ns example does not establish folding equilibrium or convergence.

## References / 참고 자료

- [RCSB PDB 1UAO](https://www.rcsb.org/structure/1UAO)
- [GaMD AMBER manual](https://www.med.unc.edu/pharm/miaolab/wp-content/uploads/sites/1385/2023/09/GaMD_Amber-manual.pdf)

Build stops before changing inputs when topology/restart files already exist, preserving those files. Preserve the existing `work/` elsewhere or use a separate tutorial copy before a new build.

### 동시 실행과 input 변경

Build와 run은 `work.writers/` registry를 공유합니다. 같은 output/state를 쓰는 작업은 동시에 실행하지 않습니다. `prepare.py`가 있는 경우 structure를 생성하는 작업도 input을 읽는 build와 충돌하면 거부합니다.

Run은 재사용할 결과의 input을 SHA256으로 비교합니다. Topology, 최초 coordinate file, stage input, predecessor restart와 restraint가 바뀌거나 기존 결과에 identity 기록이 없으면 파일을 보존하고 거부합니다. 이 tutorial은 고정 경로를 사용하므로 변경된 계산은 새 directory에 tutorial을 복사해 시작합니다.

정상 종료, command 실패와 INT/TERM에서는 자식 process의 종료를 확인한 뒤 자기 lock만 해제합니다. SIGKILL이나 node 장애로 남은 lock은 자동 삭제하지 않습니다. Error에 표시된 lock과 `owner.json`의 host, PID, command, scope를 확인하고 scheduler와 해당 host에서 모든 writer와 자식 process가 종료됐는지 확인한 뒤 그 lock directory만 수동 제거합니다. PID가 로컬에서 보이지 않는다는 이유만으로 제거하지 않습니다. `.gate/`도 같은 확인이 필요합니다.

지원하는 `--dry-run`과 `--help`는 보호나 identity 파일을 생성하지 않습니다. 진행 중인 work를 이동하거나 identity를 수정해 재사용하지 않습니다. 보호는 로컬 filesystem과 로컬 자식 process로 검증했으며 network filesystem, remote MPI와 다른 node의 writer 종료는 미검증입니다.

### Concurrent runs and input changes

Build and run share the `work.writers/` registry and reject concurrent writers to the same output/state. Where present, `prepare.py` also rejects structure writes that overlap an active build reader.

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

Production은 시작 증거도 보존합니다. Engine이 output 없이 mutable GaMD state만
바꾸고 실패해도 preparation state를 복사해 그 실패 상태를 덮어쓰지 않습니다.

Production also retains an attempt record. If the engine changes only mutable GaMD
state before failing, retry does not overwrite that state with the prepared state.

Public analysis entries automatically use `helpers/writer_guard.py` to reject concurrent writers to the same output. Protection covers engine execution through publication, and signal cleanup drains children before releasing the lock. Do not delete a lock to force a retry.

`download.sh` validates every asset and `SHA256SUMS` in staging before publishing through `helpers/publish_download.py`. Transfer, checksum and ordinary publication failures preserve existing files, including unrelated preparation files. A retained `structure/.download.pending` blocks source readers and new downloads. Inspect the retained staging and marker; deleting only the marker can expose a mixed generation.
