# Funnel Metadynamics Scaffold

## 한국어

> 아직 실행하지 않습니다. `run.sh`는 의도적으로 오류를 반환합니다.

Funnel MetaD는 ligand가 binding site에서 bulk solvent로 이동하는 경로를
funnel-shaped restraint 안에 제한합니다. Binding site 가까이에서는 원뿔 영역을,
bulk에서는 원통 영역을 사용해 ligand가 탐색해야 하는 solvent volume을 줄입니다.
Bias는 보통 funnel axis 방향 위치와 axis에서 떨어진 거리에 적용합니다.

Example system은 trypsin–benzamidine 3PTB입니다. 다음 명령은 geometry 검토에
필요한 원본 PDB, mmCIF와 BEN SDF만 다운로드합니다.

```bash
cd 1_Simulation/7_MetaD/7.2_funnel-MetaD
./download.sh
```

Runnable template로 만들기 전에 다음 선택을 구조에서 확인해야 합니다.

| 항목 | 필요한 결정 |
|---|---|
| Alignment | stable receptor atom group과 reference structure |
| Funnel axis | binding pocket 안쪽 point와 solvent 방향 point |
| Ligand | periodic molecule reconstruction과 BEN COM atom group |
| Geometry | cone length, opening angle, cylinder radius와 axial 범위 |
| Walls | `lp`와 `ld`에 적용할 wall 위치와 force constant |

이 값은 protein–ligand system마다 달라서 3PTB 구조를 보지 않고 고정하지
않습니다. 기존 φ/ψ OPES input은 Funnel MetaD가 아니므로 제거했습니다.
Geometry가 정해지면 PLUMED 2.10 `FUNNEL_PS`/`FUNNEL` module availability,
PBC 처리와 short coupled run을 확인해야 합니다.

Binding free energy를 계산하려면 bound/unbound basin sampling, reweighting과
funnel volume의 standard-state correction이 추가로 필요합니다. Tutorial 길이의
trajectory만으로 정량 값을 보고하지 않습니다.

참고: [PLUMED 2.10 FUNNEL_PS](https://www.plumed.org/doc-v2.10/user-doc/html/_f_u_n_n_e_l__p_s.html)

## English

This directory is intentionally not runnable. Funnel MetaD confines the ligand
to a conical binding-site region connected to a cylindrical bulk region, then
biases coordinates along and away from the funnel axis. `download.sh` retrieves
3PTB and the BEN ligand for geometry design. A runnable input still requires an
alignment group, two system-specific axis points, ligand reconstruction, funnel
dimensions, and wall parameters. `run.sh` fails until those choices and the
PLUMED funnel module are validated. Quantitative binding free energies would
also require reweighting, basin convergence, and a standard-state volume
correction.
