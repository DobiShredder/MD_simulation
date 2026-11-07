# Alignment and stripping / 정렬 및 stripping

## 한국어

Imaging한 trajectory를 첫 frame의 backbone에 least-squares fitting하고 solvent와
ion을 제거합니다. Translation과 rotation을 제거한 RMSD는 내부 구조 변화에
집중할 때 사용합니다.

`run.sh`는 [Chignolin conventional MD](../../../1_Simulation/1_MD/1.1_Soluble_Protein/README.md)의
`work/system.parm7`과 `work/production.nc`를 직접 읽습니다. 아래 command는 이
directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`python3 anal.py --save-figure figures`처럼 실행하면 figure를 화면에 표시하면서
`figures/alignment.png`(150 dpi)로도 저장합니다. 저장 directory는 `output/` 밖에
둡니다. Option이 없으면 image file을 만들지 않습니다.

| Output | Column | 단위 |
| --- | --- | --- |
| `rmsd_before.dat` | `Frame`, `BeforeFit`: fitting 없이 첫 frame과 비교한 backbone RMSD | Å |
| `rmsd_after.dat` | `Frame`, `AfterFit`: `:1-10@CA,C,N` fitting 뒤 RMSD | Å |
| `aligned.nc` | Fitting하고 water와 ion을 제거한 trajectory | — |
| `stripped.parm7` | `aligned.nc`와 같은 atom 수와 순서의 topology | — |
| `average.pdb` | Fitting한 Chignolin 평균 구조 | — |

`anal.py`는 두 RMSD를 비교합니다. Least-squares fitting은 translation과
rotation에 대한 RMSD 최솟값이므로 `AfterFit`은 모든 frame에서 `BeforeFit`보다
크지 않고, 첫 frame은 둘 다 0입니다.

다른 system은 `run.sh` 상단의 `topology`와 `trajectory`, `inputs/cpptraj.in`의
fit mask를 수정합니다. `strip :WAT,Na+,Cl-`는 이 example의 solvent와 ion 이름에
맞춘 mask이므로 다른 water model이나 ion residue name을 사용하면 이 mask도
바꿉니다.

`aligned.nc`와 `stripped.parm7`은 atom 수와 순서가 같으므로 함께 사용합니다.

결과 게시, 실패 log(`output.failed/`), 동시 실행 보호(`writer_guard.py`)는
[GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

The trajectory is imaged, fitted to the first-frame backbone, and stripped of
water and ions. RMSD without translation and rotation focuses on internal
structural change.

`run.sh` reads `work/system.parm7` and `work/production.nc` from the
[Chignolin conventional-MD tutorial](../../../1_Simulation/1_MD/1.1_Soluble_Protein/README.md).
Run `./run.sh` and then `python3 anal.py` from this directory.

`python3 anal.py --save-figure figures` also saves the figure as
`figures/alignment.png` (150 dpi) while displaying it. Keep that directory outside
`output/`; without the option no image file is written.

| Output | Columns | Unit |
| --- | --- | --- |
| `rmsd_before.dat` | `Frame`, `BeforeFit`: backbone RMSD to the first frame without fitting | Å |
| `rmsd_after.dat` | `Frame`, `AfterFit`: RMSD after fitting on `:1-10@CA,C,N` | Å |
| `aligned.nc` | Fitted trajectory without water and ions | — |
| `stripped.parm7` | Topology with the same atom count and order as `aligned.nc` | — |
| `average.pdb` | Average structure of the fitted Chignolin | — |

`anal.py` compares the two RMSDs. Least-squares fitting minimizes RMSD over
translation and rotation, so `AfterFit` never exceeds `BeforeFit`, and both are
zero for the first frame.

For another system, edit the two paths in `run.sh` and the fit mask in
`inputs/cpptraj.in`. `strip :WAT,Na+,Cl-` matches this example's solvent and
ion names; change it for other water models or ion residue names.

Use `stripped.parm7` with `aligned.nc`; they share atom count and order.

Result publication, failure logs (`output.failed/`) and concurrent-run
protection (`writer_guard.py`) are described in [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery).
