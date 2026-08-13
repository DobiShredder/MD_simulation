# KcsA membrane MD / KcsA 막 단백질 MD

## 한국어

membrane protein을 building 할 때 가장 중요한 것은 protein이 membrane에 묻혀 있는 orientation이 가장 중요합니다
이 튜토리얼에서는 OPM에 deposit되어 있는 orientation을 사용하여 building하는 방법을 안내합니다.
PDB 1K4C에서 Fab을 제거한 KcsA tetramer를 사용합니다.
Detergent와 bulk water는 제거하고,
Selectivity filter의 K+ 7개와 filter·cavity에 있는 crystal water 16개는 유지합니다.
Force field는 ff19SB와 Lipid21, water model은 OPC입니다.
이 튜토리얼에서 사용 될 Membrane의 조성은 POPC 90%, POPE 5%, cholesterol 5%입니다.

1K4C에서 빠진 Ser22·Arg117 side-chain atom은 closed KcsA 3EFF의 conformer를 local backbone에 alignment해 복원합니다.
Fixed-charge neutral-pH baseline으로 네 subunit의 E71을 `GLH`, D80을 `ASP`, H25를 `HIE`,
E118·E120을 `GLU`로 지정합니다.
Side chain 좌표가 불완전한 terminal H124는 제외합니다.
E71–D80 사이 proton transfer는 이 model이 표현하지 않습니다.

Membrane MD는 protein뿐 아니라 bilayer의 orientation, leaflet composition, area와 pressure response를 함께 준비해야 합니다.
Coordinate build와 AMBER topology build를 분리해 bilayer geometry와 force-field naming을 각각 검사합니다.
Simulation에서는 box의 x·y·z 방향이 서로 다르게 변할 수 있는 anisotropic pressure coupling을 사용합니다.


Build는 두 단계로 나눕니다.

1. [`1_Coordinate_Build/`](1_Coordinate_Build/README.md): OPM orientation,
   KcsA 정리, 평형화 Lipid21 bilayer 복제와 protein 삽입
2. [`2_Topology_Build/`](2_Topology_Build/README.md): Lipid21 명명 변환,
   tleap 검증, `parm7`/`rst7` 생성

[`3_Simulation/`](3_Simulation/README.md)은 100 ps equilibration과 1 ns production을 실행합니다.
다른 pH나 channel state를 다루려면 protonation, K+ occupancy와 초기 water 배치를 함께 재검토합니다.



## English

Protein orientation within the membrane is a central choice when building a
membrane-protein system. This tutorial uses the membrane placement deposited
in OPM for PDB 1K4C and retains the KcsA tetramer after Fab removal. Detergent
and bulk crystallographic waters are removed. Seven selectivity-filter K+ ions
and 16 filter/cavity waters are retained. The fixed-charge neutral-pH baseline
assigns E71 as `GLH`, D80 as `ASP`, H25 as `HIE`, and E118/E120 as `GLU` in
all four subunits. Missing Ser22 and Arg117 side-chain atoms are transferred
from closed KcsA 3EFF by local-backbone alignment. Terminal H124 is omitted
because its side-chain coordinates are incomplete. The model does not
represent proton transfer between E71 and D80. It uses ff19SB, Lipid21, OPC,
and a symmetric 90% POPC / 5% POPE / 5% cholesterol bilayer.

Membrane MD adds bilayer orientation, leaflet composition, area, and pressure
response to the protein preparation problem. Separating coordinate packing
from AMBER topology construction allows geometry and force-field naming to be
checked independently. The simulation uses anisotropic pressure coupling so
the membrane-plane and normal box dimensions can respond separately.

The workflow separates coordinate construction, AMBER topology/restart
generation, and simulation. A different pH or channel state requires a joint
review of protonation, K+ occupancy, and initial pore waters. Production is
1 ns.

## References / 참고 자료

- [RCSB PDB 1K4C](https://www.rcsb.org/structure/1K4C)
- [RCSB PDB 3EFF](https://www.rcsb.org/structure/3EFF)
- [Lipid21](https://doi.org/10.1021/acs.jctc.1c01217)
