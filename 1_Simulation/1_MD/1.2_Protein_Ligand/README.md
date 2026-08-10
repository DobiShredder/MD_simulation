# T4 lysozyme–JZ4 conventional MD / T4 lysozyme–JZ4 일반 MD

## 한국어

PDB 3HTB의 T4 lysozyme L99A/M102Q–JZ4 complex를 사용합니다. JZ4는
T4 lysozyme의 hydrophobic cavity에 결합한 중성 2-propylphenol입니다.
Protein은 ff19SB, ligand는 GAFF2/AM1-BCC, water model은 TIP3P를
사용합니다.

System은 Lemkul의 GROMACS protein–ligand tutorial과 같지만 force field는
다릅니다. Lemkul tutorial은 CHARMM36/CGenFF를 사용하고, 이 예제는
AMBER ff19SB/GAFF2로 구성합니다. 두 parameter set의 결과가 같다고
가정하지 않습니다.

Protein–ligand MD는 conventional MD와 같은 방식으로 coordinate를
적분합니다. 다만 ligand의 bond order, protonation, net charge와 atom
mapping이 추가됩니다. 이 정보가 틀리면 trajectory가 정상 종료해도
다른 chemical system을 계산합니다.

### Script 역할

| 파일 | 역할 | 주요 input과 output |
| --- | --- | --- |
| `download.sh` | 3HTB PDB/mmCIF와 JZ4 ideal SDF download | `structure/`의 source file과 `SHA256SUMS` |
| `prepare.py` | Protein과 JZ4 선택, alternate conformer A 선택, HIE31 지정 | `structure/complex.pdb` |
| `prepare.sh` | JZ4에 GAFF2 atom type과 AM1-BCC charge 생성 | `work/jz4.mol2`, `work/jz4.frcmod` |
| `build.sh` | Complex solvation, neutralization과 topology build | `work/system.parm7`, `system.rst7`, `system.pdb` |
| `run.sh` | 두 minimization, heating, equilibration과 production 실행 | `work/*.out`, `*.info`, `*.rst7`, `*.nc` |

```bash
cd 1_Simulation/1_MD/1.2_Protein_Ligand
./download.sh
python3 prepare.py structure/3HTB.raw.pdb structure/complex.pdb
./prepare.sh structure/JZ4_ideal.sdf
./build.sh structure/complex.pdb
./run.sh --dry-run
./run.sh
```

`prepare.py`는 PO₄, BME와 결정수를 제거합니다. PDB에서 보이지 않는
C-terminal Leu164는 복원하지 않으며 resolved residue 1–163만 사용합니다.
His31은 neutral-pH baseline으로 `HIE`를 사용합니다. 다른 pH나 chemical
state를 계산하려면 build 전에 다시 결정합니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `LIGAND_CHARGE=0` | `antechamber -nc`에 전달할 JZ4 net charge입니다. Chemical state를 바꾸지 않았다면 수정하지 않습니다. |
| `-at gaff2`, `-c bcc` | GAFF2 atom type과 AM1-BCC charge method를 선택합니다. |
| `ntt=3`, `gamma_ln=1.0` | Heating 이후 300 K Langevin thermostat를 사용합니다. |
| `ntb=2`, `ntp=1`, `barostat=2` | Equilibration과 production을 isotropic Monte Carlo-barostat NPT로 실행합니다. |
| `ntc=2`, `ntf=2`, `dt=0.002` | 수소 bond에 SHAKE를 적용하고 2 fs timestep을 사용합니다. |
| `restraintmask` | Production 전 stage에서 solvent/ion을 제외한 solute heavy atom을 restraint합니다. |

Heating은 200 ps, equilibration은 100 ps, production은 1 ns입니다.
Equilibration 중 volume이 지속적으로 발산하거나 box가 collapse하면 시간을
늘리기 전에 `leap.log`, `heat.out`, `equil.out`과 `equil.info`를 확인합니다.
Volume fluctuation 자체는 작은 NPT system에서 예상되지만 density runaway,
NaN 또는 SHAKE failure는 정상 equilibration이 아닙니다.

Production trajectory는 interaction analysis와 MM/GBSA·MM/PBSA input으로
사용할 수 있습니다. 1 ns 결과는 binding affinity 수렴을 의미하지
않습니다. `leap.log`에서 JZ4 atom mapping, net charge, 추가된 parameter와
system charge를 확인합니다. 기본 engine은 `pmemd.cuda`입니다.

## English

This example uses the T4 lysozyme L99A/M102Q–JZ4 complex from PDB 3HTB.
JZ4 is neutral 2-propylphenol bound in the hydrophobic cavity. The model uses
ff19SB for the protein, GAFF2/AM1-BCC for JZ4, and TIP3P water.

The molecular system follows the Lemkul GROMACS protein–ligand tutorial, but
the parameterization does not: that tutorial uses CHARMM36/CGenFF, whereas this
one uses AMBER ff19SB/GAFF2.

### Script roles

| File | Role |
| --- | --- |
| `download.sh` | Downloads 3HTB and the JZ4 ideal SDF with checksums. |
| `prepare.py` | Selects protein/JZ4, conformer A, and neutral HIE31. |
| `prepare.sh` | Generates GAFF2 atom types, AM1-BCC charges, and missing parameters. |
| `build.sh` | Solvates and neutralizes the complex and writes AMBER topology files. |
| `run.sh` | Runs minimization, heating, equilibration, and production. |

The preparation removes phosphate, BME, and crystallographic waters. It keeps
resolved residues 1–163 and does not model unresolved C-terminal Leu164.
`LIGAND_CHARGE` defaults to zero. The MD controls use a 2 fs SHAKE timestep,
Langevin thermostat, and isotropic Monte Carlo-barostat NPT. Initial
solute-heavy-atom restraints are removed for production.

Heating is 200 ps, equilibration is 100 ps, and production is 1 ns. Persistent
box divergence, density runaway, NaNs, or SHAKE failure should be diagnosed
from `leap.log`, `heat.out`, `equil.out`, and `equil.info`; a longer run does not
repair an unstable starting system.

The trajectory can supply interaction and MM/GBSA or MM/PBSA examples, but it
does not establish a converged binding affinity. Check the JZ4 atom mapping,
net charge, missing parameters, and total system charge in `leap.log`.
`run.sh` defaults to `pmemd.cuda`; set `AMBER_ENGINE` to use another executable.

## References / 참고 자료

- [Lemkul protein–ligand tutorial](https://www.mdtutorials.com/gmx/complex/index.html)
- [RCSB PDB 3HTB](https://www.rcsb.org/structure/3HTB)
