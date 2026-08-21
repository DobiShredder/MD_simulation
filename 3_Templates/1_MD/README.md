# Conventional MD templates / Conventional MD template

## 한국어

Soluble protein, protein–ligand와 membrane protein은 preparation 과정이 달라
별도 template로 구성합니다.

| Directory | 추가 input |
| --- | --- |
| `1.1_Soluble_Protein` | Build-ready protein PDB |
| `1.2_Protein_Ligand` | Complex PDB, RESP/GAFF2 MOL2와 frcmod |
| `1.3_Membrane_Protein` | Oriented protein PDB와 equilibrated Lipid21 bilayer patches |

세 `run.sh`는 `--preparation-only`, `--production-only`와 1-based inclusive
`--segments START-END`를 지원합니다. Segment 2 이후부터 시작하려면 직전
segment의 completion marker와 restart file이 있어야 합니다. 공통 build와 stage
설정은 [template 안내](../README.md)에 정리되어 있습니다.

## English

Soluble-protein, protein–ligand, and membrane-protein systems use different
preparation workflows and are kept as separate templates. The ligand template
requires reviewed RESP/GAFF2 parameters; the membrane template requires an
oriented protein and equilibrated Lipid21 bilayer patches.

All three runners support `--preparation-only`, `--production-only`, and
inclusive 1-based `--segments START-END`. Starting after segment 1 requires the
preceding completion marker and restart. See the [template guide](../README.md)
for shared build and stage controls.
