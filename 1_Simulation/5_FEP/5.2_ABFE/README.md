# T4 lysozyme–JZ4 ABFE / T4 lysozyme–JZ4 ABFE

<p align="center">
  <img src="../../../assets/simulation/abfe_decoupling_atoms.png" width="520" alt="JZ4 ABFE thermodynamic cycle과 두 decoupling leg / JZ4 ABFE thermodynamic cycle and two decoupling legs">
</p>

*Solvent와 restrained complex에서 charge와 LJ interaction을 각각 제거하는 두 decoupling 계산을 restraint correction과 연결해 physical binding cycle을 닫습니다. / Two decoupling calculations remove charge and LJ interactions in solvent and in the restrained complex, and restraint corrections close the physical binding cycle.*


## 한국어

PDB 3HTB의 JZ4를 T4 lysozyme complex와 물에서 단계적으로 decouple합니다.
Complex 계산에서는 ligand가 binding site를 벗어나지 않도록 Boresch restraint 6개를 먼저 연결합니다.
Restraint, electrostatic, van der Waals contribution과
standard-state correction을 thermodynamic cycle에 따라 계산합니다.

그림의 alchemical path는 물에서 interacting JZ4를 먼저 decouple한 뒤, interaction이
없는 ligand를 1 M reference에서 binding pose의 위치와 방향으로 restraint합니다.
이 standard-state restraint 항은 Boresch 식으로 계산하므로 별도 simulation을 하지
않습니다. 다음으로 binding site에서 restraint를 유지한 채 JZ4의 charge와 LJ
interaction을 다시 연결하고, 마지막으로 fully interacting complex의 restraint를
풉니다. 시작과 끝이 각각 solvated ligand와 bound complex이므로 이 우회 경로의
free-energy 합은 physical standard binding free energy와 같습니다.

```text
ΔG°bind = ΔGsolvent,charge + ΔGsolvent,LJ
          - ΔGcomplex,charge - ΔGcomplex,LJ
          + ΔGrestraint - ΔG°release
```

실제 simulation은 solvent와 complex에서 모두 `interacting → charge off → LJ off`
방향으로 수행합니다. Cycle 그림의 complex leg는 이를 반대로 지나가므로 complex
decoupling 두 항에 minus sign이 붙습니다. `ΔGrestraint`는 restrained bound
complex에서 restraint를 제거하는 sampled 값입니다. `ΔG°release`는 decoupled
ligand의 Boresch restraint를 풀어 1 M 상태로 보내는 analytic 값이므로 cycle에서는
그 역방향인 `-ΔG°release`가 들어갑니다.

### Script 역할

| 파일 | 역할 | 주요 output |
| --- | --- | --- |
| `download.sh` | 3HTB와 JZ4 ideal SDF download | `structure/` |
| `prepare.py` | T4 lysozyme와 JZ4를 선택하고 anchor metadata 기록 | `complex.pdb`, `preparation.tsv` |
| `build.sh` | JZ4 parameter, 원본·JZ4 두 copy·zero-charge topology와 65개 window 생성 | `work/build/`, `states.tsv` |
| `generate_inputs.py` (자동 호출) | Topology에서 restraint atom 번호, copy mask와 input 생성 | `restraints.tsv`, `work/restraint/`, `work/charge/`, `work/vdw/` |
| `run.sh` | Window별 MD와 1 ns production 실행 | Restart, trajectory, AMBER output |
| `anal.py` | Stage별 MBAR 계산과 standard-state correction 조합 | `free_energy.tsv`, `overlap_matrix.tsv` |

```bash
./download.sh
python3 prepare.py structure/3HTB.raw.pdb structure/complex.pdb
./build.sh structure/complex.pdb structure/JZ4_ideal.sdf
./run.sh
python3 anal.py
```

### 주요 option

JZ4는 GAFF2/AM1-BCC net charge 0으로 parameterize합니다. Protein은 ff19SB,
물은 OPC를 사용합니다. `generate_inputs.py`는 GLN102 `CG-CB-CA`와 JZ4
`C7-C8-C9`를 anchor로 선택하고 실제 topology atom 번호와 초기 restraint
geometry를 `restraints.tsv`에 기록합니다. Torsion reference는 Amber와 같은
ParmEd dihedral convention으로 계산합니다.

Restraint·charge stage는 11개 lambda state를 사용합니다. LJ stage는 endpoint
근처를 촘촘히 나눈 16개 state를 사용합니다. Charge와 LJ stage에서는 `icfe`와
`clambda`가 alchemical state를 정하고, `ifmbar=1`이 각 configuration의 potential
energy를 해당 stage의 모든 lambda에서 평가합니다. 이 full energy matrix가 MBAR의
input입니다.

Stage별 AMBER 설정은 다음과 같습니다.

| Stage | Topology | 주요 설정 |
| --- | --- | --- |
| Restraint | `complex.parm7` | TI 없음. `DISANG` force constant를 `(1-λ)`배로 줄임 |
| Charge | `{complex,solvent}_charge.parm7` (JZ4 두 copy) | `timask1=':164'`, `timask2=':165'`, `crgmask=':165'`, `ifsc=0` (solvent는 `:1`/`:2`) |
| LJ | `{complex,solvent}_uncharged.parm7` | `timask1=':JZ4'`, `timask2=''`, `ifsc=1`, `scmask1=':JZ4'`, `aces26=1` |

Charge stage는 Amber manual 27.1.8.1의 linear-scaling TI입니다. `build.sh`가 같은
좌표의 JZ4를 하나 더 넣은 topology를 LEaP로 만듭니다. λ=0의 V0는 charge가 있는
첫 copy, λ=1의 V1은 `crgmask`로 charge를 0으로 만든 두 번째 copy입니다. 두
copy는 서로 상호작용하지 않습니다. 두 번째 copy는 solute 뒤에 붙으므로 protein과
첫 copy의 atom 번호가 `complex.parm7`과 같습니다. `generate_inputs.py`는 copy
residue 번호를 topology에서 읽고 두 copy의 atom 이름, charge, 좌표와 restraint
atom 번호를 확인합니다. Pmemd에서 `crgmask`는 두 endpoint 모두에 적용되므로,
같은 JZ4를 `timask1`과 `timask2`에 함께 두면 charge가 양쪽에서 0이 되어 이
stage의 값도 0이 됩니다.

Window는 `work/restraint/complex/`, `work/charge/{complex,solvent}/`와
`work/vdw/{complex,solvent}/`에 생성됩니다. 각 directory 아래의 `000`부터
시작하는 번호가 lambda window입니다.

Solvent topology는 ligand와 box edge 사이에 20 Å buffer를 둡니다. 이는
`cut=10 Å`를 사용하는 `pmemd.cuda`가 작은 solvent box를 거부하지 않도록 가장
짧은 box dimension을 늘립니다.
완료 증거가 있는 stage는 production을 포함해 다시 실행하지 않고 건너뜁니다.
따라서 중단된 `./run.sh`를 다시 실행하면 남은 window부터 계산합니다. 완료 증거
없이 output이 남은 stage는 파일을 보존하고 중단하며, production도 덮어쓰지
않습니다. Error에 표시된 파일을 `work/` 밖으로 옮긴 뒤(예:
`mkdir -p work.failed/... && mv ... work.failed/.../`) `./run.sh`를 다시
실행합니다. `work/` 안의 다른 위치로 옮기면 identity가 없는 결과로 거부됩니다.

Restraint stage는 λ=0의 restrained complex에서 λ=1의 unrestrained complex로
진행합니다. 각 window의 `disang.rest`는 force constant에 `1-λ`를 곱한 일반 MD
input입니다. Soft-core TI로 restraint만 바꾸는 방식은 쓰지 않습니다. ACES26에서는
SC/CC `ele,vdw`가 항상 λ로 scaling되어(manual 27.1.7.4) ligand까지 decouple되기
때문입니다. Production은 `DUMPAVE=production.restraint.dat`에 6개 restraint 값을
5000 step마다 기록합니다. `anal.py`가 이 값으로 full-strength restraint energy
`U`를 다시 계산하고, state j의 energy를 `(1-λj)U`로 넣은 efep file을 만들어
MBAR에 넘깁니다. 이 energy 식은 AmberTools 26 sander의 restraint energy와 0.02
kcal/mol 이내로 일치했습니다. Complex minimization에도 같은 `DISANG` restraint를
적용해 heating 전에 anchor geometry가 흐트러지지 않게 합니다. Restraint stage에서
계산한 제거값은 같은 방향으로 binding cycle에 더합니다. AMBER의 `rk2`/`rk3`는 `U=rk(x-x0)^2`의 계수이므로 Boresch
analytic correction에서는 `K=2×rk`로 변환합니다. `standard_state_correction`은
decoupled ligand의 restraint를 풀어 1 M 상태로 옮기는 항이며 보통 음수입니다.
이 함수가 반환한 release free energy는 binding cycle에서 뺍니다.

JZ4의 net charge는 0이지만 atom별 partial charge interaction은 charge stage에서
제거합니다. LJ stage는 JZ4 charge를 0으로 만든 `complex_uncharged.parm7` 또는
`solvent_uncharged.parm7`을 사용하고 `crgmask`를 다시 적용하지 않습니다.
Soft-core input은 `aces26=1`과 명시적인 SC/CC nonbonded term 목록을 사용하며
`pmemd.cuda`에서 실행합니다.

JZ4의 net charge가 0이므로 ligand decoupling은 system의 net charge를 바꾸지
않습니다. `free_energy.tsv`의 leading PME net-charge correction은 0으로
기록됩니다. Restraint geometry와 window overlap을 바꾸었다면 thermodynamic
cycle과 standard-state correction을 다시 검토합니다.

`anal.py`는 AmberTools 26의 `edgembar-amber2dats.py`와
`edgembar --mode=AUTO`를 실행합니다. Full cross-state energy matrix가 있으면
MBAR를 사용하고, 없으면 모든 adjacent pair가 기록된 stage에 BAR를 사용합니다.
사용한 estimator는 `free_energy.tsv`에 stage별로 기록합니다. FE-ToolKit의
automatic equilibration, correlated-sample stride와 20회 bootstrap을 사용합니다.
Charge와 LJ window는 `production.out`, restraint window는
`production.restraint.dat`를 읽습니다. 더 긴 계산과 segment 구성은
`3_Templates/5_FEP/5.2_ABFE`에서 설정합니다.

| Output | 내용 |
| --- | --- |
| `work/free_energy.tsv` | Stage별 MBAR/BAR 값, analytic correction과 최종 `ΔG°bind` |
| `work/mbar_diagnostics.tsv` | State별 sample 수, 제거한 equilibration과 stride |
| `work/overlap_matrix.tsv` | Stage별 lambda overlap |
| `work/mbar/abfe_report.html` | FE-ToolKit convergence report |

다음 항목은 `pmemd.cuda`가 없어 미검증입니다. 짧은 run으로 먼저 확인합니다.

- Charge·LJ window mdout에 각 lambda의 `MBAR Energy analysis` block이 모두
  기록되는지 확인합니다.
- Charge stage의 두 copy linear TI에서 첫 copy에 건 Boresch restraint가 `DV/DL`에
  섞이지 않는지 확인합니다. 같은 complex charge window(예: λ=0.5)를 restraint
  유무로 짧게 돌려 `DV/DL` 평균을 비교합니다.
- Restraint stage의 λ=1 window(`rk=0`)도 `production.restraint.dat`를 쓰는지,
  pmemd DUMPAVE의 column이 sander처럼 `step`과 6개 값인지 확인합니다.

Build는 기존 topology/restart file이 있으면 input을 변경하기 전에 중단하고 파일을 보존합니다. 새 build 전에는 기존 `work/`를 다른 위치에 보관하거나 별도 tutorial 사본을 사용합니다.

### Analysis 결과 저장

`anal.py`는 새 extracted energy, report와 최종 TSV를 temporary generation에서
계산합니다. Extraction, estimator, TSV 또는 HTML 생성이 실패하면 기존
`mbar/`, `free_energy.tsv`, `mbar_diagnostics.tsv`, `overlap_matrix.tsv`를 유지합니다.
실패한 command의 최근 log 내용은 stderr에 출력합니다.

자동 호출되는 `helpers/result_generation.py`가 이 파일들을 검증하고 게시합니다.
완료 기록은 `work/.analysis-generation.json`입니다. 여러 파일의 게시 도중
중단되면 `work/.analysis.pending`이 consumer와 재실행을 차단합니다. 실행 process가
종료됐는지 확인한 뒤 marker에 적힌 previous/new directory를 보존하고 검사합니다.
Marker만 삭제하거나 파일을 개별적으로 섞지 않습니다.

외부 script에서 결과를 읽기 전에는 다음 검사를 사용합니다.

```bash
python3 helpers/result_generation.py work
```

공개 analysis entry는 자동으로 `helpers/writer_guard.py`를 호출해 같은 output의 동시 writer를 거부합니다. Engine 실행부터 결과 게시까지 보호하며, signal 종료 시 child가 멈춘 뒤 lock을 해제합니다. Lock을 임의로 삭제해 실행을 재개하지 않습니다.

`download.sh`는 모든 asset과 `SHA256SUMS`를 staging에서 확인한 뒤 `helpers/publish_download.py`로 게시합니다. Transfer, checksum 또는 일반 publication 실패에서는 기존 파일을 보존하며, 관련 없는 preparation 파일도 유지합니다. `structure/.download.pending`가 남으면 prepare/build와 새 download가 거부됩니다. 보존된 staging과 marker를 점검하고, marker만 삭제해 이전 파일과 새 파일을 섞어 사용하지 않습니다.

## English

This restrained double-decoupling example removes JZ4 interactions in the
3HTB T4 lysozyme complex and in bulk water. Six Boresch coordinates retain the
bound pose while electrostatic and Lennard-Jones interactions are decoupled.
The restraint, electrostatic, van der Waals, and standard-state contributions
are combined according to the thermodynamic cycle.

The alchemical path first decouples interacting JZ4 in water. The noninteracting
ligand is then placed at the bound position and orientation through the
analytical Boresch standard-state term, without a separate simulation. JZ4 is
coupled in the binding site while the restraint remains active, and the
restraint is finally released from the fully interacting complex. Because the
path connects solvated ligand and bound complex, its sum equals the physical
standard binding free energy:

```text
ΔG°bind = ΔGsolvent,charge + ΔGsolvent,LJ
          - ΔGcomplex,charge - ΔGcomplex,LJ
          + ΔGrestraint - ΔG°release
```

Both simulated decoupling legs run from interacting to charge-off to LJ-off.
The cycle traverses the complex leg in reverse, which gives the two complex
terms their minus signs. `ΔGrestraint` is the sampled release of the restraint
from the interacting bound complex. `ΔG°release` analytically releases the
decoupled restrained ligand to the 1 M state, so the reverse traversal enters
the cycle as `-ΔG°release`.

Run the five public entry points in the order shown above. `build.sh` uses
ff19SB, GAFF2/AM1-BCC, and OPC, writes the original, two-JZ4-copy, and
zero-JZ4-charge topologies, then creates 65 windows. Restraint and charge
stages use eleven lambda states; the soft-core LJ stages use sixteen states with
additional endpoint spacing. Each window contains 200 ps heating, 100 ps
equilibration, and one 1 ns production run.
JZ4 is parameterized with a net charge of zero. The protein anchors are GLN102
`CG-CB-CA`, and the ligand anchors are JZ4 `C7-C8-C9`.

| Stage | Topology | Key settings |
| --- | --- | --- |
| Restraint | `complex.parm7` | No TI; `DISANG` force constants scaled by `(1-λ)` |
| Charge | `{complex,solvent}_charge.parm7` (two JZ4 copies) | `timask1=':164'`, `timask2=':165'`, `crgmask=':165'`, `ifsc=0` (`:1`/`:2` in solvent) |
| LJ | `{complex,solvent}_uncharged.parm7` | `timask1=':JZ4'`, `timask2=''`, `ifsc=1`, `scmask1=':JZ4'`, `aces26=1` |

The charge stage is linear-scaling TI (Amber manual 27.1.8.1). LEaP adds a
second JZ4 at identical coordinates; V0 is the charged first copy and V1 the
second copy with charges removed by `crgmask`. The copies do not interact. The
copy is appended after the solute, so protein and first-copy atom indices match
`complex.parm7`. `generate_inputs.py` reads the copy residue numbers from the
topology and checks atom names, charges, coordinates, and restraint atom indices.
In pmemd `crgmask` applies to both endpoints, so placing the same JZ4 in both
`timask1` and `timask2` would zero its charges in both states and give a zero
charge leg.

The solvent topology uses a 20 Å solute-to-box-edge buffer to keep the shortest
box dimension out of the `pmemd.cuda` small-box guard with the 10 Å cutoff.
Stages with completion evidence, production included, are skipped, so rerunning
an interrupted `./run.sh` continues with the remaining windows. A stage with
output but no completion evidence is preserved and stops the run; production is
never overwritten. Move the files named in the error out of `work/` (for example:
`mkdir -p work.failed/... && mv ... work.failed/.../`) and rerun `./run.sh`.
Files moved elsewhere inside `work/` are rejected as results without identity.

The restraint stage is ordinary MD: each window scales the `DISANG` force
constants by `1-λ`, from fully restrained at lambda zero to unrestrained at
lambda one. A soft-core TI restraint stage is not used because ACES26 always
scales SC/CC `ele,vdw` with lambda (manual 27.1.7.4), which would also decouple
the ligand. Production writes the six restraint values every 5000 steps to
`DUMPAVE=production.restraint.dat`. `anal.py` recomputes the full-strength
restraint energy `U` and writes MBAR efep files with `(1-λj)U` for each state j.
This energy matched AmberTools 26 sander restraint energies within 0.02
kcal/mol. Complex minimization uses the same `DISANG` restraints so heating
does not start from displaced anchor geometry. Torsion references follow the
Amber/ParmEd dihedral convention. Although JZ4 is net neutral, the charge stage
removes its atom-centered partial-charge interactions. The LJ stage uses the
zero-JZ4-charge topology without applying `crgmask` a second time.
Soft-core interactions use the Amber 26 `aces26=1` format and require
`pmemd.cuda`.

`anal.py` uses FE-ToolKit MBAR when a stage has the full cross-state energy
matrix and falls back to adjacent-state BAR when all neighboring pairs are
available. The selected estimator is recorded for each stage in
`free_energy.tsv`. It reads `production.out` from charge and LJ windows and
`production.restraint.dat` from restraint windows, then adds the analytical
standard-state term. Use `3_Templates/5_FEP/5.2_ABFE` for longer or
segmented calculations. The leading PME
net-charge correction is zero because JZ4 is neutral. Outputs include bootstrap uncertainty,
per-state sampling diagnostics, stage overlap matrices, and an HTML convergence
report. The short windows and approximate correction are suitable for learning
the workflow, not for claiming a converged experimental binding affinity.

The restraint stage runs from a restrained to an unrestrained bound complex.
Its sampled removal free energy enters the binding cycle with the same sign,
while the negative analytical standard-state release term is subtracted. AMBER uses
`U=rk(x-x0)^2`; the analytical Boresch expression therefore uses `K=2*rk`.
Unverified without `pmemd.cuda`; check these in a short run first:

- Every charge and LJ mdout contains `MBAR Energy analysis` blocks for all lambdas.
- In the two-copy linear-TI charge stage, the Boresch restraint on the first
  copy does not enter `DV/DL`. Compare short runs of one complex charge window
  (for example λ=0.5) with and without the restraint.
- The λ=1 restraint window (`rk=0`) still writes `production.restraint.dat`,
  and pmemd DUMPAVE rows are `step` plus six values as in sander.

Build stops before changing inputs when topology/restart files already exist, preserving those files. Preserve the existing `work/` elsewhere or use a separate tutorial copy before a new build.

### 동시 실행과 input 변경

Build와 run은 `work.writers/` registry를 공유합니다. 같은 output/state를 쓰는 작업은 동시에 실행하지 않습니다. `prepare.py`가 있는 경우 structure를 생성하는 작업도 input을 읽는 build와 충돌하면 거부합니다.

Run은 재사용할 결과의 input을 SHA256으로 비교합니다. Topology, 최초 coordinate file, stage input, predecessor restart와 restraint가 바뀌거나 기존 결과에 identity 기록이 없으면 파일을 보존하고 거부합니다. 이 tutorial은 고정된 `work/`를 사용합니다. Input을 바꾼 계산은 기존 결과를 옮긴 뒤(예: `mv work work.old`) `./build.sh`부터 다시 실행합니다.

정상 종료, command 실패와 INT/TERM에서는 자식 process의 종료를 확인한 뒤 자기 lock만 해제합니다. SIGKILL이나 node 장애로 남은 lock은 자동 삭제하지 않습니다. Error에 표시된 lock과 `owner.json`의 host, PID, command, scope를 확인하고 scheduler와 해당 host에서 모든 writer와 자식 process가 종료됐는지 확인한 뒤 그 lock directory만 수동 제거합니다. PID가 로컬에서 보이지 않는다는 이유만으로 제거하지 않습니다. `.gate/`도 같은 확인이 필요합니다.

지원하는 `--dry-run`과 `--help`는 보호나 identity 파일을 생성하지 않습니다. 진행 중인 work를 이동하거나 identity를 수정해 재사용하지 않습니다. 보호는 로컬 filesystem과 로컬 자식 process로 검증했으며 network filesystem, remote MPI와 다른 node의 writer 종료는 미검증입니다.

### Concurrent runs and input changes

Build and run share the `work.writers/` registry and reject concurrent writers to the same output/state. Where present, `prepare.py` also rejects structure writes that overlap an active build reader.

Run compares inputs for result reuse with SHA256. Changed topology, initial coordinates, stage input, predecessor restart or restraint, and results without identity records, are preserved and rejected. This tutorial uses a fixed `work/`. For changed inputs, move the old results aside (for example: `mv work work.old`) and rerun `./build.sh`.

Normal exit, command failure and INT/TERM release only the owned lock after child termination is verified. Locks left by SIGKILL or node failure are retained. Inspect the reported lock and its `owner.json` host, PID, command and scopes; confirm through the scheduler and owning host that all writers and children stopped before manually removing only that lock directory. A PID missing locally is not sufficient. Apply the same checks to `.gate/`.

Supported `--dry-run` and `--help` do not create writer or identity files. Do not move active work trees or edit identities to reuse results. Protection was tested on a local filesystem with local child processes; network filesystems, remote MPI and termination of writers on other nodes remain unverified.

### Stage 완료 판정 / Stage completion

Input identity는 입력이 같은지 확인하며 engine의 성공 종료를 증명하지 않습니다.
Runner가 engine의 성공 종료와 필수 output을 확인한 뒤 만든 완료 증거가 있어야
stage를 재사용합니다. Output이 남았지만 완료 증거가 없거나 필수 output이
누락·비어 있으면 기존 결과를 보존하고 중단합니다. 기존 결과를 소급 인증하지
않습니다.
`ntwx=0`인 AMBER stage는 trajectory를 완료 조건으로 요구하지 않습니다.
지원되는 continuation은 기존 restart/state 전달 방식을 따릅니다.

Input identity checks unchanged inputs; it does not prove a successful engine exit.
A stage is reused only with completion evidence written after a successful engine
exit and required-output checks. Outputs without that evidence, or missing/empty
required outputs, are preserved and rejected. Existing results are not certified
retroactively. AMBER stages with `ntwx=0` do not require a trajectory for
completion. Supported continuation retains its existing restart/state handoff.

### Analysis result storage

`anal.py` calculates new extracted energies, reports, and final TSV files in a
temporary generation. Extraction, estimation, TSV, or HTML failure preserves
the previous `mbar/`, `free_energy.tsv`, `mbar_diagnostics.tsv`, and
`overlap_matrix.tsv`. Recent failed-command log lines are printed to stderr.

The automatically called `helpers/result_generation.py` validates and publishes
this group, recording completion in `work/.analysis-generation.json`. If multiple
file publication is interrupted, `work/.analysis.pending` blocks consumers and
reruns. Check that the process has ended, then preserve and inspect the
previous/new directories listed there. Do not remove only the marker or mix
individual files.

Before reading results in an external script, run the check below.

```bash
python3 helpers/result_generation.py work
```

Public analysis entries automatically use `helpers/writer_guard.py` to reject concurrent writers to the same output. Protection covers engine execution through publication, and signal cleanup drains children before releasing the lock. Do not delete a lock to force a retry.

`download.sh` validates every asset and `SHA256SUMS` in staging before publishing through `helpers/publish_download.py`. Transfer, checksum and ordinary publication failures preserve existing files, including unrelated preparation files. A retained `structure/.download.pending` blocks source readers and new downloads. Inspect the retained staging and marker; deleting only the marker can expose a mixed generation.
