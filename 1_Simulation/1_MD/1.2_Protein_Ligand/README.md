# Trypsin–benzamidine conventional MD / Trypsin–benzamidine 일반 MD

## 한국어

PDB 3PTB의 bovine beta-trypsin–benzamidine complex를 사용합니다. 결정수는
제거하고 bound benzamidine과 structural Ca2+는 유지합니다. Protein은 ff19SB,
ligand는 GAFF2/AM1-BCC, water model은 TIP3P입니다. Benzamidine의 기본 net
charge는 +1입니다.

~~~bash
cd 1_Simulation/1_MD/1.2_Protein_Ligand
./download.sh
python3 prepare.py structure/3PTB.raw.pdb structure/complex.pdb
./prepare.sh structure/BEN_ideal.sdf
./build.sh structure/complex.pdb
./run.sh --dry-run
./run.sh
~~~

Production은 10 ns입니다. Interaction 분석과 MM/GBSA·MM/PBSA input으로
사용할 수 있지만 binding affinity 수렴을 의미하지 않습니다. `leap.log`에서
disulfide bond, Ca2+, ligand atom mapping과 net charge를 확인합니다.

`prepare.py`는 SSBOND 기록의 CYS pair 6개를 CYX로 바꾸고
`structure/disulfides.leap`을 만듭니다. 대상 pH의 tautomer와 protonation은
`prepare.sh` 전에 정합니다. `prepare.sh`는 BEN ideal SDF에 GAFF2 atom
type과 AM1-BCC charge를 적용합니다. 생성된 mol2의 bond order, hydrogen과
charge 합을 확인합니다. Net charge를 바꾸려면 `LIGAND_CHARGE`를
지정합니다. 기본 engine은 `pmemd.cuda`입니다.

## English

PDB 3PTB supplies the bovine beta-trypsin–benzamidine complex. Crystallographic
waters are removed; bound benzamidine and structural Ca2+ are retained. The
model uses ff19SB, GAFF2/AM1-BCC, and TIP3P. Benzamidine defaults to net charge
+1.

Production is 10 ns. It can supply interaction and MM/GBSA or MM/PBSA input,
but not a converged binding affinity. Check disulfides, Ca2+, ligand atom
mapping, and net charge in `leap.log`. Set the target tautomer and protonation
before `prepare.sh`. The script assigns GAFF2 atom types and AM1-BCC charges
from the BEN ideal SDF. Check bond orders, hydrogens, and total charge in the
generated mol2. Set `LIGAND_CHARGE` to change the default +1 net charge.
`run.sh` uses `pmemd.cuda`; set `AMBER_ENGINE` to use another executable.

## References / 참고 자료

- [RCSB PDB 3PTB](https://www.rcsb.org/structure/3PTB)
