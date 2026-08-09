# Trypsin–benzamidine ABFE / Trypsin–benzamidine ABFE

## 한국어

PDB 3PTB의 benzamidine을 complex와 물에서 단계적으로 decouple합니다. Complex
계산에서는 ligand가 binding site를 벗어나지 않도록 Boresch restraint 6개를
먼저 연결합니다. Restraint, electrostatic, van der Waals contribution과
standard-state correction을 thermodynamic cycle의 부호에 맞춰 합칩니다.

### Script 역할

| 파일 | 역할 | 주요 output |
| --- | --- | --- |
| `download.sh` | 3PTB와 BEN ideal SDF download | `structure/` |
| `prepare.py` | BEN·Ca2+·disulfide 보존, Asp189 anchor 기록 | `complex.pdb`, `preparation.tsv` |
| `protonate_benzamidine.py` | RCSB neutral SDF를 BEN(+1)로 바꾸는 내부 helper | `work/ben-protonated.sdf` |
| `build.sh` | BEN parameter, charged/uncharged topology와 65개 window 생성 | `work/build/`, `states.tsv` |
| `generate_inputs.py` | Topology에서 restraint atom 번호와 input 생성 | `restraints.tsv`, `work/windows/` |
| `run.sh` | Window별 MD와 1 ns production 실행 | Restart, trajectory, AMBER output |
| `anal.py` | MBAR leg 계산, standard-state와 PME correction 조합 | `free_energy.tsv`, `overlap_matrix.tsv` |

```bash
./download.sh
python3 prepare.py structure/3PTB.raw.pdb structure/complex.pdb
./build.sh structure/complex.pdb structure/BEN_ideal.sdf
./run.sh --dry-run
./run.sh
python3 anal.py
```

### 주요 option

RCSB neutral SDF의 imine N에 H 하나와 formal charge를 추가한 뒤 BEN을
GAFF2/AM1-BCC net charge +1로 parameterize합니다. Protein은 ff19SB, 물은
TIP3P를 사용합니다. `generate_inputs.py`는 Asp189 `CA-CB-CG`와 BEN
`C7-C1-C2`를 anchor로 선택하고 실제 topology atom 번호를 `restraints.tsv`에
기록합니다.

Restraint·charge stage는 11개 lambda state를 사용합니다. LJ stage는 endpoint
근처를 촘촘히 나눈 16개 state를 사용합니다. `icfe`와 `clambda`가 alchemical
state를 정하고 `ifsc`/`scmask1`이 LJ endpoint의 singularity를 피합니다.
`ifmbar=1`은 각 configuration의 potential energy를 해당 stage의 모든 lambda에서
평가합니다. 이 full energy matrix가 MBAR의 input입니다.

Restraint stage는 λ=0의 unrestrained complex에서 λ=1의 restrained complex로
진행합니다. 모든 window는 같은 full-strength `DISANG` file을 사용하고,
`gti_nmropt=1`이 restraint energy를 lambda에 따라 scaling합니다. 따라서
restraint stage도 MBAR로 분석할 수 있습니다. 이 값을 binding cycle에 넣을 때는
부호를 바꿉니다. AMBER의 `rk2`/`rk3`는 `U=rk(x-x0)^2`의 계수이므로 Boresch
analytic correction에서는 `K=2×rk`로 변환합니다. `standard_state_correction`은
decoupled ligand의 restraint를 풀어 1 M 상태로 옮기는 항이며 보통 음수입니다.

Charge stage는 원래 topology와 `crgmask=':BEN'`을 사용합니다. LJ stage는
BEN charge를 0으로 만든 `complex_uncharged.parm7` 또는
`solvent_uncharged.parm7`을 사용하고 `crgmask`를 다시 적용하지 않습니다.
Soft-core input은 `aces26=1`과 명시적인 SC/CC nonbonded term 목록을 사용하며
`pmemd.cuda`에서 실행합니다.

Benzamidine decoupling은 system의 net charge를 바꿉니다. `anal.py`는 cubic-box
근사를 사용한 leading PME net-charge correction을 별도 행으로 기록합니다.
이는 모든 finite-size artifact를 대신하지 않습니다. Box 크기, restraint
geometry와 window overlap을 바꾸었다면 correction과 cycle을 다시 검토합니다.

`anal.py`는 AmberTools 26의 `edgembar-amber2dats.py`와
`edgembar --mode=MBAR`를 실행합니다. FE-ToolKit의 automatic equilibration,
correlated-sample stride와 20회 bootstrap을 사용합니다.

| Output | 내용 |
| --- | --- |
| `work/free_energy.tsv` | Stage별 MBAR 값, analytic correction과 최종 `ΔG°bind` |
| `work/mbar_diagnostics.tsv` | State별 sample 수, 제거한 equilibration과 stride |
| `work/overlap_matrix.tsv` | Stage별 lambda overlap |
| `work/mbar/abfe_report.html` | FE-ToolKit convergence report |

`gti_nmropt=1` restraint MBAR와 ACES26 MBAR energy matrix는 Amber 26
`pmemd.cuda` desktop short run으로 아직 검증하지 않았습니다. 실행 전 mdout에
각 lambda의 `MBAR Energy analysis` block이 모두 기록되는지 확인합니다.

## English

This restrained double-decoupling example removes benzamidine interactions in
the 3PTB trypsin complex and in bulk water. Six Boresch coordinates retain the
bound pose while electrostatic and Lennard-Jones interactions are decoupled.

Run the five public entry points in the order shown above. `build.sh` uses
ff19SB, GAFF2/AM1-BCC, and TIP3P, writes charged and zero-BEN-charge topologies,
then creates 65 windows. Restraint and charge
stages use eleven lambda states; the soft-core LJ stages use sixteen states with
additional endpoint spacing. Each window contains 200 ps heating, 1 ns
equilibration, and one 1 ns production segment.
The default ligand path adds one imine-N hydrogen and a +1 formal charge to the
neutral RCSB SDF. Boresch ligand anchors are `C7-C1-C2`.

The restraint stage uses one full-strength `DISANG` definition in every window.
`gti_nmropt=1` scales that restraint from the unrestrained to the restrained
state and `ifmbar=1` records its cross-state energies. The charge stage uses
`crgmask=':BEN'` with the charged topology. The LJ stage
uses the zero-BEN-charge topology without applying `crgmask` a second time.
Soft-core interactions use the Amber 26 `aces26=1` format and require
`pmemd.cuda`.

`anal.py` uses the AmberTools 26 FE-ToolKit MBAR estimator for all five sampled
stages. It then adds the analytical standard-state term and reports a leading
PME net-charge correction separately. Its outputs include bootstrap uncertainty,
per-state sampling diagnostics, stage overlap matrices, and an HTML convergence
report. The short windows and approximate correction are suitable for learning
the workflow, not for claiming a converged experimental binding affinity.

The restraint leg runs from an unrestrained to a restrained bound complex, so
its MBAR contribution enters the binding cycle with the opposite sign. AMBER uses
`U=rk(x-x0)^2`; the analytical Boresch expression therefore uses `K=2*rk`.
The `gti_nmropt=1` restraint-MBAR combination still requires an Amber 26
`pmemd.cuda` desktop smoke test.
