# MM/GBSA

## 한국어

Single-trajectory MM/GBSA는 같은 complex frame에서 receptor와 ligand를
분리합니다. Bonded energy가 상쇄되는 장점이 있지만 unbound ensemble이 bound
conformation과 같다는 가정을 둡니다.

`run.sh`는 [T4 lysozyme–JZ4 conventional MD](../../../1_Simulation/1_MD/1.2_Protein_Ligand/README.md)의
`work/system.parm7`과 `work/production.nc`를 직접 읽습니다. 해당 simulation을
먼저 실행한 뒤 이 directory에서 계산합니다.

```bash
./run.sh
python3 anal.py
```

`python3 anal.py --save-figure figures`처럼 실행하면 running mean figure를 화면에
표시하면서 `figures/mmgbsa_running_mean.png`(150 dpi)로도 저장합니다. 저장 directory는
`output/` 밖에 둡니다. Option이 없으면 image file을 만들지 않습니다. TSV 결과는
figure 창을 열기 전에 `output/`에 기록됩니다.

`run.sh`는 `ante-MMPBSA.py`로 water와 mobile ion(`strip_mask=':WAT,Na+,Cl-'`)을
제거하고 `:JZ4`를 ligand로 분리합니다. Receptor는 T4 lysozyme residue 1–163입니다. Complex,
receptor와 ligand topology는 모두 `mbondi2` PBRadii를 사용합니다. MMPBSA.py
결과는 `final_results.dat`, `final_decomposition.dat`, `energy.csv`,
`decomposition.csv`에 기록됩니다.

`anal.py`는 energy, running mean, 5개 block과 decomposition을
`energy_summary.tsv`, `running_mean.tsv`, `block_summary.tsv`,
`decomposition_summary.tsv`로 요약하고 model별 frame 수를 `Frames: N (GB)`처럼
출력합니다. Block 수는 `anal.py` 상단의 `BLOCK_COUNT`에서
바꾸며 frame이 `max(2, BLOCK_COUNT)`보다 적으면 중단합니다.

| Output | Column | 단위 |
| --- | --- | --- |
| `final_results.dat` | MMPBSA.py 요약. `Differences (Complex - Receptor - Ligand)` block이 binding 값입니다. | kcal/mol |
| `energy.csv`, `decomposition.csv` | MMPBSA.py의 frame별 energy term과 residue decomposition | kcal/mol |
| `final_decomposition.dat` | MMPBSA.py의 residue decomposition 평균 | kcal/mol |
| `energy_summary.tsv` | `model`, `term`(`VDWAALS`, `EEL`, `EGB`, `ESURF`, `DELTA G gas`, `DELTA G solv`, `DELTA TOTAL` 등), `mean`, `standard_deviation`, `frames` | kcal/mol |
| `running_mean.tsv` | `model`, `frame`, `running_mean_delta_total` | kcal/mol |
| `block_summary.tsv` | `model`, `block`, `start_frame`, `end_frame`, `mean_delta_total` | kcal/mol |
| `decomposition_summary.tsv` | `model`, `residue`, `mean_total`, `standard_deviation`, `frames`. `mean_total` 절댓값이 큰 순서입니다. | kcal/mol |

`model`은 `GB`이고, `frame`은 `energy.csv`의 `Frame #` 값(0부터 시작)입니다.
ΔTOTAL은 complex − receptor − ligand이므로 음수이면 이 model에서 complex 쪽이
더 낮은 energy입니다. Block mean이 서로 크게 다르면 frame 수가 부족하거나
trajectory 구간에 따라 값이 변한다는 뜻입니다. Decomposition에서는 ligand
(`JZ4`)와 그 주변 residue가 상위에 나옵니다.

기본 계산은 1 ns production에서 10 ps 간격으로 저장한 100개 frame에
`igb=5`, `saltcon=0.15 M`와 LCPO nonpolar term을 적용합니다. `idecomp=2`는
per-residue contribution을 기록합니다. GB 설정은 `inputs/mmpbsa.in`, 다른
system의 경로, ligand mask, strip mask와 radius set은 `run.sh` 상단의
`simulation_dir`, `ligand_mask`, `strip_mask`, `radii_set`에서 바꿉니다.

`inputs/mmpbsa.in`의 `endframe=9999999`는 MMPBSA.py 기본값이며 trajectory의
마지막 frame까지 읽습니다. 따라서 더 긴 trajectory도 모든 frame을 계산합니다.
일부만 계산하려면 `startframe`, `endframe`, `interval`을 바꿉니다. 예를 들어
`startframe=21`은 앞의 20개 frame을 제외하고, `interval=2`는 한 frame씩 건너뜁니다.
계산 시간은 frame 수에 비례합니다.

결과 게시, 실패 log(`output.failed/`), 동시 실행 보호(`writer_guard.py`)는
[GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

Single-trajectory MM/GBSA separates receptor and ligand from the same complex
snapshots. Bonded terms cancel, but the unbound ensembles are assumed to match
the bound conformations.

`run.sh` reads `work/system.parm7` and `work/production.nc` from the
[T4 lysozyme–JZ4 conventional-MD tutorial](../../../1_Simulation/1_MD/1.2_Protein_Ligand/README.md).
Run that simulation first, then run `./run.sh` and `python3 anal.py` from this
directory.

`python3 anal.py --save-figure figures` also saves the running-mean figure as
`figures/mmgbsa_running_mean.png` (150 dpi) while displaying it. Keep that directory outside
`output/`; without the option no image file is written. TSV results are written
to `output/` before the figure window opens.

`run.sh` uses `ante-MMPBSA.py` to strip water and mobile ions
(`strip_mask=':WAT,Na+,Cl-'`) and to separate
`:JZ4` from receptor residues 1–163, with mbondi2 radii for all three
topologies. MMPBSA.py writes `final_results.dat`, `final_decomposition.dat`,
`energy.csv`, and `decomposition.csv`.

`anal.py` summarizes energies, the running mean, five blocks, and the
decomposition in `energy_summary.tsv`, `running_mean.tsv`, `block_summary.tsv`,
and `decomposition_summary.tsv`. It prints the frame count per model, e.g.
`Frames: N (GB)`. Set the block count with `BLOCK_COUNT` at the top of
`anal.py`; fewer frames than `max(2, BLOCK_COUNT)` stop the run.

| Output | Columns | Unit |
| --- | --- | --- |
| `final_results.dat` | MMPBSA.py summary; the `Differences (Complex - Receptor - Ligand)` block holds the binding values | kcal/mol |
| `energy.csv`, `decomposition.csv` | Per-frame MMPBSA.py energy terms and residue decomposition | kcal/mol |
| `final_decomposition.dat` | MMPBSA.py mean residue decomposition | kcal/mol |
| `energy_summary.tsv` | `model`, `term` (`VDWAALS`, `EEL`, `EGB`, `ESURF`, `DELTA G gas`, `DELTA G solv`, `DELTA TOTAL`, ...), `mean`, `standard_deviation`, `frames` | kcal/mol |
| `running_mean.tsv` | `model`, `frame`, `running_mean_delta_total` | kcal/mol |
| `block_summary.tsv` | `model`, `block`, `start_frame`, `end_frame`, `mean_delta_total` | kcal/mol |
| `decomposition_summary.tsv` | `model`, `residue`, `mean_total`, `standard_deviation`, `frames`, sorted by absolute `mean_total` | kcal/mol |

`model` is `GB`, and `frame` is the `Frame #` value in `energy.csv` (starting
at 0). ΔTOTAL is complex − receptor − ligand, so a negative value means the
complex has the lower energy in this model. Block means that differ strongly
indicate too few frames or drift along the trajectory. The decomposition lists
the ligand (`JZ4`) and its neighboring residues first.

The default calculation uses GB model 5 (`igb=5`), 0.15 M salt, LCPO, and
per-residue decomposition (`idecomp=2`) for 100 frames saved every 10 ps from
the 1 ns production trajectory. Edit GB settings in `inputs/mmpbsa.in`. For
another system, edit `simulation_dir`, `ligand_mask`, `strip_mask`, and
`radii_set` at the top of `run.sh`.

`endframe=9999999` in `inputs/mmpbsa.in` is the MMPBSA.py default and reads to
the last frame, so longer trajectories are analysed in full. To restrict the
range, edit `startframe`, `endframe`, and `interval`; for example,
`startframe=21` skips the first 20 frames and `interval=2` uses every second
frame. Run time scales with the frame count.

Result publication, failure logs (`output.failed/`) and concurrent-run
protection (`writer_guard.py`) are described in [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery).
