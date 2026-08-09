# KcsA membrane MD / KcsA 막 단백질 MD

## 한국어

PDB 1K4C biological assembly에서 Fab을 제거한 KcsA tetramer를 사용합니다.
결정수와 detergent는 제거하고 selectivity filter의 K+ 7개는 유지합니다.
Force field는 ff19SB와 Lipid21, water model은 OPC입니다. Membrane 조성은
POPC 90%, POPE 5%, cholesterol 5%입니다.

Membrane MD는 protein뿐 아니라 bilayer의 orientation, leaflet composition,
area와 pressure response를 함께 준비해야 합니다. Coordinate build와 AMBER
topology build를 분리해 PACKMOL-Memgen의 geometry와 force-field naming을
각각 검사합니다. Simulation에서는 box의 x·y·z 방향이 서로 다르게 변할 수
있는 anisotropic pressure coupling을 사용합니다.

Build는 두 단계로 나눕니다.

1. [`1_Coordinate_Build/`](1_Coordinate_Build/README.md): RCSB assembly
   추출, KcsA 정리, PACKMOL-Memgen 막·물·이온 좌표 생성
2. [`2_Topology_Build/`](2_Topology_Build/README.md): Lipid21 명명 변환,
   tleap 검증, `parm7`/`rst7` 생성

[`3_Simulation/`](3_Simulation/README.md)은 1 ns equilibration과 10 ns
production을 실행합니다. Membrane 조성, K+ occupancy, E71 protonation,
온도와 pressure coupling은 system build 전에 정합니다.

## English

PDB 1K4C supplies the KcsA tetramer after Fab removal. Seven
selectivity-filter K+ ions are retained; crystallographic waters and detergent
are removed. The model uses ff19SB, Lipid21, OPC, and a symmetric
90% POPC / 5% POPE / 5% cholesterol bilayer.

Membrane MD adds bilayer orientation, leaflet composition, area, and pressure
response to the protein preparation problem. Separating coordinate packing
from AMBER topology construction allows geometry and force-field naming to be
checked independently. The simulation uses anisotropic pressure coupling so
the membrane-plane and normal box dimensions can respond separately.

The workflow separates coordinate construction, AMBER topology/restart
generation, and simulation. Set membrane composition, K+ occupancy, E71
protonation, temperature, and pressure coupling before the build. Production
is 10 ns.

## References / 참고 자료

- [RCSB PDB 1K4C](https://www.rcsb.org/structure/1K4C)
- [PACKMOL-Memgen](https://doi.org/10.1021/acs.jcim.9b00269)
- [Lipid21](https://doi.org/10.1021/acs.jctc.1c01217)
