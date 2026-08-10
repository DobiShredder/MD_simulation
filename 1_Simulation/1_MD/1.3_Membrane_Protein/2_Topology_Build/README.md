# Stage 2: topology build / 2단계: topology build

## 한국어

1단계 coordinate에 ff19SB, Lipid21과 OPC를 적용해 `system.parm7`과
`system.rst7`을 만듭니다. Coordinate에 기록한 Lipid21 modular residue
`PA`·`PC`·`PE`·`OL`·`CHL`은 `leaprc.lipid21`이 읽습니다.

PDB의 `CRYST1`과 같은 124.072×124.686×90.000 Å box를 명시한 뒤, 먼저
`addionsrand system Cl- 0`으로 KcsA와 filter K+를 포함한 전하를
중화합니다. 이어 K+ 126개와 Cl− 126개를 추가해 box volume을 기준으로 약
0.15 M KCl을 만듭니다. Ion은 water를 치환해 배치됩니다.

### 파일 역할

| 파일 | 역할 |
| --- | --- |
| `run.sh` | Coordinate 복사, tleap 실행과 output 존재 여부를 확인합니다. |
| `tleap.in` | ff19SB/Lipid21/OPC, box와 KCl을 적용해 topology를 저장합니다. |

~~~bash
cd 1_Simulation/1_MD/1.3_Membrane_Protein/2_Topology_Build
./run.sh --dry-run ../1_Coordinate_Build/work/system-coordinates.pdb
./run.sh ../1_Coordinate_Build/work/system-coordinates.pdb
~~~

`work/leap.log`에서 unknown residue, missing heavy atom, bond error와 `check`
결과를 확인합니다. Protein은 408 residues이고 filter K+ 7개와 pore water
16개가 bulk ion·water보다 먼저 위치합니다. E71·D80·H25 residue name과
leaflet당 POPC 185개, POPE 10개, cholesterol 10개도 확인합니다. `check`
error가 있으면 topology를 사용하지 않습니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `TLEAP` | AmberTools 환경의 tleap executable을 지정합니다. |
| `WORK_DIR` | tleap log, topology와 restart output directory를 바꿉니다. |

`TLEAP`은 executable, `WORK_DIR`는 output directory를 바꿉니다. Box나
조성을 바꾸면 고정된 salt pair 수 126도 다시 계산해야 합니다.

## English

This stage applies ff19SB, Lipid21, and OPC to the stage-1 coordinates. The
tleap input preserves the 124.072×124.686×90.000 Å box, neutralizes the
protein/filter-ion charge, and adds 126 KCl pairs, approximately 0.15 M for
this fixed volume. Verify the absence of unknown residues, missing heavy
atoms, bond errors, and `check` errors. Expected membrane counts are 185 POPC,
10 POPE, and 10 cholesterol molecules per leaflet. Outputs are
`work/system.parm7`, `work/system.rst7`, and `work/system.pdb`.
