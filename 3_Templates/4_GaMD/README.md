# GaMD templates

## 한국어

세 template는 conventional MD equilibration 뒤에 potential-energy 통계를 모아
GaMD boost parameter를 만들고, 그 state를 production segment 사이에 이어받습니다.

| Directory | Boost |
| --- | --- |
| `4.1_GaMD` | system total potential과 dihedral dual boost |
| `4.2_LiGaMD3` | ligand essential, 나머지 nonbonded, bonded triple boost |
| `4.3_Pep-GaMD` | peptide와 나머지 system dual boost |

LiGaMD3와 Pep-GaMD는 Amber 26의 serial `pmemd.cuda`가 필요합니다. GaMD
parameter-preparation과 production은 NVT이며, 앞선 equilibration은 NPT입니다.
`gamd-restart.dat`와 MD restart를 모두 이어받아야 같은 bias state가 유지됩니다.
Preparation은 tutorial과 같은 whole-system minimization, restrained NVT
heating과 NPT equilibration 순서입니다. LiGaMD3와 Pep-GaMD input은
`gti_add_sc=1`, `ntf=1`을 사용합니다.

`--preparation-only`는 GaMD parameter preparation까지 실행합니다.
`--production-only`와 1-based inclusive `--segments START-END`는 완료된
`gamd-restart.dat`와 MD restart부터 production을 이어갑니다.

## English

Each template collects potential-energy statistics after conventional NPT
equilibration, constructs GaMD boost parameters, and continues both the MD
restart and GaMD state across production segments. GaMD preparation and
production use NVT. Amber 26 LiGaMD3 and Pep-GaMD require serial `pmemd.cuda`.
Preproduction follows whole-system minimization, restrained NVT heating, and
NPT equilibration. Selective variants retain `gti_add_sc=1` and `ntf=1`.
`--preparation-only` includes GaMD parameter preparation. `--production-only`
and inclusive 1-based `--segments START-END` continue from the completed GaMD
state and MD restart.
