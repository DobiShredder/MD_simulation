# Umbrella-sampling PMF / US PMF

## 한국어

[`1_Simulation/2_US/`](../../../1_Simulation/2_US/README.md)의 window별
`distance.dat`으로 terminal Cα distance의 1D PMF를 계산합니다. External
WHAM executable은 사용하지 않습니다. `anal.py`가 NumPy로 binned WHAM
equation을 반복 계산합니다.

먼저 2_US production을 완료합니다. `prepare.py`는 `us/work/NNN/distance.dat`만
읽습니다. Distance restraint 하나를 기록한 AMBER DUMPAVE는 2열이며, 1열은 run
시작부터 센 MD step, 2열은 distance(Å)입니다. `continue.in`으로 만든
`distance-cont.dat`은 읽지 않으므로 continuation을 포함하려면 parser를 따로
수정합니다.

이 directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`python3 anal.py --save-figure figures`처럼 실행하면 figure를 화면에 표시하면서
`figures/wham_pmf_overlap.png`(150 dpi)로도 저장합니다. 저장 directory는 `output/` 밖에
둡니다. Option이 없으면 image file을 만들지 않습니다.

`run.sh`는 `prepare.py`를 호출해 처음 100 ps를 제외한 window별 series를
`output/series/`에, window별 요약을 `output/summary.tsv`에 만듭니다. Input 검사와
결과 경로 출력도 `prepare.py`가 처리합니다. `anal.py`는 PMF와
neighboring-window overlap을 계산하고 표시합니다.

| Output | Column | 단위 |
| --- | --- | --- |
| `output/series/window_NNN.dat` | `time_ps`, `distance_A`: discard 후 window별 series | ps, Å |
| `output/summary.tsv` | `window`, `center_A`, `amber_rk_kcal_mol_A2`, `frames`, `first_time_ps`, `last_time_ps` | Å, kcal mol⁻¹ Å⁻², ps |
| `output/pmf.tsv` | `distance_A`, `count`, `probability`, `pmf_kcal_mol`: 최솟값을 0으로 이동한 PMF, 빈 bin은 `nan` | Å, kcal/mol |
| `output/window_offsets.tsv` | `window`, `center_A`, `offset_kcal_mol`: WHAM이 수렴한 window별 relative free-energy offset | Å, kcal/mol |
| `output/overlap.tsv` | `left`, `right`, `left_center_A`, `right_center_A`, `overlap`: neighboring-window histogram overlap coefficient | Å, 0–1 |
| `output/wham_diagnostics.tsv` | `temperature_K`, `bins`, `tolerance_kcal_mol`, `iterations`, `residual_kcal_mol` | K, kcal/mol |

PMF 최솟값은 0입니다. `overlap`이 0에 가까운 window 쌍 사이의 PMF는 WHAM이
두 window를 연결할 sample이 부족하므로 신뢰하기 어렵습니다.

`prepare.py`는 step에 `PRODUCTION_TIMESTEP_PS`(기본 0.002 ps,
`us/inputs/production.in`의 `dt`)를 곱해 ps로 바꾼 뒤 `DISCARD_PS`(100 ps)를
적용합니다. `dt`, column 또는 discard 구간이 다르면 `prepare.py` 상단의 값을
수정합니다. Input과 output 경로는 같은 위치의 `WINDOWS_DIR`과 `OUTPUT_DIR`에서
설정합니다.

`anal.py`는 300 K, 3–27 Å 범위와 120 bins(0.2 Å)를 기본으로 사용합니다.
상단의 `TEMPERATURE_KELVIN`은 `us/inputs/production.in`의 `temp0`와 같아야 하며,
grid는 `PMF_MIN_ANGSTROM`, `PMF_MAX_ANGSTROM`, `PMF_BINS`로 바꿉니다.
범위는 rk=1.0 window 폭(약 0.55 Å)을 기준으로 바깥 center에서 약 5σ까지
넓혔습니다. AMBER NMR-style restraint의 bias는 `rk(r-r0)^2`이므로
`window.tsv`의 `rk`를 그대로 사용합니다. External WHAM의 `1/2 k(r-r0)^2`
convention을 위한 factor-of-two 변환은 적용하지 않습니다.

빈 bin은 PMF를 `nan`으로 기록합니다. PMF 범위 밖의 frame이 있거나 WHAM이
설정한 tolerance까지 수렴하지 않으면 계산을 중단합니다.

Overlap은 window 배치 진단이며 수렴의 증거가 아닙니다. 1 ns 결과는 bin과
discard 구간에 민감할 수 있으므로 independent run과 sampling 길이를 따로
비교합니다. Bootstrap uncertainty와 radial Jacobian correction은 포함하지
않습니다. 이 CV는 Chignolin 내부의 terminal distance이므로 결과를 절대 binding
free energy 또는 전체 folding free energy로 해석하지 않습니다.

이 directory에서는 `result_generation.py` 대신 `prepare.py`가 `output/` 교체와
`output/.generation.json` 기록을 맡습니다. Preparation을 다시 실행하면 이전
PMF도 새 series와 섞이지 않도록 함께 교체됩니다. 실패 처리와 동시 실행
보호(`writer_guard.py`)는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

Per-window `distance.dat` files from
[`1_Simulation/2_US/`](../../../1_Simulation/2_US/README.md) are converted to a
one-dimensional terminal-Cα-distance PMF. `anal.py` solves the binned WHAM
equations directly with NumPy and needs no external WHAM executable.

Complete the 2_US production first. `prepare.py` reads only
`us/work/NNN/distance.dat`. An AMBER DUMPAVE file for one distance restraint has
two columns: the MD step counted from the start of the run and the distance in
Å. The `distance-cont.dat` written by `continue.in` is ignored unless the
parser is extended.

Run `./run.sh` and then `python3 anal.py` from this directory. `run.sh` calls
`prepare.py`, which discards the first 100 ps, writes each window series to
`output/series/` and a per-window summary to `output/summary.tsv`, checks inputs,
and reports output paths. `anal.py` calculates and plots the PMF and
neighboring-window overlap.

| Output | Columns | Unit |
| --- | --- | --- |
| `output/series/window_NNN.dat` | `time_ps`, `distance_A`: per-window series after the discard | ps, Å |
| `output/summary.tsv` | `window`, `center_A`, `amber_rk_kcal_mol_A2`, `frames`, `first_time_ps`, `last_time_ps` | Å, kcal mol⁻¹ Å⁻², ps |
| `output/pmf.tsv` | `distance_A`, `count`, `probability`, `pmf_kcal_mol`: PMF shifted to a zero minimum; empty bins are `nan` | Å, kcal/mol |
| `output/window_offsets.tsv` | `window`, `center_A`, `offset_kcal_mol`: converged WHAM free-energy offset per window | Å, kcal/mol |
| `output/overlap.tsv` | `left`, `right`, `left_center_A`, `right_center_A`, `overlap`: neighboring-window histogram overlap coefficient | Å, 0–1 |
| `output/wham_diagnostics.tsv` | `temperature_K`, `bins`, `tolerance_kcal_mol`, `iterations`, `residual_kcal_mol` | K, kcal/mol |

The PMF minimum is zero. Between window pairs with `overlap` near zero, WHAM
has too few shared samples to connect the windows, so the PMF there is
unreliable.

`python3 anal.py --save-figure figures` also saves the figure as
`figures/wham_pmf_overlap.png` (150 dpi) while displaying it. Keep that directory outside
`output/`; without the option no image file is written.

`prepare.py` multiplies the step by `PRODUCTION_TIMESTEP_PS` (0.002 ps, the
`dt` in `us/inputs/production.in`) before applying `DISCARD_PS` (100 ps). Edit
these constants at the top of `prepare.py` if `dt`, the column layout, or the
discard interval changes. Set input and output paths with `WINDOWS_DIR` and
`OUTPUT_DIR` in the same file.

`anal.py` uses 300 K and a 3–27 Å grid with 120 bins (0.2 Å), about 5σ beyond
the outer centers for the rk=1.0 windows (about 0.55 Å wide).
`TEMPERATURE_KELVIN` at the top must match `temp0` in `us/inputs/production.in`;
change the grid with `PMF_MIN_ANGSTROM`, `PMF_MAX_ANGSTROM`, and `PMF_BINS`. The bias is
evaluated directly as AMBER's `rk(r-r0)^2`, so no factor-of-two conversion for
an external `1/2 k(r-r0)^2` convention is applied.

Empty bins are reported as `nan`. Samples outside the PMF range or failure to
reach the WHAM tolerance stop the calculation.

Histogram overlap diagnoses window placement but does not demonstrate
convergence. Bootstrap uncertainty and a radial Jacobian correction are outside
this example. The short terminal-distance PMF is neither an absolute binding
free energy nor a complete folding free energy.

Here `prepare.py`, not `result_generation.py`, replaces `output/` and writes
`output/.generation.json`. Rerunning the preparation also replaces the old PMF
so it never mixes with new series. Failure handling and concurrent-run
protection (`writer_guard.py`) are described in [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery).

## References / 참고 자료

- [Kumar et al., WHAM](https://doi.org/10.1002/jcc.540130812)
