# Stage 1: coordinate build / 1단계: 좌표 생성

## 한국어

`download.sh`는 1K4C biological-assembly PDB와 mmCIF를 받고 checksum을
기록합니다. `prepare.py`는 assembly의 네 model에서
KcsA chain C를 모아 A–D tetramer로 만들고, 겹쳐 있는 symmetry-copy K+를
7개로 정리하며 모든 결정수와 detergent를 제거합니다.

이 단계는 force field parameter를 만들지 않습니다. Protein과 filter ion을
막 normal에 맞춰 배치하고 lipid, water와 bulk ion을 채운 coordinate file을
만듭니다. Packing 결과를 먼저 검사하면 topology build error와 geometry 문제를
분리할 수 있습니다.

### Script 역할

| 파일 | 역할 |
| --- | --- |
| `download.sh` | 1K4C biological assembly PDB/mmCIF와 checksum을 저장합니다. |
| `prepare.py` | KcsA tetramer, chain ID와 filter K+를 정리한 protein PDB를 만듭니다. |
| `run.sh` | PACKMOL-Memgen을 호출해 mixed bilayer, water와 KCl coordinate를 생성합니다. |

~~~bash
cd 1_Simulation/1_MD/1.3_Membrane_Protein/1_Coordinate_Build
./download.sh
python3 prepare.py structure/1K4C.pdb1 work/kcsa-tetramer.pdb
./run.sh --dry-run work/kcsa-tetramer.pdb
./run.sh work/kcsa-tetramer.pdb
~~~

### 주요 option

PACKMOL-Memgen 기본값은 `POPC:POPE:CHL1=90:5:5`, water slab 20 Å와
0.15 M KCl입니다. 결정 구조의 K+ 축을 z축으로 사용합니다. Output에서
orientation, lipid piercing, leaflet별 lipid 수, water intrusion과 filter K+
7개를 확인합니다. `LIPIDS`, `LIPID_RATIO`, `WATER_DISTANCE` 및
`SALT_CONCENTRATION`으로 기본값을 바꿉니다. 다른 lipid 조성을 쓰려면
`LIPIDS`와 `LIPID_RATIO`를 함께 지정하고
`ALLOW_CUSTOM_COMPOSITION=1`을 설정합니다. Protonation은 `run.sh` 전에
결정합니다. 결과는 `work/packed/system-coordinates.pdb`입니다.

`LIPIDS`는 residue 종류, `LIPID_RATIO`는 상대 조성입니다. 두 목록의 길이는
같아야 합니다. `WATER_DISTANCE`는 membrane 양쪽 water slab 두께(Å),
`SALT_CONCENTRATION`은 bulk salt 농도(M)입니다. `WORK_DIR`를 바꾸면 independent
coordinate build를 기존 결과와 분리할 수 있습니다. PACKMOL-Memgen 자체
option을 시험할 때는 `PACKMOL_MEMGEN_OPTIONS`에 공백으로 구분해 지정합니다.

## English

`download.sh` records the RCSB biological-assembly sources and checksums.
`prepare.py` collects KcsA chain C from the four assembly models, renames
the tetramer A–D, reduces symmetry-copied K+ ions to the seven crystallographic
sites, and removes every crystal water and detergent molecule.

This stage creates coordinates, not force-field parameters. It orients the
protein/filter ions and packs lipids, water, and bulk ions so geometry can be
inspected before topology construction.

### Script roles

| File | Role |
| --- | --- |
| `download.sh` | Downloads the 1K4C biological assembly and records checksums. |
| `prepare.py` | Produces the cleaned A–D tetramer with seven filter ions. |
| `run.sh` | Runs PACKMOL-Memgen to build the mixed membrane and solvent. |

PACKMOL-Memgen defaults to `POPC:POPE:CHL1=90:5:5`, a 20 Å water slab, and
0.15 M KCl. The crystallographic ion axis defines z. Check orientation, lipid
piercing, leaflet counts, water intrusion, and the seven retained K+ ions. Set
`LIPIDS`, `LIPID_RATIO`, `WATER_DISTANCE`, or `SALT_CONCENTRATION` to change
the build settings. Changing the lipid composition requires both `LIPIDS` and
`LIPID_RATIO` plus `ALLOW_CUSTOM_COMPOSITION=1`. Set protonation before
`run.sh`. The resulting coordinate file is `work/packed/system-coordinates.pdb`.
`LIPIDS` and `LIPID_RATIO` define matched lipid lists and relative composition;
`WATER_DISTANCE` is in Å and `SALT_CONCENTRATION` is in molar units. `WORK_DIR`
selects a separate build location. `PACKMOL_MEMGEN_OPTIONS` passes additional
space-separated options to PACKMOL-Memgen.
