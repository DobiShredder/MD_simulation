# T4 lysozyme–JZ4 ABFE / T4 lysozyme–JZ4 ABFE

<p align="center">
  <img src="../../../assets/simulation/abfe_decoupling_atoms.png" width="520" alt="JZ4 ABFE thermodynamic cycle과 두 decoupling leg / JZ4 ABFE thermodynamic cycle and two decoupling legs">
</p>

*Solvent와 restrained complex에서 charge와 LJ interaction을 각각 제거하는 두 decoupling 계산을 restraint correction과 연결해 physical binding cycle을 닫습니다. / Two decoupling calculations remove charge and LJ interactions in solvent and in the restrained complex, and restraint corrections close the physical binding cycle.*


## 한국어

PDB 3HTB의 JZ4를 T4 lysozyme complex와 물에서 단계적으로 decouple합니다.
Complex 계산에서는 ligand가 binding site를 벗어나지 않도록 Boresch restraint 6개를
먼저 연결합니다. Restraint, electrostatic, van der Waals contribution과
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

Window는 `work/restraint/complex/`, `work/charge/{complex,solvent}/`와
`work/vdw/{complex,solvent}/`에 생성됩니다. 각 directory 아래의 `000`부터
시작하는 번호가 lambda window입니다.

필요한 program과 계산량(65 windows, `pmemd.cuda` 260회, production 합계 65 ns)은
[FEP README](../README.md#필요한-program)에 있습니다.

### Analysis와 output

`anal.py`는 AmberTools 26의 `edgembar-amber2dats.py`와
`edgembar --mode=AUTO`를 실행합니다. Full cross-state energy matrix가 있으면
MBAR를 사용하고, 없으면 모든 adjacent pair가 기록된 stage에 BAR를 사용합니다.
사용한 estimator는 `free_energy.tsv`에 stage별로 기록합니다. FE-ToolKit의
automatic equilibration, correlated-sample stride와 20회 bootstrap을 사용합니다.
Charge와 LJ window는 `production.out`, restraint window는
`production.restraint.dat`를 읽습니다.

| Output | 내용 |
| --- | --- |
| `work/free_energy.tsv` | Stage별 MBAR/BAR 값, analytic correction과 최종 `ΔG°bind` |
| `work/mbar_diagnostics.tsv` | State별 sample 수, 제거한 equilibration과 stride |
| `work/overlap_matrix.tsv` | Stage별 lambda overlap |
| `work/mbar/abfe_report.html` | FE-ToolKit convergence report |

짧은 window와 근사 correction은 workflow 학습용이며 수렴된 실험 binding affinity를
주장하는 데 쓰지 않습니다. 부호와 overlap 기준은
[FEP README](../README.md#결과-해석)를 따릅니다.

`free_energy.tsv`의 행은 다음 순서입니다.

| 행 | 의미 |
| --- | --- |
| `restraint`, `complex_charge`, `complex_vdw`, `solvent_charge`, `solvent_vdw` | Stage별 sampled 값(simulation 방향) |
| `bound_restraint_cycle_contribution` | Cycle에 같은 부호로 더하는 `ΔGrestraint` |
| `standard_state_correction` | Boresch analytic `ΔG°release`. Cycle에서 뺍니다. |
| `leading_pme_net_charge_correction` | 중성 ligand이므로 0 |
| `raw_standard_binding_delta_g`, `corrected_standard_binding_delta_g` | 최종 `ΔG°bind`. 이 예제에서는 두 값이 같습니다. |

### 성공 확인

| Command | 정상 종료 |
| --- | --- |
| `./build.sh structure/complex.pdb structure/JZ4_ideal.sdf` | `Created 65 ABFE windows: work/restraint, work/charge, work/vdw`로 끝나고 `work/restraints.tsv`에 restraint 6개가 있습니다. |
| `./run.sh` | `ABFE production completed: work/restraint, work/charge, work/vdw`로 끝납니다. |
| `python3 anal.py` | `ABFE free-energy results: work/free_energy.tsv`로 끝납니다. |

Analysis가 실패하면 기존 결과를 유지하고 실패한 command의 최근 log를 stderr에
출력합니다. 외부 script에서 결과를 읽기 전에는 다음 검사를 사용합니다.

```bash
python3 helpers/result_generation.py work
```

완료 기록은 `work/.analysis-generation.json`입니다. `work/.analysis.pending`이
남으면 게시가 중간에 멈춘 것이므로 GUIDE.md 부록의 `.output.pending`과 같은
방식으로 처리합니다.

### 주요 option

JZ4는 GAFF2/AM1-BCC net charge 0으로 parameterize합니다. Protein은 ff19SB,
물은 OPC를 사용합니다. `generate_inputs.py`는 GLN102 `CG-CB-CA`와 JZ4
`C7-C8-C9`를 anchor로 선택하고 실제 topology atom 번호와 초기 restraint
geometry를 `restraints.tsv`에 기록합니다. Torsion reference는 Amber와 같은
ParmEd dihedral convention으로 계산합니다.

Restraint·charge stage는 11개 lambda state를 사용합니다. LJ stage는 endpoint
근처를 촘촘히 나눈 16개 state를 사용합니다. 각 window는 200 ps heating, 100 ps
equilibration과 1 ns production을 실행합니다. Charge와 LJ stage에서는 `icfe`와
`clambda`가 alchemical state를 정하고, `ifmbar=1`이 각 configuration의 potential
energy를 해당 stage의 모든 lambda에서 평가합니다. 이 full energy matrix가 MBAR의
input입니다.

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

Charge window의 minimization도 같은 `timask1`, `timask2`, `crgmask`를 쓰는 TI run입니다.
Pmemd는 TI run에서만 두 copy의 좌표를 같게 유지합니다. 이 설정이 없으면 두 copy가
따로 움직이고 heating이 `Atom ... does not have match in V1`로 멈춥니다.

Restraint stage는 λ=0의 restrained complex에서 λ=1의 unrestrained complex로
진행합니다. 각 window의 `disang.rest`는 force constant에 `1-λ`를 곱한 일반 MD
input입니다. Soft-core TI로 restraint만 바꾸는 방식은 쓰지 않습니다. ACES26에서는
SC/CC `ele,vdw`가 항상 λ로 scaling되어(manual 27.1.7.4) ligand까지 decouple되기
때문입니다. Production은 `DUMPAVE=production.restraint.dat`에 6개 restraint 값을
5000 step마다 기록합니다. `anal.py`가 이 값으로 full-strength restraint energy
`U`를 다시 계산하고, state j의 energy를 `(1-λj)U`로 넣은 efep file을 만들어
MBAR에 넘깁니다. 이 energy 식은 AmberTools 26 sander의 restraint energy와 0.02
kcal/mol 이내로 일치했습니다. Complex minimization에도 같은 `DISANG` restraint를
적용해 heating 전에 anchor geometry가 흐트러지지 않게 합니다.

Restraint stage에서 계산한 제거값은 같은 방향으로 binding cycle에 더합니다.
AMBER의 `rk2`/`rk3`는 `U=rk(x-x0)^2`의 계수이므로 Boresch analytic correction에서는
`K=2×rk`로 변환합니다. `standard_state_correction`은 decoupled ligand의 restraint를
풀어 1 M 상태로 옮기는 항이며 보통 음수입니다. 이 함수가 반환한 release free
energy는 binding cycle에서 뺍니다.

JZ4의 net charge는 0이지만 atom별 partial charge interaction은 charge stage에서
제거합니다. LJ stage는 JZ4 charge를 0으로 만든 `complex_uncharged.parm7` 또는
`solvent_uncharged.parm7`을 사용하고 `crgmask`를 다시 적용하지 않습니다.
Soft-core input은 `aces26=1`과 명시적인 SC/CC nonbonded term 목록을 사용하며
`pmemd.cuda`에서 실행합니다. Ligand decoupling은 system의 net charge를 바꾸지
않으므로 `free_energy.tsv`의 leading PME net-charge correction은 0으로
기록됩니다.

Solvent topology는 ligand와 box edge 사이에 20 Å buffer를 둡니다. 이는
`cut=10 Å`를 사용하는 `pmemd.cuda`가 작은 solvent box를 거부하지 않도록 가장
짧은 box dimension을 늘립니다.

Restraint geometry와 window overlap을 바꾸었다면 thermodynamic cycle과
standard-state correction을 다시 검토합니다. 더 긴 계산과 system별 설정은
`3_Templates/5_FEP/5.2_ABFE`에서 구성합니다.

### 미검증 항목

다음 항목은 `pmemd.cuda`가 없어 미검증입니다. 짧은 run으로 먼저 확인합니다.

- Charge·LJ window mdout에 각 lambda의 `MBAR Energy analysis` block이 모두
  기록되는지 확인합니다.
- Charge stage의 두 copy linear TI에서 첫 copy에 건 Boresch restraint가 `DV/DL`에
  섞이지 않는지 확인합니다. 같은 complex charge window(예: λ=0.5)를 restraint
  유무로 짧게 돌려 `DV/DL` 평균을 비교합니다.
- Restraint stage의 λ=1 window(`rk=0`)도 `production.restraint.dat`를 쓰는지,
  pmemd DUMPAVE의 column이 sander처럼 `step`과 6개 값인지 확인합니다.

### Window 재실행

완료 기록이 있는 stage는 production을 포함해 다시 실행하지 않습니다. 따라서
중단된 `./run.sh`를 다시 실행하면 남은 window부터 계산합니다. Partial output이
남은 window의 처리와 동시 실행 보호는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을
참고합니다.

### 문제 해결

| Message | 원인과 조치 |
| --- | --- |
| `ACES26 soft-core inputs must run with pmemd.cuda` 또는 `AMBER engine not found` | `AMBER_ENGINE`이 `pmemd.cuda`가 아니거나 Amber 26이 `PATH`에 없습니다. `pmemd.cuda` 경로를 지정합니다. |
| `Unexpected 3HTB protein atom/residue counts` 또는 `Expected 10 JZ4 heavy atoms` | `prepare.py` input이 `download.sh`가 받은 `structure/3HTB.raw.pdb`가 아닙니다. 원본 PDB로 다시 실행합니다. |
| `Protein anchor residue is not GLN` | `structure/preparation.tsv`의 anchor residue가 GLN102가 아닙니다. `prepare.py`를 다시 실행하고 `work`를 옮긴 뒤 build합니다. |
| `The two JZ4 copies differ in ..._charge.parm7` | Charge stage topology에서 두 번째 copy가 첫 copy와 다릅니다. `work/build/tleap_{complex,solvent}_charge.log`를 봅니다. |
| `restraint DUMPAVE output not found` 또는 `expected step and 6 restraint values` | Restraint window의 `production.restraint.dat`가 없거나 column이 다릅니다. 위 미검증 항목의 DUMPAVE 형식을 확인합니다. |
| `energy matrix cannot support adjacent-state BAR` | Charge·LJ window에 인접 state energy가 없습니다. `production.out`의 `MBAR Energy analysis` block과 `work/mbar/extract.log`를 확인합니다. |

## English

This restrained double-decoupling example removes JZ4 interactions in the
3HTB T4 lysozyme complex and in bulk water. In the complex, six Boresch
restraints are applied first so that the ligand stays in the binding site. The
restraint, electrostatic, van der Waals, and standard-state contributions are
combined according to the thermodynamic cycle.

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

### Script roles

| File | Role | Main output |
| --- | --- | --- |
| `download.sh` | Downloads 3HTB and the JZ4 ideal SDF | `structure/` |
| `prepare.py` | Selects T4 lysozyme and JZ4 and records anchor metadata | `complex.pdb`, `preparation.tsv` |
| `build.sh` | Creates JZ4 parameters, the original, two-JZ4-copy and zero-charge topologies, and 65 windows | `work/build/`, `states.tsv` |
| `generate_inputs.py` (called automatically) | Writes restraint atom indices, copy masks and inputs from the topology | `restraints.tsv`, `work/restraint/`, `work/charge/`, `work/vdw/` |
| `run.sh` | Runs per-window MD and 1 ns production | Restarts, trajectories, AMBER output |
| `anal.py` | Computes per-stage MBAR and combines the standard-state correction | `free_energy.tsv`, `overlap_matrix.tsv` |

```bash
./download.sh
python3 prepare.py structure/3HTB.raw.pdb structure/complex.pdb
./build.sh structure/complex.pdb structure/JZ4_ideal.sdf
./run.sh
python3 anal.py
```

Windows are created under `work/restraint/complex/`,
`work/charge/{complex,solvent}/` and `work/vdw/{complex,solvent}/`. The numbered
subdirectories starting at `000` are the lambda windows.

Required programs and the expected computation (65 windows, 260 `pmemd.cuda`
runs, 65 ns of total production) are listed in the
[FEP README](../README.md#required-programs).

### Analysis and outputs

`anal.py` runs AmberTools 26 `edgembar-amber2dats.py` and
`edgembar --mode=AUTO`. It uses MBAR when a stage has the full cross-state
energy matrix and falls back to BAR when all adjacent pairs are available. The
selected estimator is recorded for each stage in `free_energy.tsv`. FE-ToolKit
automatic equilibration, correlated-sample stride and 20 bootstrap samples are
used. Charge and LJ windows provide `production.out`; restraint windows provide
`production.restraint.dat`.

| Output | Content |
| --- | --- |
| `work/free_energy.tsv` | Per-stage MBAR/BAR values, analytical correction and final `ΔG°bind` |
| `work/mbar_diagnostics.tsv` | Per-state sample counts, removed equilibration and stride |
| `work/overlap_matrix.tsv` | Per-stage lambda overlap |
| `work/mbar/abfe_report.html` | FE-ToolKit convergence report |

The short windows and approximate correction are suitable for learning the
workflow, not for claiming a converged experimental binding affinity. See the
[FEP README](../README.md#interpreting-the-results) for the sign and overlap
guideline.

Rows in `free_energy.tsv`:

| Row | Meaning |
| --- | --- |
| `restraint`, `complex_charge`, `complex_vdw`, `solvent_charge`, `solvent_vdw` | Sampled stage values in the simulated direction |
| `bound_restraint_cycle_contribution` | `ΔGrestraint`, added to the cycle with the same sign |
| `standard_state_correction` | Analytical Boresch `ΔG°release`, subtracted in the cycle |
| `leading_pme_net_charge_correction` | Zero for the neutral ligand |
| `raw_standard_binding_delta_g`, `corrected_standard_binding_delta_g` | Final `ΔG°bind`; the two are equal in this example |

### Success check

| Command | Normal finish |
| --- | --- |
| `./build.sh structure/complex.pdb structure/JZ4_ideal.sdf` | Ends with `Created 65 ABFE windows: work/restraint, work/charge, work/vdw`; `work/restraints.tsv` lists six restraints. |
| `./run.sh` | Ends with `ABFE production completed: work/restraint, work/charge, work/vdw`. |
| `python3 anal.py` | Ends with `ABFE free-energy results: work/free_energy.tsv`. |

A failed analysis keeps the previous results and prints recent log lines of the
failed command to stderr. Before reading results in an external script, run the
check below.

```bash
python3 helpers/result_generation.py work
```

Completion is recorded in `work/.analysis-generation.json`. A leftover
`work/.analysis.pending` means publication stopped midway; handle it like
`.output.pending` in the GUIDE.md appendix.

### Key options

JZ4 is parameterized with GAFF2/AM1-BCC and a net charge of zero. The protein
uses ff19SB and the water OPC. `generate_inputs.py` selects GLN102 `CG-CB-CA`
and JZ4 `C7-C8-C9` as anchors and records the actual topology atom indices and
initial restraint geometry in `restraints.tsv`. Torsion references follow the
Amber/ParmEd dihedral convention.

Restraint and charge stages use eleven lambda states; the soft-core LJ stages
use sixteen states with additional endpoint spacing. Each window runs 200 ps
heating, 100 ps equilibration, and one 1 ns production run. In the charge and LJ
stages, `icfe` and `clambda` set the alchemical state, and `ifmbar=1` evaluates
each configuration at every lambda of that stage. This full energy matrix is the
MBAR input.

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

Charge-window minimization is also a TI run with the same `timask1`, `timask2`
and `crgmask`. Pmemd keeps the two copies at identical coordinates only in a TI
run; without these masks the copies drift apart and heating stops with
`Atom ... does not have match in V1`.

The restraint stage runs from a restrained complex at λ=0 to an unrestrained
complex at λ=1. It is ordinary MD: each window's `disang.rest` scales the force
constants by `1-λ`. A soft-core TI restraint stage is not used because ACES26
always scales SC/CC `ele,vdw` with lambda (manual 27.1.7.4), which would also
decouple the ligand. Production writes the six restraint values every 5000 steps
to `DUMPAVE=production.restraint.dat`. `anal.py` recomputes the full-strength
restraint energy `U` and writes MBAR efep files with `(1-λj)U` for each state j.
This energy matched AmberTools 26 sander restraint energies within 0.02
kcal/mol. Complex minimization uses the same `DISANG` restraints so heating
does not start from displaced anchor geometry.

The sampled restraint removal enters the binding cycle with the same sign.
AMBER uses `U=rk(x-x0)^2` for `rk2`/`rk3`, so the analytical Boresch expression
uses `K=2×rk`. `standard_state_correction` moves the decoupled ligand from the
restraint to the 1 M state and is usually negative; the release free energy it
returns is subtracted in the binding cycle.

Although JZ4 is net neutral, the charge stage removes its atom-centered
partial-charge interactions. The LJ stage uses `complex_uncharged.parm7` or
`solvent_uncharged.parm7` without applying `crgmask` a second time. Soft-core
inputs use `aces26=1` with an explicit SC/CC nonbonded term list and run in
`pmemd.cuda`. Ligand decoupling does not change the system net charge, so the
leading PME net-charge correction in `free_energy.tsv` is zero.

The solvent topology uses a 20 Å solute-to-box-edge buffer to keep the shortest
box dimension out of the `pmemd.cuda` small-box guard with the 10 Å cutoff.

If you change the restraint geometry or window overlap, review the
thermodynamic cycle and standard-state correction again. Use
`3_Templates/5_FEP/5.2_ABFE` for longer or system-specific calculations.

### Unverified items

These items are unverified without `pmemd.cuda`; check them in a short run first.

- Every charge and LJ mdout contains `MBAR Energy analysis` blocks for all lambdas.
- In the two-copy linear-TI charge stage, the Boresch restraint on the first
  copy does not enter `DV/DL`. Compare short runs of one complex charge window
  (for example λ=0.5) with and without the restraint.
- The λ=1 restraint window (`rk=0`) still writes `production.restraint.dat`,
  and pmemd DUMPAVE rows are `step` plus six values as in sander.

### Rerunning windows

Stages with a completion record, production included, are not rerun, so
rerunning an interrupted `./run.sh` continues with the remaining windows. See
[GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for handling windows with partial output and
for concurrent-run protection.

### Troubleshooting

| Message | Cause and fix |
| --- | --- |
| `ACES26 soft-core inputs must run with pmemd.cuda` or `AMBER engine not found` | `AMBER_ENGINE` is not `pmemd.cuda`, or Amber 26 is not on `PATH`. Point it to `pmemd.cuda`. |
| `Unexpected 3HTB protein atom/residue counts` or `Expected 10 JZ4 heavy atoms` | The `prepare.py` input is not the `structure/3HTB.raw.pdb` from `download.sh`. Rerun with the original PDB. |
| `Protein anchor residue is not GLN` | The anchor residue in `structure/preparation.tsv` is not GLN102. Rerun `prepare.py`, move `work` aside and rebuild. |
| `The two JZ4 copies differ in ..._charge.parm7` | The second copy in the charge-stage topology differs from the first. Read `work/build/tleap_{complex,solvent}_charge.log`. |
| `restraint DUMPAVE output not found` or `expected step and 6 restraint values` | A restraint window lacks `production.restraint.dat` or its columns differ. Check the DUMPAVE format listed under unverified items. |
| `energy matrix cannot support adjacent-state BAR` | A charge or LJ window lacks neighboring-state energies. Check `MBAR Energy analysis` blocks in `production.out` and `work/mbar/extract.log`. |

## References / 참고 자료

- [RCSB PDB 3HTB](https://www.rcsb.org/structure/3HTB)
- Boresch, S.; Tettinger, F.; Leitgeb, M.; Karplus, M. Absolute binding free
  energies: a quantitative approach for their calculation. *J. Phys. Chem. B*
  **2003**, 107, 9535–9551. [doi:10.1021/jp0217839](https://doi.org/10.1021/jp0217839)
