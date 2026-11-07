# Secondary structure / 이차 구조

## 한국어

Cpptraj의 DSSP implementation으로 Chignolin residue별 secondary structure를
분류합니다. Kabsch–Sander hydrogen-bond geometry를 사용하며 integer code
0–7은 None, extended, bridge, 3-10 helix, alpha helix, pi helix, turn, bend에
대응합니다.

`run.sh`는 [Chignolin conventional MD](../../../1_Simulation/1_MD/1.1_Soluble_Protein/README.md)의
`work/system.parm7`과 `work/production.nc`를 직접 읽습니다. 아래 command는 이
directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`python3 anal.py --save-figure figures`처럼 실행하면 figure를 화면에 표시하면서
`figures/secondary_structure.png`(150 dpi)로도 저장합니다. 저장 directory는 `output/` 밖에
둡니다. Option이 없으면 image file을 만들지 않습니다.

| Output | Column | 단위 |
| --- | --- | --- |
| `secondary_structure.dat` | `Frame`, residue별 column(`GLY:1` … `GLY:10`)의 state code | 0–7 |
| `secondary_byresidue.dat` | `#Residue`, `Extended`, `Bridge`, `3-10`, `Alpha`, `Pi`, `Turn`, `Bend` | 분율 0–1 |
| `secondary_total.dat` | `Frame`, `DSSP[Extended]` … `DSSP[Bend]`: 전체 residue 중 각 state 분율 | 0–1 |

`anal.py`는 residue-time map과 state fraction을 표시합니다. Cpptraj total
output에는 `None` column이 없으므로 Python에서 나머지 분율로 계산합니다. 접힌
hairpin에서는 strand residue가 주로 `Extended`(1), 가운데 turn residue가
`Turn`(6)으로 분류됩니다.

다른 system은 `run.sh` 상단의 두 경로와 `inputs/cpptraj.in`의 residue mask를
수정하고, residue 수에 맞춰 `anal.py` 상단의 `RESIDUE_COUNT`를 바꿉니다.

`secstruct` action에는 stride keyword가 없습니다. Frame을 건너뛰려면
`1_Preprocessing/1.3_Conversion`의 `start_frame`, `stop_frame`, `stride`로
`sampled.nc`를 만든 뒤 이 `run.sh`의 `trajectory`를
`../../1_Preprocessing/1.3_Conversion/output/sampled.nc`로 바꿉니다. 큰 stride는
짧은 secondary-structure transition을 놓칠 수 있습니다.

STRIDE program도 secondary structure assignment에 사용할 수 있습니다.
Cpptraj과 다른 hydrogen-bond 및 assignment 규칙을 사용하므로 두 program의
결과를 같은 label로 바로 합치지 말고 method 차이를 확인합니다.

Terminal이나 proline처럼 필요한 backbone amide atom이 없는 residue가 있어도
cpptraj은 정보 메시지를 남기고 나머지 계산을 계속합니다.

결과 게시, 실패 log(`output.failed/`), 동시 실행 보호(`writer_guard.py`)는
[GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

Cpptraj's DSSP implementation assigns integer secondary-structure states
(0–7: none, extended, bridge, 3-10, alpha and pi helix, turn, bend) to each
Chignolin residue and frame using Kabsch–Sander hydrogen-bond geometry.

`run.sh` reads `work/system.parm7` and `work/production.nc` from the
[Chignolin conventional-MD tutorial](../../../1_Simulation/1_MD/1.1_Soluble_Protein/README.md).
Run `./run.sh` and then `python3 anal.py` from this directory.

`python3 anal.py --save-figure figures` also saves the figure as
`figures/secondary_structure.png` (150 dpi) while displaying it. Keep that directory outside
`output/`; without the option no image file is written.

| Output | Columns | Unit |
| --- | --- | --- |
| `secondary_structure.dat` | `Frame`, state code per residue column (`GLY:1` … `GLY:10`) | 0–7 |
| `secondary_byresidue.dat` | `#Residue`, `Extended`, `Bridge`, `3-10`, `Alpha`, `Pi`, `Turn`, `Bend` | fraction 0–1 |
| `secondary_total.dat` | `Frame`, `DSSP[Extended]` … `DSSP[Bend]`: fraction of residues in each state | 0–1 |

`anal.py` displays a residue-time map and state fractions. The cpptraj total
output has no `None` column, so Python computes it as the remainder. In the
folded hairpin, strand residues are mostly `Extended` (1) and the central turn
residues `Turn` (6).

For another system, edit the two paths in `run.sh`, the residue mask in
`inputs/cpptraj.in`, and `RESIDUE_COUNT` at the top of `anal.py`.

`secstruct` has no stride keyword. To sample frames, create `sampled.nc` with
`start_frame`, `stop_frame`, and `stride` in `1_Preprocessing/1.3_Conversion`,
then set `trajectory` in this `run.sh` to
`../../1_Preprocessing/1.3_Conversion/output/sampled.nc`. A large stride can
miss short secondary-structure transitions.

STRIDE is an alternative assignment program, but its hydrogen-bond and
assignment rules differ from cpptraj DSSP; do not merge the labels directly.

Residues missing backbone amide atoms, such as termini or proline, produce an
informational cpptraj message and the rest of the calculation continues.

Result publication, failure logs (`output.failed/`) and concurrent-run
protection (`writer_guard.py`) are described in [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery).
