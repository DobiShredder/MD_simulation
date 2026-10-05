# Chignolin WESTPA–AMBER weighted ensemble

Reference syntax: Amber 2026 and WESTPA 2.

## 한국어

PDB 1UAO Chignolin을 explicit OPC water에서 전파하고 residue 2–9의 Cα RMSD를
progress coordinate로 사용합니다. Conventional MD와 같은 unbiased AMBER
dynamics를 실행하지만, WESTPA가 1 ps마다 walker를 RMSD bin에 배치하고
split/merge하여 bin당 walker 수를 조정합니다. Split된 walker의 weight 합과
parent restart는 보존되며 각 child는 서로 다른 Langevin seed로 이어집니다.

RMSD 3.0 Å 이상은 resampling과 target 분석을 연습하기 위한 partially unfolded
state입니다. 20 iterations의 짧은 기본 run에서는 target event가 없을 수 있으며,
event 수나 target weight를 folding/unfolding rate로 해석하지 않습니다.

### Script 역할

| 파일 | 실행 방식 | 주요 input과 output |
| --- | --- | --- |
| `download.sh` | 직접 실행 | PDB 1UAO → `structure/1UAO.raw.pdb`, checksum |
| `prepare.py` | 직접 실행 | NMR model 1 → `structure/chignolin.pdb` |
| `build.sh` | 직접 실행 | Chignolin PDB → ff19SB/OPC topology, RMSD reference와 basis restart |
| `env.sh` | 자동 호출 | WESTPA root, work directory, AMBER/cpptraj executable 설정 |
| `init.sh` | 직접 실행 | Basis/target state → `work/west.h5` |
| `run.sh` | 직접 실행 | WESTPA iterations → segment restart, log와 갱신된 `west.h5` |
| `westpa_scripts/runseg.sh` | WESTPA가 호출 | Parent restart → 1 ps AMBER segment와 두 pcoord 값 |
| `anal.py` | 직접 실행 | Weight, effective walker, RMSD 범위, bin occupancy와 target 진단 TSV |

```bash
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./build.sh structure/chignolin.pdb
./init.sh
./run.sh
python3 anal.py
```

### 주요 option

`build.sh`는 ff19SB/OPC 12 Å box를 만들고 minimization, 100 ps heating과
100 ps NPT equilibration을 거쳐 `work/bstates/basis.rst7`을 생성합니다.
각 preparation stage의 `*.out`과 restart가 모두 있으면 건너뛰고, 둘 중 완료 증거가 없거나 필수 output이 누락되면 기존 결과를 보존하고 중단합니다. `west.h5`나 segment output이 있으면
기존 WESTPA state를 보호하기 위해 build를 중단합니다.
Minimized structure인 `work/common_files/reference.rst7`에 residue 2–9 Cα를
least-squares fit한 RMSD를 Å 단위로 계산합니다. Terminal residue를 제외하면
말단 움직임이 progress coordinate를 지배하는 현상을 줄일 수 있습니다.

`west.cfg`는 bin당 walker 4개와 20 iterations를 사용합니다. RMSD bin은
0–3 Å 구간에서 조밀하게 나뉘고 `[3.0, inf)`가 target bin입니다.
`tstate.file`의 3.25 Å는 이 bin 안의 representative value입니다. Cα RMSD는
서로 다른 unfolded conformation을 같은 값으로 투영할 수 있으므로, 연구용
계산에서는 native contact나 다른 coordinate를 추가하고 binning을 다시
설계합니다.

Target bin에 도달한 walker의 weight는 다음 iteration에서 folded basis state로
recycling됩니다. 따라서 생성된 walker 집합은 equilibrium conformational
ensemble이 아닙니다. 이 tutorial에서는 recycling과 weight 전달을 관찰하는
용도로만 사용합니다.

Segment input의 `irest=1`, `ntx=5`는 parent coordinate와 velocity를 이어받습니다.
`WEST_RAND32`에서 positive Langevin seed를 만들어 split된 walker가 같은
random-number stream을 반복하지 않게 합니다. 기존 `work/west.h5`를 이어서
실행할 때는 `./run.sh`을 다시 실행합니다. 새 run을 시작할 때만
`./init.sh --reset`을 사용합니다.

기본 engine은 한 GPU에서 serial work manager로 실행하는 `pmemd.cuda`입니다.
Executable만 `AMBER_ENGINE`으로 바꿀 수 있습니다. CPU worker 수와 system별
WESTPA 설정은 `3_Templates/6_WE/6.1_WESTPA_AMBER`에서 구성합니다.

`iteration_summary.tsv`의 total weight는 1에 가까워야 합니다.
`bin_occupancy.tsv`는 iteration별 segment 수와 weight를 보여주며,
`target_events.tsv`는 RMSD 3.0 Å 이상에 도달한 segment를 기록합니다.

Weight diagnostics는 finite이며 음수가 아닌 weight와 segment별 1차원 finite pcoord를 요구합니다. Total weight는 유한한 양수여야 합니다. 합을 1로 강제 보정하지 않고 실제 합을 출력합니다. 잘못된 HDF5를 읽으면 기존 TSV를 보존합니다. `calc_pcoord.sh`는 cpptraj output의 numeric RMSD와 column 수를 확인하고 잘못된 값을 반환하지 않습니다.

공개 analysis entry는 자동으로 `helpers/writer_guard.py`를 호출해 같은 output의 동시 writer를 거부합니다. Engine 실행부터 결과 게시까지 보호하며, signal 종료 시 child가 멈춘 뒤 lock을 해제합니다. Lock을 임의로 삭제해 실행을 재개하지 않습니다.

`download.sh`는 모든 asset과 `SHA256SUMS`를 staging에서 확인한 뒤 `helpers/publish_download.py`로 게시합니다. Transfer, checksum 또는 일반 publication 실패에서는 기존 파일을 보존하며, 관련 없는 preparation 파일도 유지합니다. `structure/.download.pending`가 남으면 prepare/build와 새 download가 거부됩니다. 보존된 staging과 marker를 점검하고, marker만 삭제해 이전 파일과 새 파일을 섞어 사용하지 않습니다.

### 중단 상태와 완료 iteration

`run.sh`는 `west.cfg`의 requested iteration 수와 HDF5의 `west_current_iteration-1`을 비교합니다. Wall-clock 제한으로 정상 중단되면 `paused`와 완료한 iteration 수를 출력합니다. 같은 input에서 `./run.sh`를 다시 실행해 이어갑니다.

`anal.py`는 current iteration보다 작은 iteration만 읽으며 모든 segment의 status가 완료인지 검사합니다. 다음 propagation을 위해 미리 만든 pending group은 diagnostics에 넣지 않습니다. 완료 metadata가 없거나 완료 iteration에 미완료 segment가 있으면 기존 TSV를 쓰기 전에 중단합니다.

## English

This example propagates PDB 1UAO Chignolin in explicit OPC water and uses the
Cα RMSD of residues 2–9 as its progress coordinate. AMBER supplies the same
unbiased dynamics used in conventional MD. Every 1 ps, WESTPA bins the walkers
by RMSD and splits or merges them while conserving statistical weight and
continuing from the parent restart.

Run `download.sh`, `prepare.py`, `build.sh`, `init.sh`, `run.sh`, and `anal.py`
in order. The build uses ff19SB, a 12 Å OPC box, minimization, 100 ps heating,
and 100 ps NPT equilibration. RMSD is least-squares fitted to the minimized
reference using the Cα atoms of residues 2–9. A preparation stage is skipped
only with successful completion evidence and all required outputs; partial results are preserved and rejected. Existing
`west.h5` or segment output protects the initialized WESTPA state from rebuilds.

The default configuration maintains four walkers per bin for 20 iterations.
The `[3.0, inf)` Å bin is labeled as a partially unfolded target, with 3.25 Å as
an interior representative value. This target is a tutorial diagnostic rather
than a folding definition. A short run may produce no target event, and target
counts or weights are not a folding/unfolding rate estimate. One-dimensional
Cα RMSD can also combine distinct conformations, so production studies need a
system-specific progress coordinate and binning strategy.

Walkers reaching the target transfer their weight to the folded basis state for
recycling in the next iteration. The resulting walkers therefore do not form an
equilibrium conformational ensemble; recycling is retained here as a workflow
and weight-handling exercise.

Segments continue parent coordinates and velocities with `irest=1` and
`ntx=5`. A positive Langevin seed derived from `WEST_RAND32` gives split walkers
independent random streams. Re-run `run.sh` to continue an initialized WESTPA
run; use `init.sh --reset` only to discard it and start again.

The default is serial `pmemd.cuda` on one GPU, with only the executable exposed
through `AMBER_ENGINE`. Configure CPU workers and system-specific WESTPA options
in `3_Templates/6_WE/6.1_WESTPA_AMBER`. Analysis reports total weight, effective
walker count, RMSD range, bin occupancy, and target arrivals.

### 동시 실행과 input 변경

Build와 run은 `work.writers/` registry를 공유합니다. 같은 output/state를 쓰는 작업은 동시에 실행하지 않습니다. `prepare.py`가 있는 경우 structure를 생성하는 작업도 input을 읽는 build와 충돌하면 거부합니다. 로컬 manager의 callback은 검증된 manager 보호를 이어받습니다. 단독 callback은 segment와 progress-coordinate output별 보호를 획득합니다.

Build와 WESTPA init/run은 topology, basis/reference, AMBER input, `west.cfg`와 progress-coordinate callback을 SHA256으로 비교합니다. 변경된 input이나 identity가 없는 기존 결과는 보존하고 거부합니다. `init.sh --reset`도 input 검사를 먼저 수행하며 동일 input일 때만 기존 reset 동작을 허용합니다. 변경된 계산은 새 tutorial copy에서 시작합니다. WESTPA가 weight, resampling과 HDF5 state를 관리합니다.

정상 종료, command 실패와 INT/TERM에서는 자식 process의 종료를 확인한 뒤 자기 lock만 해제합니다. SIGKILL이나 node 장애로 남은 lock은 자동 삭제하지 않습니다. Error에 표시된 lock과 `owner.json`의 host, PID, command, scope를 확인하고 scheduler와 해당 host에서 모든 writer와 자식 process가 종료됐는지 확인한 뒤 그 lock directory만 수동 제거합니다. PID가 로컬에서 보이지 않는다는 이유만으로 제거하지 않습니다. `.gate/`도 같은 확인이 필요합니다.

지원하는 `--dry-run`과 `--help`는 보호나 identity 파일을 생성하지 않습니다. 진행 중인 work를 이동하거나 identity를 수정해 재사용하지 않습니다. 보호는 로컬 filesystem과 로컬 자식 process로 검증했으며 network filesystem, remote MPI와 다른 node의 writer 종료는 미검증입니다.

### Concurrent runs and input changes

Build and run share the `work.writers/` registry and reject concurrent writers to the same output/state. Where present, `prepare.py` also rejects structure writes that overlap an active build reader. Local manager callbacks inherit a verified manager writer. Standalone callbacks acquire protection for their segment and progress-coordinate outputs.

Build and WESTPA init/run compare topology, basis/reference, AMBER inputs, `west.cfg` and progress-coordinate callbacks with SHA256. Changed inputs and results without identity records are preserved and rejected. `init.sh --reset` validates inputs before its existing reset behavior and accepts only matching inputs. Start a changed calculation in a new tutorial copy. WESTPA manages weights, resampling and HDF5 state.

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

이 완료 판정은 `build.sh`의 topology와 basis preparation에 적용합니다.
Walker continuation과 weight/resampling은 기존 WESTPA state와 manager가 담당합니다.

This completion check applies to topology and basis preparation in `build.sh`.
Walker continuation, weights, and resampling remain managed by WESTPA state and its manager.

Weight diagnostics require finite, nonnegative weights and finite one-dimensional pcoord for each segment. Total weight must be finite and positive; diagnostics report the actual sum without renormalizing it to one. Invalid HDF5 leaves existing TSV files intact. `calc_pcoord.sh` checks numeric RMSD and column counts before returning a cpptraj result.

Public analysis entries automatically use `helpers/writer_guard.py` to reject concurrent writers to the same output. Protection covers engine execution through publication, and signal cleanup drains children before releasing the lock. Do not delete a lock to force a retry.

`download.sh` validates every asset and `SHA256SUMS` in staging before publishing through `helpers/publish_download.py`. Transfer, checksum and ordinary publication failures preserve existing files, including unrelated preparation files. A retained `structure/.download.pending` blocks source readers and new downloads. Inspect the retained staging and marker; deleting only the marker can expose a mixed generation.

### Paused runs and completed iterations

`run.sh` compares the requested iteration count in `west.cfg` with `west_current_iteration-1` in HDF5. A normal wall-clock stop is reported as `paused`, with the completed count. Run `./run.sh` again with the same inputs to continue.

`anal.py` reads only iterations below the current iteration and checks that every segment has completed status. Pending groups prepared for the next propagation are excluded. Missing completion metadata or incomplete segments in a completed iteration stop analysis before replacing existing TSV files.
