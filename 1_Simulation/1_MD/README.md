# System-based conventional MD / 시스템별 일반 MD

## 한국어

세 가지 system으로 AMBER 일반 MD를 연습합니다. Production은 모두 10 ns로
설정되어 있습니다.

- [수용성 단백질: chignolin (PDB 1UAO)](1.1_Soluble_Protein/README.md)
- [단백질–리간드: trypsin–benzamidine (PDB 3PTB)](1.2_Protein_Ligand/README.md)
- [막 단백질: KcsA (PDB 1K4C)](1.3_Membrane_Protein/README.md)

각 `download.sh`가 RCSB 구조와 checksum을 저장합니다. Protonation, missing
atom, 결정학적 첨가물과 force field는 build 전에 확인합니다. 기본 engine은
`pmemd.cuda`입니다. Chignolin과 trypsin–benzamidine은 TIP3P, KcsA는 OPC를
사용합니다. Download와 전처리 구조는 `structure/`, AMBER control
file은 `inputs/`, 생성된 topology·restart·trajectory는 `work/`에 둡니다.

## English

Three systems cover the basic AMBER MD workflow. Each production input is set
to 10 ns.

- [Soluble protein: chignolin (PDB 1UAO)](1.1_Soluble_Protein/README.md)
- [Protein–ligand: trypsin–benzamidine (PDB 3PTB)](1.2_Protein_Ligand/README.md)
- [Membrane protein: KcsA (PDB 1K4C)](1.3_Membrane_Protein/README.md)

Each `download.sh` records the RCSB source and checksum. Check protonation,
missing atoms, crystallographic additives, and force-field choices before the
build. Chignolin and trypsin–benzamidine use TIP3P; KcsA uses OPC. The default
engine is `pmemd.cuda`. Source and prepared structures use `structure/`, AMBER
control files use `inputs/`, and generated files use `work/`.
