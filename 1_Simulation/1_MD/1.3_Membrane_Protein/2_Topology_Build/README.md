# Stage 2: topology build / 2단계: topology build

## 한국어

1단계 coordinate에 ff19SB, Lipid21과 OPC를 적용해 `system.parm7`과 `system.rst7`을 만듭니다.
Lipid21의 modular residue `PA`·`PC`·`PE`·`OL`과 `CHL`은 `leaprc.lipid21`이 읽습니다.

### 파일 역할

| 파일 | 역할 |
| --- | --- |
| `run.sh` | Coordinate를 `work/`로 복사하고 tleap을 실행합니다. |
| `prepare_tleap.py` | `CRYST1` box와 WAT 수를 읽어 tleap input을 만듭니다. `run.sh`가 자동으로 호출합니다. |
| `tleap.in` | Force field, box placeholder, neutralization과 KCl 추가를 정의한 template입니다. |

~~~bash
cd 1_Simulation/1_MD/1.3_Membrane_Protein/2_Topology_Build
./run.sh ../1_Coordinate_Build/work/system-coordinates.pdb
~~~

### 주요 option

`prepare_tleap.py`는 PDB의 `CRYST1`을 그대로 사용합니다.
그러지 않으면 평형화된 patch의 x·y 주기가 변할 수 있습니다.

0.15 M KCl pair 수는 total box volume이 아니라 water 분자 수로 계산합니다.

~~~text
KCl pairs = round(number of WAT × 0.15 / 55.5)
~~~

기본 KcsA coordinate에는 pore water를 포함해 약 28,000개의 WAT가 있으며, 76 KCl pairs가 생성됩니다.
Coordinate 크기나 water 수가 달라지면 값도 자동으로 바뀌니다.
`addionsrand`는 tleap 실행마다 다른 water를 선택할 수 있으므로
ion 초기 위치와 `system.rst7` checksum은 고정되지 않습니다.

주요 output은 `work/system.parm7`, `work/system.rst7`, `work/system.pdb`와 `work/leap.log`입니다.
`leap.log`에서 unknown residue, missing heavy atom, parameter error와 `Errors = 0`을 확인합니다.
Chain C-terminus의 `OXT`를 tleap이 추가하는 message는 예상된 결과입니다.
Initial energy에서 `VDWAALS = *************`가 보이면
simulation을 진행하지 않고 1단계 coordinate를 다시 확인합니다.

## English

This stage applies ff19SB, Lipid21, and OPC to the stage-1 coordinates.
`prepare_tleap.py` transfers the PDB `CRYST1` dimensions to a generated tleap
input and calculates 0.15 M KCl pairs from the number of water molecules. The
default KcsA system contains about 28,000 waters and receives 76 KCl pairs.
Because `addionsrand` selects solvent molecules anew for each tleap invocation,
the initial ion positions and restart checksum are not fixed.

Outputs are `work/system.parm7`, `work/system.rst7`, `work/system.pdb`, and
`work/leap.log`. Check for unknown residues, missing heavy atoms, parameter
errors, and `Errors = 0`. Do not proceed if the initial energy reports an
overflow such as `VDWAALS = *************`.
