# RMSD, RMSF, and Rg

## 한국어

Chignolin의 backbone RMSD, residue별 RMSF와 radius of gyration(Rg)을 한 번에
계산합니다. RMSD는 첫 frame과 average structure를 각각 reference로 사용합니다.
RMSF는 average structure에 fitting한 좌표에서 계산합니다.

`run.sh`는 [Chignolin conventional MD](../../../1_Simulation/1_MD/1.1_Soluble_Protein/README.md)의
`work/system.parm7`과 `work/production.nc`를 직접 읽습니다. 아래 command는 이
directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`python3 anal.py --save-figure figures`처럼 실행하면 figure를 화면에 표시하면서
`figures/rmsd_rmsf_rg.png`(150 dpi)로도 저장합니다. 저장 directory는 `output/` 밖에
둡니다. Option이 없으면 image file을 만들지 않습니다.

`run.sh`는 cpptraj의 두 `run` pass를 사용합니다. 첫 pass는 `rmsd_first.dat`과
`average.pdb`를, 두 번째 pass는 나머지 파일을 만듭니다.

| Output | Column | 단위 |
| --- | --- | --- |
| `rmsd_first.dat` | `Frame`, `ToFirst`: 첫 frame 기준 backbone RMSD | Å |
| `rmsd_average.dat` | `Frame`, `ToAverage`: average structure 기준 backbone RMSD | Å |
| `rmsf_byres.dat` | `Res`, `RMSF`: residue별 Cα RMSF | Å |
| `rg.dat` | `Frame`, `Rg`: mass-weighted heavy-atom radius of gyration | Å |
| `average.pdb` | 첫 pass에서 만든 average structure | — |

`anal.py`는 세 지표를 표시합니다. `ToFirst`는 첫 frame에서 0이고, RMSF는 보통
terminal residue(1, 10)에서 가장 큽니다.

다른 system은 `run.sh` 상단의 두 경로와 `inputs/cpptraj.in`의 mask를
수정합니다. RMSD와 fitting mask는 backbone `:1-10@CA,C,N`이고, RMSF는
residue별 Cα `:1-10@CA`에서 계산합니다. Rg는 protein heavy atom에 질량을
적용합니다.

Reference와 mask가 바뀌면 값의 의미도 바뀌므로 서로 다른 계산을 비교할 때 같은
definition을 사용합니다. 짧은 trajectory의 안정된 RMSD만으로 구조 ensemble의
수렴을 판단하지 않습니다.

결과 게시, 실패 log(`output.failed/`), 동시 실행 보호(`writer_guard.py`)는
[GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

This example calculates backbone RMSD against the first frame and the average
structure, per-residue Cα RMSF after fitting to the average structure, and
mass-weighted heavy-atom Rg.

`run.sh` reads `work/system.parm7` and `work/production.nc` from the
[Chignolin conventional-MD tutorial](../../../1_Simulation/1_MD/1.1_Soluble_Protein/README.md).
Run `./run.sh` and then `python3 anal.py` from this directory.

`python3 anal.py --save-figure figures` also saves the figure as
`figures/rmsd_rmsf_rg.png` (150 dpi) while displaying it. Keep that directory outside
`output/`; without the option no image file is written.

The first cpptraj pass writes `rmsd_first.dat` and `average.pdb`; the second
writes the remaining files.

| Output | Columns | Unit |
| --- | --- | --- |
| `rmsd_first.dat` | `Frame`, `ToFirst`: backbone RMSD to the first frame | Å |
| `rmsd_average.dat` | `Frame`, `ToAverage`: backbone RMSD to the average structure | Å |
| `rmsf_byres.dat` | `Res`, `RMSF`: per-residue Cα RMSF | Å |
| `rg.dat` | `Frame`, `Rg`: mass-weighted heavy-atom radius of gyration | Å |
| `average.pdb` | Average structure from the first pass | — |

`anal.py` displays all three observables. `ToFirst` is zero for the first
frame, and RMSF is usually largest at the terminal residues (1 and 10).

For another system, edit the two paths in `run.sh` and the masks in
`inputs/cpptraj.in`. RMSD and fitting use backbone `:1-10@CA,C,N`, RMSF uses
`:1-10@CA` per residue, and Rg uses mass-weighted protein heavy atoms.

Keep reference and mask definitions identical when comparing calculations. A
stable RMSD from a short trajectory does not show ensemble convergence.

Result publication, failure logs (`output.failed/`) and concurrent-run
protection (`writer_guard.py`) are described in [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery).
