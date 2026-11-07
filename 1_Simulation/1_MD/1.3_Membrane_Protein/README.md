# KcsA membrane MD / KcsA 막 단백질 MD

## 한국어

PDB 1K4C에서 Fab을 제거한 KcsA tetramer를 Lipid21 bilayer에 넣고 conventional MD를
실행합니다. Membrane protein build에서 가장 중요한 선택은 protein이 membrane에 묻힌
orientation입니다. 이 tutorial은 OPM에 deposit된 orientation을 사용합니다.

Membrane MD는 protein뿐 아니라 bilayer의 orientation, leaflet composition, area와
pressure response를 함께 준비해야 합니다. Coordinate build와 AMBER topology build를
분리해 bilayer geometry와 force-field naming을 각각 검사합니다. Simulation에서는 box의
x·y·z 방향이 서로 다르게 변할 수 있는 anisotropic pressure coupling을 사용합니다.

### System 구성

- Force field는 ff19SB와 Lipid21, water model은 OPC입니다.
- Membrane 조성은 POPC 90%, POPE 5%, cholesterol 5%입니다.
- Detergent와 bulk water는 제거합니다. Selectivity filter의 K+ 7개와 filter·cavity에
  있는 crystal water 16개는 유지합니다.
- 1K4C에서 빠진 Ser22·Arg117 side-chain atom은 closed KcsA 3EFF의 conformer를 local
  backbone에 alignment해 복원합니다.
- Fixed-charge neutral-pH baseline으로 네 subunit의 E71을 `GLH`, D80을 `ASP`, H25를
  `HIE`, E118·E120을 `GLU`로 지정합니다. E71–D80 사이 proton transfer는 이 model이
  표현하지 않습니다.
- Side chain 좌표가 불완전한 terminal H124는 제외합니다.

### 실행 순서

| 순서 | Directory | 내용 |
| --- | --- | --- |
| 1 | [`1_Coordinate_Build/`](1_Coordinate_Build/README.md) | OPM orientation, KcsA 정리, equilibration된 Lipid21 bilayer 복제와 protein 삽입 |
| 2 | [`2_Topology_Build/`](2_Topology_Build/README.md) | 1단계의 Lipid21 residue 이름을 유지한 coordinate로 tleap 검증과 `parm7`/`rst7` 생성 |
| 3 | [`3_Simulation/`](3_Simulation/README.md) | Solvent → lipid → protein 순서로 완화, 총 100 ps equilibration과 1 ns production |

Protein restraint는 heavy atoms → backbone → 전체 해제 순서로 진행합니다.
필요한 program과 계산량은 [상위 README](../README.md#준비-사항)에 있습니다.

세 단계의 writer lock은 `work.writers/` 대신 이 directory 옆의
`1.3_Membrane_Protein.writers/`에 함께 기록됩니다. 앞 단계의 `work/`를 읽는 동안
그 단계를 다시 build할 수 없습니다. 실행 상태, 실패 후 재실행, 동시 실행 보호는
[GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

다른 pH나 channel state를 다루려면 protonation, K+ occupancy와 초기 water 배치를 함께
재검토합니다.

## English

This tutorial inserts the KcsA tetramer from PDB 1K4C, with the Fab removed, into
a Lipid21 bilayer and runs conventional MD. Protein orientation within the membrane
is the central choice when building a membrane-protein system; this tutorial uses
the placement deposited in OPM.

Membrane MD adds bilayer orientation, leaflet composition, area, and pressure
response to the protein preparation problem. Separating coordinate packing from
AMBER topology construction allows geometry and force-field naming to be checked
independently. The simulation uses anisotropic pressure coupling so the
membrane-plane and normal box dimensions can respond separately.

### System

- ff19SB, Lipid21, and OPC water.
- A symmetric 90% POPC / 5% POPE / 5% cholesterol bilayer.
- Detergent and bulk crystallographic waters are removed. Seven
  selectivity-filter K+ ions and 16 filter/cavity waters are retained.
- Missing Ser22 and Arg117 side-chain atoms are transferred from closed KcsA 3EFF
  by local-backbone alignment.
- The fixed-charge neutral-pH baseline assigns E71 as `GLH`, D80 as `ASP`, H25 as
  `HIE`, and E118/E120 as `GLU` in all four subunits. The model does not represent
  proton transfer between E71 and D80.
- Terminal H124 is omitted because its side-chain coordinates are incomplete.

### Order

| Step | Directory | Content |
| --- | --- | --- |
| 1 | [`1_Coordinate_Build/`](1_Coordinate_Build/README.md) | OPM orientation, KcsA cleanup, replication of equilibrated Lipid21 bilayer patches, and protein insertion |
| 2 | [`2_Topology_Build/`](2_Topology_Build/README.md) | tleap checks and `parm7`/`rst7` generation from the stage-1 coordinates, which already use Lipid21 residue names |
| 3 | [`3_Simulation/`](3_Simulation/README.md) | Relaxation of solvent, lipids, and protein in order, 100 ps total equilibration, and 1 ns production |

Protein restraints progress from heavy atoms to backbone to none. Required
programs and the computational cost are listed in the
[parent README](../README.md#prerequisites).

All three steps record writer locks in `1.3_Membrane_Protein.writers/` beside this
directory instead of `work.writers/`. A step cannot be rebuilt while a later step
reads its `work/`. See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state, reruns
after failure and concurrent-run protection.

A different pH or channel state requires a joint review of protonation, K+
occupancy, and initial pore waters.

## References / 참고 자료

- [RCSB PDB 1K4C](https://www.rcsb.org/structure/1K4C)
- [RCSB PDB 3EFF](https://www.rcsb.org/structure/3EFF)
- [Lipid21](https://doi.org/10.1021/acs.jctc.1c01217)
