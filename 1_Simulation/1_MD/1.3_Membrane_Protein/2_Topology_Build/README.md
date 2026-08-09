# Stage 2: topology build / 2단계: topology build

## 한국어

1단계 coordinate에 ff19SB, Lipid21과 OPC를 적용해 `system.parm7`과
`system.rst7`을 만듭니다.

Coordinate file의 atom/residue name은 force-field template와 정확히 맞아야
합니다. PACKMOL-Memgen의 기본 AMBER output은 Lipid21 naming을 사용합니다.
`run.sh`는 이 coordinate를 복사하고 `tleap.in`을 실행한 뒤 topology를 검사합니다.
PDB에는 AMBER restart에 필요한 periodic box 정보가 없으므로 `setBox system
"centers"`로 coordinate 전체를 감싸는 직육면체 box도 지정합니다.
Filter K+를 포함한 전체 charge는 `addionsrand system Cl- 0`으로 중화합니다.

### 파일 역할

| 파일 | 역할 |
| --- | --- |
| `run.sh` | Input 복사와 검사, tleap 실행 및 output 확인을 담당합니다. |
| `tleap.in` | ff19SB, Lipid21, OPC를 읽고 `system.parm7`, `system.rst7`, `system.pdb`를 저장합니다. |

~~~bash
cd 1_Simulation/1_MD/1.3_Membrane_Protein/2_Topology_Build
./run.sh --dry-run ../1_Coordinate_Build/work/packed/system-coordinates.pdb
./run.sh ../1_Coordinate_Build/work/packed/system-coordinates.pdb
~~~

### 주요 option

| Option | 의미 |
| --- | --- |
| `TLEAP` | AmberTools 설치에 맞는 tleap executable을 지정합니다. |
| `WORK_DIR` | Naming 변환 file, tleap log와 topology output을 저장할 directory입니다. |
| `source leaprc.*` | `tleap.in`에서 protein, lipid와 water force field 조합을 선택합니다. Naming과 water box를 함께 맞춰야 합니다. |

`work/leap.log`에서 unknown atom/residue, missing atom과 total charge를
확인합니다. `work/system.pdb`에는 KcsA residue 412개, filter K+ 7개와
초기 pore water 16개, 설정한 POPC:POPE:CHL1 조성이 남아 있어야
합니다. E71·D80·H25·H124의 AMBER residue name도 확인합니다.
`check` error가 있으면
topology를 사용하지 않습니다.

`TLEAP`은 실행 파일, `WORK_DIR`는 output directory를 바꿉니다. Force field와
water model을 바꾸려면 `tleap.in`의 `leaprc`와 water box를 함께 바꾸고 lipid
residue 호환성을 다시 확인합니다.

## English

Stage-1 coordinates are built into `system.parm7` and `system.rst7` with
ff19SB, Lipid21, and OPC.

PACKMOL-Memgen's default AMBER output already uses Lipid21 naming. `run.sh`
copies those coordinates, executes `tleap.in`, and checks the resulting
topology. The tleap input loads ff19SB, Lipid21, and OPC. Because PDB does not
carry the periodic box required by an AMBER restart, `setBox system "centers"`
also defines a rectangular box enclosing the generated coordinates.
`addionsrand system Cl- 0` neutralizes the complete system, including the
retained filter K+ ions.

Check unknown or missing atoms, total charge, 412 KcsA residues, seven filter
K+ ions, 16 initial pore waters, the selected protonation names, and the
POPC:POPE:CHL1 ratio. A topology with `check` errors is not ready for
simulation. The outputs are `work/system.parm7` and
`work/system.rst7`.
`TLEAP` overrides the executable and `WORK_DIR` selects the output directory.
Changing a force field or water model also requires compatible residue naming
and water-box settings.
