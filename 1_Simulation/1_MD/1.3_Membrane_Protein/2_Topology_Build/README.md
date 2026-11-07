# Stage 2: topology build / 2단계: topology build

## 한국어

1단계 coordinate에 ff19SB, Lipid21과 OPC를 적용해 `system.parm7`과 `system.rst7`을 만듭니다.
Lipid21의 modular residue `PA`·`PC`·`PE`·`OL`과 `CHL`은 `leaprc.lipid21`이 읽습니다.

### 파일 역할

| 파일 | 역할 |
| --- | --- |
| `run.sh` | Coordinate를 `work/amber-named.pdb`로 복사하고 tleap을 실행합니다. |
| `prepare_tleap.py` | `CRYST1` box와 WAT 수를 읽어 tleap input을 만듭니다. `run.sh`가 자동으로 호출합니다. |
| `tleap.in` | Force field, box placeholder, neutralization과 KCl 추가를 정의한 template입니다. |

### 실행

~~~bash
cd 1_Simulation/1_MD/1.3_Membrane_Protein/2_Topology_Build
./run.sh ../1_Coordinate_Build/work/system-coordinates.pdb
~~~

이 단계는 AmberTools 26 `tleap`과 Python 3만 사용하고 GPU를 쓰지 않습니다.
`work/`에 `amber-named.pdb`, `tleap.in`, `system.parm7`, `system.rst7`, `system.pdb`,
`leap.log`, `tleap.stdout.log` 중 하나라도 있으면 빈 파일이어도 복사와 LEaP 실행 전에
거부합니다. 실행 상태와 재실행은 [GUIDE.md 부록](../../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

### 주요 output

| 파일 | 내용 |
| --- | --- |
| `work/system.parm7`, `work/system.rst7` | 3단계 simulation input |
| `work/system.pdb` | 확인용 구조 |
| `work/leap.log` | LEaP log |
| `work/tleap.stdout.log` | tleap의 terminal output |

정상 종료하면 마지막 줄에 `AMBER topology and restart: work`가 출력됩니다.
`leap.log`에서 unknown residue, missing heavy atom, parameter error와 `Errors = 0`을 확인합니다.
Chain C-terminus의 `OXT`를 tleap이 추가하는 message는 예상된 결과입니다.
Initial energy에서 `VDWAALS = *************`가 보이면
simulation을 진행하지 않고 1단계 coordinate를 다시 확인합니다.

### 주요 option

`prepare_tleap.py`는 PDB의 `CRYST1`을 그대로 사용합니다.
그러지 않으면 equilibration된 patch의 x·y 주기가 변할 수 있습니다.

0.15 M KCl pair 수는 total box volume이 아니라 water 분자 수로 계산합니다.

~~~text
KCl pairs = round(number of WAT × 0.15 / 55.5)
~~~

기본 KcsA coordinate에는 pore water를 포함해 약 28,000개의 WAT가 있으며, 76 KCl pairs가 생성됩니다.
Coordinate 크기나 water 수가 달라지면 값도 자동으로 바뀝니다.
Pair 수가 0이면 bulk-salt 추가 command를 생략하고 neutralization만 유지합니다.

`addionsrand`는 tleap 실행마다 다른 water를 선택할 수 있으므로
ion 초기 위치와 `system.rst7` checksum은 고정되지 않습니다.

### 자주 생기는 문제

| Message | 조치 |
| --- | --- |
| `Coordinate PDB not found` | 1단계 `run.sh`를 먼저 실행합니다. |
| `tleap failed. See work/tleap.stdout.log and work/leap.log` | `leap.log`의 첫 error에서 residue 이름과 atom 이름을 확인합니다. Lipid21 이름은 1단계 output을 그대로 사용합니다. |
| `Topology build output already exists` | `mv work work.old` 후 다시 실행합니다. 3단계가 이 `work`를 읽는 중이면 writer lock이 거부합니다. |

## English

This stage applies ff19SB, Lipid21, and OPC to the stage-1 coordinates and
writes `system.parm7` and `system.rst7`. `leaprc.lipid21` reads the modular
Lipid21 residues `PA`, `PC`, `PE`, `OL`, and `CHL`.

### File roles

| File | Role |
| --- | --- |
| `run.sh` | Copies the coordinates to `work/amber-named.pdb` and runs tleap. |
| `prepare_tleap.py` | Reads the `CRYST1` box and the WAT count to write the tleap input. Called automatically by `run.sh`. |
| `tleap.in` | Template defining the force fields, box placeholder, neutralization, and KCl addition. |

### Running

~~~bash
cd 1_Simulation/1_MD/1.3_Membrane_Protein/2_Topology_Build
./run.sh ../1_Coordinate_Build/work/system-coordinates.pdb
~~~

This step uses only AmberTools 26 `tleap` and Python 3; it does not use a GPU.
Any existing `work/amber-named.pdb`, `tleap.in`, `system.parm7`, `system.rst7`,
`system.pdb`, `leap.log`, or `tleap.stdout.log`, even an empty one, blocks copying
and LEaP execution. See [GUIDE.md appendix](../../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state and
reruns.

### Main outputs

| File | Content |
| --- | --- |
| `work/system.parm7`, `work/system.rst7` | Stage-3 simulation inputs |
| `work/system.pdb` | Structure for inspection |
| `work/leap.log` | LEaP log |
| `work/tleap.stdout.log` | tleap terminal output |

A successful run ends with `AMBER topology and restart: work`.
Check `leap.log` for unknown residues, missing heavy atoms, parameter errors, and
`Errors = 0`. Messages about tleap adding `OXT` at chain C-termini are expected.
Do not proceed if the initial energy reports an overflow such as
`VDWAALS = *************`; recheck the stage-1 coordinates.

### Key options

`prepare_tleap.py` transfers the PDB `CRYST1` dimensions unchanged; otherwise the
x/y periodicity of the equilibrated patch could change.

The number of 0.15 M KCl pairs is computed from the number of water molecules,
not the total box volume:

~~~text
KCl pairs = round(number of WAT × 0.15 / 55.5)
~~~

The default KcsA system contains about 28,000 waters, including pore waters, and
receives 76 KCl pairs. The value follows changes in coordinate size or water
count. When the pair count is zero, the bulk-salt command is omitted and
neutralization is kept.

Because `addionsrand` can select different waters on each tleap invocation, the
initial ion positions and the `system.rst7` checksum are not fixed.

### Common problems

| Message | Action |
| --- | --- |
| `Coordinate PDB not found` | Run the stage-1 `run.sh` first. |
| `tleap failed. See work/tleap.stdout.log and work/leap.log` | Check residue and atom names at the first error in `leap.log`. Use the Lipid21 names from the stage-1 output unchanged. |
| `Topology build output already exists` | Run `mv work work.old` and rerun. The writer lock refuses while stage 3 reads this `work`. |
