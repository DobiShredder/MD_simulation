# Imaging and centering / Imaging 및 centering

## 한국어

Periodic boundary condition 때문에 분리되어 보이는 molecule을 같은 primary
unit cell에 배치합니다. Chignolin residue `:1-10`을 `autoimage` anchor로
사용하며 protein center of mass와 box center의 거리를 처리 전후로 비교합니다.

`run.sh`는 [Chignolin conventional MD](../../../1_Simulation/1_MD/1.1_Soluble_Protein/README.md)의
`work/system.parm7`과 `work/production.nc`를 직접 읽고 `inputs/cpptraj.in`을
실행합니다. 아래 command는 이 directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`python3 anal.py --save-figure figures`처럼 실행하면 figure를 화면에 표시하면서
`figures/imaging.png`(150 dpi)로도 저장합니다. 저장 directory는 `output/` 밖에
둡니다. Option이 없으면 image file을 만들지 않습니다.

| Output | Column | 단위 |
| --- | --- | --- |
| `center_raw.dat` | `Frame`, imaging 전 protein center x/y/z(2–4열), vector origin(5–7열, 0) | Å |
| `center_imaged.dat` | 같은 형식, imaging 후 protein center | Å |
| `box_center.dat` | 같은 형식, box center | Å |
| `imaged.nc` | Imaging한 전체 trajectory. `system.parm7`과 함께 사용합니다. | — |

`anal.py`는 처리 전후의 protein center–box center distance를 표시합니다. Imaging
후 값은 작고 거의 일정합니다. 처리 전 값은 protein이 box center에서 멀어지면
커집니다.

다른 protein을 사용할 때는 `run.sh` 상단의 두 경로와 `inputs/cpptraj.in`의
`autoimage anchor :1-10`, 두 `vector ... center` mask를 함께 바꿉니다.

결과 게시, 실패 log(`output.failed/`), 동시 실행 보호(`writer_guard.py`)는
[GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

This example uses cpptraj `autoimage` to place molecules in a consistent
primary unit cell. Chignolin residues `:1-10` form the anchor.

`run.sh` reads `work/system.parm7` and `work/production.nc` from the
[Chignolin conventional-MD tutorial](../../../1_Simulation/1_MD/1.1_Soluble_Protein/README.md)
and runs `inputs/cpptraj.in`. Run `./run.sh` and then `python3 anal.py` from
this directory.

`python3 anal.py --save-figure figures` also saves the figure as
`figures/imaging.png` (150 dpi) while displaying it. Keep that directory outside
`output/`; without the option no image file is written.

| Output | Columns | Unit |
| --- | --- | --- |
| `center_raw.dat` | `Frame`, protein center x/y/z before imaging (columns 2–4), vector origin (columns 5–7, zero) | Å |
| `center_imaged.dat` | Same layout, protein center after imaging | Å |
| `box_center.dat` | Same layout, box center | Å |
| `imaged.nc` | Imaged full trajectory; use with `system.parm7` | — |

`anal.py` plots the protein-center-to-box-center distance before and after
imaging. After imaging the distance stays small and nearly constant; before
imaging it grows whenever the protein drifts away from the box center.

For another system, edit the two paths in `run.sh` together with the anchor and
the two `vector ... center` masks in `inputs/cpptraj.in`.

Result publication, failure logs (`output.failed/`) and concurrent-run
protection (`writer_guard.py`) are described in [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery).
