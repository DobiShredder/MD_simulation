# Stage 2: topology build / 2단계: topology build

## 한국어

1단계 coordinate를 Lipid21 atom/residue name으로 변환한 뒤 ff19SB,
Lipid21과 OPC로 `system.parm7`과 `system.rst7`을 만듭니다.

~~~bash
cd 1_Simulation/1_MD/1.3_Membrane_Protein/2_Topology_Build
./run.sh --dry-run ../1_Coordinate_Build/work/packed/system-coordinates.pdb
./run.sh ../1_Coordinate_Build/work/packed/system-coordinates.pdb
~~~

`work/leap.log`에서 unknown atom/residue, missing atom과 total charge를
확인합니다. `work/system.pdb`에는 KcsA residue 412개, filter K+ 7개와
설정한 POPC:POPE:CHL 조성이 남아 있어야 합니다. `check` error가 있으면
topology를 사용하지 않습니다.

## English

Stage-1 coordinates are converted to Lipid21 names and built into
`system.parm7` and `system.rst7` with ff19SB, Lipid21, and OPC.

Check unknown or missing atoms, total charge, 412 KcsA residues, seven filter
K+ ions, and the POPC:POPE:CHL ratio. A topology with `check` errors is not
ready for simulation. The outputs are `work/system.parm7` and
`work/system.rst7`.
