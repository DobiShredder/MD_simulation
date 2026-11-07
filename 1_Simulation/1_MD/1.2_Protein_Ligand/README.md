# T4 lysozyme–JZ4 conventional MD / T4 lysozyme–JZ4 일반 MD

## 한국어

PDB 3HTB의 T4 lysozyme L99A/M102Q–JZ4 complex를 사용합니다.
JZ4는 T4 lysozyme의 hydrophobic cavity에 결합한 중성 2-propylphenol입니다.
Protein은 ff19SB, ligand는 GAFF2/AM1-BCC, water model은 OPC를 사용합니다.
계산은 두 minimization, 200 ps heating, 100 ps equilibration, 1 ns production 순입니다.

System은 Lemkul의 GROMACS protein–ligand tutorial과 같지만 force field는 다릅니다.
Lemkul tutorial은 CHARMM36/CGenFF를 사용하고, 이 예제는 AMBER ff19SB/GAFF2로 구성합니다.
두 parameter set의 결과가 같다고 가정하지 않습니다.

Protein–ligand MD는 conventional MD와 같은 방식으로 좌표를 적분합니다.
다만 ligand의 bond order, protonation, net charge와 atom mapping이 추가됩니다.
이 정보가 달라지면 trajectory가 정상 종료해도 다른 chemical system을 계산합니다.

Ligand atom의 partial charge 계산 방식에 주의합니다.
일반적으로는 *ab initio* 양자 계산으로 분자 주변의 electrostatic potential을 계산하고,
이를 재현하도록 atom-centered partial charge를 RESP 등의 방법으로 fitting합니다.
이 계산은 `Gaussian`, `GAMESS` 같은 양자 계산 program으로 수행하며 이 tutorial에서는 다루지 않습니다.
여기서는 비용을 줄이기 위해 semi-empirical 방법인 AM1-BCC로 partial charge를 정의합니다.
새 protein–ligand system을 만들 때는 양자 계산 기반 charge를 권장합니다.

### Script 역할

| 파일 | 역할 | 주요 input과 output |
| --- | --- | --- |
| `download.sh` | 3HTB PDB/mmCIF와 JZ4 ideal SDF download | `structure/`의 source file과 `SHA256SUMS` |
| `prepare.py` | Protein과 JZ4 선택, alternate conformer A 선택, HIE31 지정 | `structure/complex.pdb` |
| `prepare.sh` | JZ4에 GAFF2 atom type과 AM1-BCC charge 생성, `parmchk2`로 누락 parameter 생성 | `work/jz4.mol2`, `work/jz4.frcmod` |
| `build.sh` | Complex solvation, neutralization과 topology build | `work/system.parm7`, `system.rst7`, `system.pdb` |
| `run.sh` | 두 minimization, heating, equilibration과 production 실행 | `work/*.out`, `*.info`, `*.rst7`, `*.nc` |

### 실행

```bash
cd 1_Simulation/1_MD/1.2_Protein_Ligand
./download.sh
python3 prepare.py structure/3HTB.raw.pdb structure/complex.pdb
./prepare.sh structure/JZ4_ideal.sdf
./build.sh structure/complex.pdb
./run.sh
```

`prepare.py`는 PO₄, BME와 water를 제거합니다.
PDB에서 보이지 않는 C-terminal Leu164는 복원하지 않으며 resolved residue 1–163만 사용합니다.
His31은 neutral-pH baseline으로 `HIE`를 사용합니다.
다른 pH나 chemical state를 계산하려면 build 전에 다시 결정합니다.

`prepare.sh`는 같은 SDF와 net charge로 완료한 parameter(`sqm.out`, `jz4.mol2`,
`jz4.frcmod`)를 재사용합니다. Input이 바뀌거나 완료 기록 없는 output이 있으면
파일을 보존하고 거부합니다.

필요한 program과 계산량은 [상위 README](../README.md#준비-사항)에 있습니다.
기본 engine은 `pmemd.cuda`이며 `AMBER_ENGINE`으로 바꿉니다.
`build.sh` 뒤에는 `leap.log`에서 JZ4 atom mapping, net charge, 추가된 parameter와
system charge를 확인합니다.

Production이 완료된 `work`에서 다시 실행하면 engine을 실행하지 않고
`Skipping completed production`을 출력한 뒤 정상 종료합니다.
실행 상태, 실패 후 재실행, 동시 실행 보호는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

### 주요 output과 완료 확인

| Stage | Input | 길이 | Positional restraint | Trajectory |
| --- | --- | --- | --- | --- |
| Solvent minimization | `min-solvent.in` | `maxcyc=5000`, 처음 `ncyc=2500`은 steepest descent | Protein·JZ4 heavy atom, 10 kcal·mol⁻¹·Å⁻² | 없음 |
| Whole-system minimization | `min-all.in` | `maxcyc=5000` | 없음 | 없음 |
| NVT heating | `heat.in` | `nstlim=100000`, 200 ps, 20→300 K | 5 kcal·mol⁻¹·Å⁻² | `heat.nc` 20 frame |
| NPT equilibration | `equil.in` | `nstlim=50000`, 100 ps | 1 kcal·mol⁻¹·Å⁻² | `equil.nc` 10 frame |
| NPT production | `production.in` | `nstlim=500000`, 1 ns | 없음 | `production.nc` 100 frame |

Trajectory frame과 energy는 10 ps(`ntwx=ntpr=5000`)마다, restart는 100 ps(`ntwr=50000`)마다
기록합니다. 정상 종료하면 terminal 마지막 두 줄이 다음과 같습니다.

```text
Completed: 1 ns production (work/production.out)
Production trajectory: work/production.nc
```

`cpptraj -p work/system.parm7 -y work/production.nc -tl`은 `Frames: 100`을
출력합니다. 다음은 [MM/GBSA analysis](../../../2_Analysis/6_Binding_Energy/6.1_MMGBSA/README.md)입니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `antechamber -nc 0` | 이 예제에서 사용하는 neutral JZ4의 net charge입니다. 다른 chemical state는 template에서 별도 system으로 준비합니다. |
| `-at gaff2`, `-c bcc` | GAFF2 atom type과 AM1-BCC charge method를 선택합니다. |
| `ntt=3`, `gamma_ln=1.0` | Heating 이후 300 K Langevin thermostat를 사용합니다. |
| `ntb=2`, `ntp=1`, `barostat=2` | Equilibration과 production을 isotropic Monte Carlo-barostat NPT로 실행합니다. |
| `ntc=2`, `ntf=2`, `dt=0.002` | 수소 bond에 SHAKE를 적용하고 2 fs timestep을 사용합니다. |
| `restraintmask` | Solvent minimization, heating과 equilibration에서 solvent/ion을 제외한 solute heavy atom을 restraint합니다. |
| `restraint_wt` | 10 → 5 → 1 kcal·mol⁻¹·Å⁻²로 줄이고 production은 `ntr=0`입니다. |
| `pres0=1.0`, `taup=2.0`, `cut=10.0` | 목표 압력 1 bar, pressure relaxation time 2 ps, nonbonded cutoff 10 Å입니다. |

### 결과 확인

Equilibration 중 volume이 지속적으로 발산하거나 box가 collapse하면 시간을
늘리기 전에 `leap.log`, `heat.out`, `equil.out`과 `equil.info`를 확인합니다.
Volume fluctuation 자체는 작은 NPT system에서 예상되지만 density runaway,
NaN 또는 SHAKE failure는 정상 equilibration이 아닙니다.

Production trajectory는 interaction analysis와 MM/GBSA·MM/PBSA input으로
사용할 수 있습니다. 1 ns 결과는 binding affinity 수렴을 의미하지 않습니다.

공통 확인 항목은 [상위 README](../README.md#결과-판단)에 있습니다. 이 system에서는
protein backbone에 맞춘 뒤 계산한 JZ4 heavy-atom RMSD로 ligand가 cavity 안에
머무는지 함께 봅니다.

### 자주 생기는 문제

`run.sh` message는 [상위 README](../README.md#자주-생기는-문제)에 정리했습니다.

| Message | 조치 |
| --- | --- |
| `antechamber not found.`, `parmchk2 not found.` | AmberTools 26 환경을 불러옵니다. |
| `antechamber run failed. See log: work/antechamber.log` | Log와 `work/sqm.out`에서 AM1 계산 오류를 확인합니다. SDF의 수소, bond order와 net charge를 먼저 봅니다. |
| `Topology build requires ligand parameters` | `prepare.sh`를 먼저 실행합니다. |
| `tleap failed. See work/tleap.stdout.log and work/leap.log` | `leap.log`에서 JZ4 atom 이름이 `jz4.mol2`와 맞는지 확인합니다. |

## English

This example uses the T4 lysozyme L99A/M102Q–JZ4 complex from PDB 3HTB.
JZ4 is neutral 2-propylphenol bound in the hydrophobic cavity. The model uses
ff19SB for the protein, GAFF2/AM1-BCC for JZ4, and OPC water. The workflow runs
two minimizations, 200 ps heating, 100 ps equilibration, and 1 ns production.

The molecular system follows the Lemkul GROMACS protein–ligand tutorial, but
the parameterization does not: that tutorial uses CHARMM36/CGenFF, whereas this
one uses AMBER ff19SB/GAFF2. Results from the two parameter sets should not be
assumed to be equivalent.

Protein–ligand MD integrates the coordinates in the same way as conventional
MD. The ligand additionally requires a defined bond order, protonation state,
net charge, and atom mapping. Changing any of these describes a different
chemical system even if the trajectory finishes normally.

Ligand partial charges require particular attention. A common protocol
calculates the molecular electrostatic potential with an *ab initio*
quantum-chemistry method and fits atom-centered partial charges, for example
with RESP. Programs such as Gaussian or GAMESS can perform the quantum
calculation, but that workflow is outside this tutorial. This example instead
uses the lower-cost semi-empirical AM1-BCC method. For a new protein–ligand
system, a quantum-chemistry charge protocol is recommended.

### Script roles

| File | Role | Main inputs and outputs |
| --- | --- | --- |
| `download.sh` | Downloads 3HTB PDB/mmCIF and the JZ4 ideal SDF with checksums. | source files and `SHA256SUMS` in `structure/` |
| `prepare.py` | Selects protein/JZ4, conformer A, and neutral HIE31. | `structure/complex.pdb` |
| `prepare.sh` | Generates GAFF2 atom types, AM1-BCC charges, and missing parameters with `parmchk2`. | `work/jz4.mol2`, `work/jz4.frcmod` |
| `build.sh` | Solvates and neutralizes the complex and writes AMBER topology files. | `work/system.parm7`, `system.rst7`, `system.pdb` |
| `run.sh` | Runs two minimizations, heating, equilibration, and production. | `work/*.out`, `*.info`, `*.rst7`, `*.nc` |

### Running

```bash
cd 1_Simulation/1_MD/1.2_Protein_Ligand
./download.sh
python3 prepare.py structure/3HTB.raw.pdb structure/complex.pdb
./prepare.sh structure/JZ4_ideal.sdf
./build.sh structure/complex.pdb
./run.sh
```

`prepare.py` removes phosphate, BME, and crystallographic waters. It keeps
resolved residues 1–163 and does not model unresolved C-terminal Leu164. His31
uses `HIE` as the neutral-pH baseline; decide again before the build for another
pH or chemical state.

`prepare.sh` reuses parameters (`sqm.out`, `jz4.mol2`, `jz4.frcmod`) completed
with the same SDF and net charge. Changed inputs or outputs without a completion
record are preserved and rejected.

Required programs and the computational cost are listed in the
[parent README](../README.md#prerequisites). `run.sh` defaults to
`pmemd.cuda`; set `AMBER_ENGINE` to use another executable.
After `build.sh`, check the JZ4 atom mapping, net charge, added parameters, and
total system charge in `leap.log`.

Rerunning after a completed production skips the engine, prints
`Skipping completed production`, and exits 0.
See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state, reruns after failure and
concurrent-run protection.

### Main outputs and completion check

| Stage | Input | Length | Positional restraint | Trajectory |
| --- | --- | --- | --- | --- |
| Solvent minimization | `min-solvent.in` | `maxcyc=5000`, first `ncyc=2500` steepest descent | Protein and JZ4 heavy atoms, 10 kcal·mol⁻¹·Å⁻² | None |
| Whole-system minimization | `min-all.in` | `maxcyc=5000` | None | None |
| NVT heating | `heat.in` | `nstlim=100000`, 200 ps, 20→300 K | 5 kcal·mol⁻¹·Å⁻² | `heat.nc`, 20 frames |
| NPT equilibration | `equil.in` | `nstlim=50000`, 100 ps | 1 kcal·mol⁻¹·Å⁻² | `equil.nc`, 10 frames |
| NPT production | `production.in` | `nstlim=500000`, 1 ns | None | `production.nc`, 100 frames |

Frames and energies are written every 10 ps (`ntwx=ntpr=5000`) and restarts
every 100 ps (`ntwr=50000`). A successful run ends with these two lines:

```text
Completed: 1 ns production (work/production.out)
Production trajectory: work/production.nc
```

`cpptraj -p work/system.parm7 -y work/production.nc -tl` prints
`Frames: 100`. Continue with the
[MM/GBSA analysis](../../../2_Analysis/6_Binding_Energy/6.1_MMGBSA/README.md).

### Key options

| Option | Meaning |
| --- | --- |
| `antechamber -nc 0` | Net charge of the neutral JZ4 used here. Prepare other chemical states as separate systems in the template. |
| `-at gaff2`, `-c bcc` | Selects GAFF2 atom types and the AM1-BCC charge method. |
| `ntt=3`, `gamma_ln=1.0` | 300 K Langevin thermostat after heating. |
| `ntb=2`, `ntp=1`, `barostat=2` | Isotropic Monte Carlo-barostat NPT for equilibration and production. |
| `ntc=2`, `ntf=2`, `dt=0.002` | SHAKE on bonds to hydrogen with a 2 fs timestep. |
| `restraintmask` | Restrains solute heavy atoms, excluding solvent and ions, during solvent minimization, heating, and equilibration. |
| `restraint_wt` | Reduced 10 → 5 → 1 kcal·mol⁻¹·Å⁻²; production uses `ntr=0`. |
| `pres0=1.0`, `taup=2.0`, `cut=10.0` | 1 bar target pressure, 2 ps pressure relaxation time, and 10 Å nonbonded cutoff. |

### Checking results

Persistent box divergence, density runaway, NaNs, or SHAKE failure should be
diagnosed from `leap.log`, `heat.out`, `equil.out`, and `equil.info`; a longer
run does not repair an unstable starting system. Volume fluctuations alone are
expected in a small NPT system.

The production trajectory can supply interaction and MM/GBSA or MM/PBSA
examples, but 1 ns does not establish a converged binding affinity.

General checks are listed in the [parent README](../README.md#judging-the-result).
For this system, also check that JZ4 stays in the cavity, using the JZ4
heavy-atom RMSD after fitting the protein backbone.

### Common problems

`run.sh` messages are listed in the [parent README](../README.md#common-problems).

| Message | Action |
| --- | --- |
| `antechamber not found.`, `parmchk2 not found.` | Load the AmberTools 26 environment. |
| `antechamber run failed. See log: work/antechamber.log` | Check the log and `work/sqm.out` for AM1 errors. Review the SDF hydrogens, bond orders, and net charge first. |
| `Topology build requires ligand parameters` | Run `prepare.sh` first. |
| `tleap failed. See work/tleap.stdout.log and work/leap.log` | Check in `leap.log` that the JZ4 atom names match `jz4.mol2`. |

## References / 참고 자료

- [Lemkul protein–ligand tutorial](https://www.mdtutorials.com/gmx/complex/index.html)
- [RCSB PDB 3HTB](https://www.rcsb.org/structure/3HTB)
