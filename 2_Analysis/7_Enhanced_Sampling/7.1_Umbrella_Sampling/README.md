# Umbrella-sampling PMF / US PMF

## 한국어

[`1_Simulation/2_US/`](../../../1_Simulation/2_US/README.md)의 window별
`distance.dat`으로 terminal Cα distance의 1D PMF를 계산합니다. External
WHAM executable은 사용하지 않습니다. `anal.py`가 NumPy로 binned WHAM
equation을 반복 계산합니다.

먼저 2_US production을 완료합니다. 이후 이 directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`run.sh`는 `us/work/NNN/distance.dat`에서 처음 100 ps를 제외하고
window별 series를 `output/series/`에 만듭니다. DUMPAVE의 1열을 time, 8열을
distance로 읽습니다. Column이나 discard 구간이 다르면 `prepare.py` 상단의
값을 수정합니다.

`anal.py`는 300 K, 5–25 Å 범위와 100 bins를 기본으로 사용합니다. AMBER
NMR-style restraint의 bias는 `rk(r-r0)^2`이므로 `window.tsv`의 `rk`를 그대로
사용합니다. External WHAM의 `1/2 k(r-r0)^2` convention을 위한 factor-of-two
변환은 적용하지 않습니다.

| Output | 내용 |
| --- | --- |
| `output/pmf.tsv` | Bin별 frame 수, probability와 최솟값을 0으로 이동한 PMF |
| `output/window_offsets.tsv` | WHAM에서 수렴한 window별 relative free-energy offset |
| `output/overlap.tsv` | Neighboring-window histogram overlap coefficient |
| `output/wham_diagnostics.tsv` | 온도, bin 수, iteration과 최종 residual |

빈 bin은 PMF를 `nan`으로 기록합니다. PMF 범위 밖의 frame이 있거나 WHAM이
설정한 tolerance까지 수렴하지 않으면 계산을 중단합니다. Overlap은 window
배치 진단이며 수렴의 증거가 아닙니다. 1 ns 결과는 bin과 discard 구간에
민감할 수 있으므로 independent run과 sampling 길이를 따로 비교합니다.

Bootstrap uncertainty와 radial Jacobian correction은 포함하지 않습니다.
이 CV는 Chignolin 내부의 terminal distance이므로 결과를 절대 binding free
energy 또는 전체 folding free energy로 해석하지 않습니다.

## English

Per-window `distance.dat` files from the matching 2_US simulation are converted
to a one-dimensional terminal-distance PMF. The implementation solves the
binned WHAM equations directly with NumPy and does not require an external WHAM
executable.

Run `./run.sh` to discard the first 100 ps and prepare each distance series,
then run `python3 anal.py` to calculate and plot the PMF and neighboring-window
overlap. The default grid covers 5–25 Å with 100 bins at 300 K.

The bias is evaluated directly as AMBER's `rk(r-r0)^2`. No factor-of-two
conversion for an external `1/2 k(r-r0)^2` convention is needed. Empty bins are
reported as `nan`, while samples outside the selected PMF range or failure to
reach the WHAM tolerance stop the calculation.

`pmf.tsv`, `window_offsets.tsv`, `overlap.tsv`, and `wham_diagnostics.tsv`
contain the numerical results. Histogram overlap diagnoses window placement but does not demonstrate
convergence. Bootstrap uncertainty and a radial Jacobian correction are outside
this example. The short terminal-distance PMF is neither an absolute binding
free energy nor a complete folding free energy.

## References / 참고 자료

- [Kumar et al., WHAM](https://doi.org/10.1002/jcc.540130812)
