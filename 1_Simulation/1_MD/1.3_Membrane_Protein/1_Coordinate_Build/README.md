# Stage 1: coordinate build / 1단계: 좌표 생성

## 한국어

`download.sh`는 PDB 1K4C biological assembly와 Lipid21로 평형화한
POPC·POPE·POPC/cholesterol bilayer coordinate를 받습니다. Lipid coordinate는
[Amber Lipid21 bilayer simulations](https://doi.org/10.5281/zenodo.14776136)에
공개된 GROMACS coordinate입니다. 이 단계에서는 GROMACS topology를 사용하지
않고 coordinate만 Lipid21 conformer로 사용합니다.

`prepare.py`는 네 assembly model의 KcsA chain C를 A–D tetramer로 만들고
filter K+ 7개와 filter·cavity water 16개를 유지합니다. Neutral-pH baseline은
E71=`GLH`, D80=`ASP`, H25=`HIE`, E118/E120=`GLU`입니다. 원본 H124는
imidazole side chain 좌표가 없으므로 임의로 복원하지 않고 제외합니다. 최종
protein은 subunit당 S22–G123, 모두 408 residues입니다.

`build_membrane.py`는 평형화한 128-POPC unit cell을 x와 y로 정확히 2×2
복제합니다. KcsA와 2 Å 이내에서 겹치는 lipid는 분자 단위로 제거하고 두
leaflet의 lipid 수를 맞춥니다. 각 leaflet의 205개 lipid 중 10개를 POPE,
10개를 cholesterol로 바꿔 POPC 90.2%, POPE 4.9%, cholesterol 4.9% 조성을
만듭니다. 원래 unit cell의 주기를 그대로 복제하므로 box 경계에서 lipid가
겹치지 않습니다.

이 방식은 Lemkul membrane tutorial처럼 평형화한 bilayer에 protein을
삽입하는 접근입니다. CHARMM-GUI가 pseudoatom을 lipid conformer로 치환하는
것과 목적은 비슷하지만 CHARMM-GUI server나 CHARMM force field는 사용하지
않습니다. 여러 all-atom lipid를 PACKMOL로 한 번에 채우는 과정도 없습니다.

### 파일 역할

| 파일 | 역할 |
| --- | --- |
| `download.sh` | 1K4C와 공개 Lipid21 bilayer coordinate, checksum을 저장합니다. |
| `prepare.py` | Tetramer, protonation name, filter K+와 pore water를 정리합니다. |
| `build_membrane.py` | Bilayer 복제, KcsA 삽입, 조성 변경과 water 배치를 수행합니다. |
| `run.sh` | `build_membrane.py`에 필요한 경로를 전달합니다. |

~~~bash
cd 1_Simulation/1_MD/1.3_Membrane_Protein/1_Coordinate_Build
./download.sh
python3 prepare.py structure/1K4C.pdb1 work/kcsa-tetramer.pdb
./run.sh --dry-run work/kcsa-tetramer.pdb
./run.sh work/kcsa-tetramer.pdb
~~~

결과는 `work/system-coordinates.pdb`입니다. Box는
124.072×124.686×90.000 Å입니다. Bulk KCl은 coordinate 단계가 아니라
2단계 tleap에서 추가합니다. VMD 등으로 protein orientation, leaflet 수,
lipid piercing, hydrophobic core의 bulk water와 filter K+·water가 유지됐는지
확인합니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `PYTHON` | NumPy를 사용할 수 있는 Python executable을 지정합니다. |
| `WORK_DIR` | Coordinate output을 저장할 directory를 바꿉니다. |

다른 조성이나 box 크기는 단순한 option 변경이 아닙니다. 평형화 source
patch, leaflet별 분자 수, protein–lipid overlap과 salt 수를 함께 다시
검증해야 합니다.

## English

`download.sh` retrieves the 1K4C biological assembly and equilibrated Lipid21
bilayer coordinates from the public Lipid21 dataset. `prepare.py` constructs
the A–D KcsA tetramer, retains seven filter K+ ions and 16 filter/cavity
waters, and applies the neutral-pH residue names. H124 lacks its imidazole
side-chain coordinates in 1K4C, so it is omitted instead of being rebuilt
arbitrarily. The resulting protein contains S22–G123 in each subunit.

`build_membrane.py` replicates the equilibrated 128-POPC unit cell exactly 2×2
in the membrane plane. It removes complete lipids that overlap KcsA, balances
the two leaflets, and replaces 10 of 205 lipids per leaflet with POPE and 10
with cholesterol. This gives approximately 90.2% POPC, 4.9% POPE, and 4.9%
cholesterol. The workflow follows the pre-equilibrated-bilayer insertion idea
used in the Lemkul tutorial without depending on CHARMM-GUI or packing all
components simultaneously.

The output is `work/system-coordinates.pdb` with a
124.072×124.686×90.000 Å box. Stage 2 adds bulk KCl. Inspect orientation,
leaflet counts, protein–lipid contacts, core water, and retained pore species
before building the topology.

## References / 참고 자료

- [Lemkul membrane protein tutorial](https://www.mdtutorials.com/gmx/membrane_protein/index.html)
- [CHARMM-GUI Membrane Builder method](https://pmc.ncbi.nlm.nih.gov/articles/PMC8158057/)
- [Amber Lipid21 bilayer simulations](https://doi.org/10.5281/zenodo.14776136)
