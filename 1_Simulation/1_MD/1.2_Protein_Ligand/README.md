# Trypsin–benzamidine conventional MD / Trypsin–benzamidine 일반 MD

## 한국어

PDB 3PTB의 bovine beta-trypsin–benzamidine complex를 사용합니다. 결정수는
제거하고 bound benzamidine과 structural Ca2+는 유지합니다. Protein은 ff19SB,
ligand는 GAFF2/AM1-BCC, water model은 TIP3P입니다. Benzamidine의 기본 net
charge는 +1입니다.

Protein–ligand MD의 propagation 자체는 conventional MD와 같지만, ligand의
chemical state와 parameter가 추가됩니다. Bond order, protonation, net charge와
protein–ligand atom mapping이 틀리면 trajectory가 정상 종료되어도 다른
chemical system을 계산하게 됩니다.

### Script 역할

| 파일 | 역할 | 주요 input과 output |
| --- | --- | --- |
| `download.sh` | 3PTB PDB/mmCIF와 BEN ideal SDF download | `structure/`의 source file과 `SHA256SUMS` |
| `prepare.py` | 결정수 제거, BEN·Ca2+ 보존, 6개 CYS pair의 CYX 변환 | `complex.pdb`, `disulfides.leap` |
| `protonate_benzamidine.py` | RCSB neutral SDF를 BEN(+1) 구조로 바꾸는 내부 helper | `work/ben-protonated.sdf` |
| `prepare.sh` | BEN(+1)에 GAFF2 atom type과 AM1-BCC charge 생성 | SDF → `work/ben.mol2`, `ben.frcmod` |
| `build.sh` | Protein, BEN, Ca2+, disulfide를 합쳐 solvation·topology build | `work/system.parm7`, `system.rst7`, `system.pdb` |
| `run.sh` | 두 minimization, heating, equilibration과 production 실행 | `work/*.out`, `*.rst7`, `*.nc` |

~~~bash
cd 1_Simulation/1_MD/1.2_Protein_Ligand
./download.sh
python3 prepare.py structure/3PTB.raw.pdb structure/complex.pdb
./prepare.sh structure/BEN_ideal.sdf
./build.sh structure/complex.pdb
./run.sh --dry-run
./run.sh
~~~

### 주요 option

| Option | 의미 |
| --- | --- |
| `LIGAND_CHARGE=1` | `antechamber -nc`에 전달할 BEN net charge입니다. Chemical state를 바꾼 뒤에만 수정합니다. |
| `-at gaff2`, `-c bcc` | GAFF2 atom type과 AM1-BCC charge method를 선택합니다. |
| `ntt=3`, `gamma_ln=1.0` | 300 K Langevin thermostat를 사용합니다. |
| `ntb=2`, `ntp=1`, `barostat=2` | Equilibration과 production을 isotropic NPT로 실행합니다. |
| `ntc=2`, `ntf=2`, `dt=0.002` | 수소 bond에 SHAKE를 적용하고 2 fs timestep을 사용합니다. |
| `restraintmask` | 초기 stage에서 solvent/ion을 제외한 solute heavy atom을 restraint합니다. |

Production은 10 ns입니다. Interaction 분석과 MM/GBSA·MM/PBSA input으로
사용할 수 있지만 binding affinity 수렴을 의미하지 않습니다. `leap.log`에서
disulfide bond, Ca2+, ligand atom mapping과 net charge를 확인합니다.

`prepare.py`는 SSBOND 기록의 CYS pair 6개를 CYX로 바꾸고
`structure/disulfides.leap`을 만듭니다. 대상 pH의 tautomer와 protonation은
`prepare.sh` 전에 정합니다. RCSB ideal SDF는 neutral benzamidine이므로
기본 `LIGAND_CHARGE=1`에서는 `protonate_benzamidine.py`가 imine N에 H를
하나 추가하고 +1 formal charge를 기록합니다. `prepare.sh`는 이 구조에
GAFF2 atom type과 AM1-BCC charge를 적용합니다. 생성된 mol2의 central atom
name `C7`, bond order, hydrogen과 charge 합을 확인합니다. Net charge를
바꾸면 자동 protonation을 적용하지 않으므로 ligand 구조도 함께 준비해야
합니다. 기본 engine은 `pmemd.cuda`입니다.

## English

PDB 3PTB supplies the bovine beta-trypsin–benzamidine complex. Crystallographic
waters are removed; bound benzamidine and structural Ca2+ are retained. The
model uses ff19SB, GAFF2/AM1-BCC, and TIP3P. Benzamidine defaults to net charge
+1.

Protein–ligand propagation follows conventional MD, but the ligand introduces
chemical-state and parameter choices. Bond order, protonation, net charge, and
atom mapping must describe the intended ligand before simulation.

### Script roles

| File | Role |
| --- | --- |
| `download.sh` | Downloads 3PTB and the BEN ideal SDF with checksums. |
| `prepare.py` | Retains BEN/Ca2+, removes waters, and prepares six disulfides. |
| `protonate_benzamidine.py` | Internally converts the neutral RCSB SDF to BEN(+1). |
| `prepare.sh` | Generates GAFF2 atom types, AM1-BCC charges, and missing parameters. |
| `build.sh` | Builds and solvates the complete complex. |
| `run.sh` | Runs minimization, heating, equilibration, and production. |

`LIGAND_CHARGE` controls the `antechamber` net charge. The MD controls use a
2 fs SHAKE timestep, Langevin thermostat, and isotropic Monte Carlo-barostat
NPT. Initial solute-heavy-atom restraints are removed for production.

Production is 10 ns. It can supply interaction and MM/GBSA or MM/PBSA input,
but not a converged binding affinity. Check disulfides, Ca2+, ligand atom
mapping, and net charge in `leap.log`. Set the target tautomer and protonation
before `prepare.sh`. With the default `LIGAND_CHARGE=1`, the neutral RCSB ideal
SDF is protonated by adding one imine-N hydrogen and a +1 formal charge before
GAFF2/AM1-BCC assignment. Check the central `C7` mapping, bond orders,
hydrogens, and total charge in the generated mol2. A different net charge also
requires a matching ligand structure.
`run.sh` uses `pmemd.cuda`; set `AMBER_ENGINE` to use another executable.

## References / 참고 자료

- [RCSB PDB 3PTB](https://www.rcsb.org/structure/3PTB)
