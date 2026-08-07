# Umbrella-sampling PMF / US PMF

## 한국어

[`1_Simulation/2_US/`](../../../1_Simulation/2_US/README.md)의 window별
`distance.dat`으로 1차원 PMF와 neighboring histogram overlap을 계산합니다.
결과는 `output/`에 저장하며 simulation output은 수정하지 않습니다.

```bash
cd 2_Analysis/7_Enhanced_Sampling/7.1_Umbrella_Sampling
./run.sh --dry-run
./run.sh
```

기본 input은 `../../../1_Simulation/2_US/us/work/windows`입니다.
`prepare.py`는 `distance.dat`의 1열을 time, 8열을 restrained distance로
읽고 처음 1,000 ps를 제거합니다. Amber output의 column이 다르면
`DISTANCE_COLUMN`을 바꿉니다.

WHAM metadata의 harmonic coefficient는 AMBER NMR-style restraint의
`rk(r-r0)^2`를 `2*rm2`로 변환한 값입니다. 다른 restraint 또는 WHAM
convention을 사용할 때는 이 변환을 수정합니다.

`overlap.py`는 neighboring histogram의 overlap coefficient를 0–1 범위로
계산합니다. 하나의 cutoff로 수렴을 판정하지 않습니다. Discard 구간, bin 수,
window 배치, 독립 반복과 bootstrap 결과를 함께 비교합니다.

Estimator는 PATH 또는 `WHAM_BIN`의 Grossfield-style `wham`입니다.
`BOOTSTRAP_TRIALS`가 0보다 크면 Monte Carlo bootstrap argument를 전달합니다.
다른 WHAM CLI는 `run.sh`의 호출부를 수정합니다.

## English

Per-window `distance.dat` files from the matching simulation are used for a
one-dimensional WHAM PMF and neighboring-histogram overlap. Processed series,
metadata, overlap tables, and the PMF are written under `output/`; simulation
output is left unchanged.

The default input is the simulation `us/work/windows` directory. `prepare.py`
reads each center and AMBER `rk2` from `window.tsv`, treats DUMPAVE column 1 as
time and column 8 as the restrained distance, and discards the first 1,000 ps.
Check the columns in the Amber 26 output and change `DISTANCE_COLUMN` when
needed.

The metadata converts AMBER's `rk(r-r0)^2` coefficient to the `1/2 k(r-r0)^2`
convention expected by the selected WHAM executable using `k=2*rm2`. Recheck
this conversion whenever either convention changes. Histogram overlap is a
diagnostic, not a convergence proof. Test discard length, bins, window
placement, independent repeats, and bootstrap uncertainty.

`run.sh` expects a Grossfield-style `wham` executable through PATH or
`WHAM_BIN`. Positive `BOOTSTRAP_TRIALS` are passed using that implementation's
Monte Carlo bootstrap arguments; adapt the command for a different WHAM CLI.
