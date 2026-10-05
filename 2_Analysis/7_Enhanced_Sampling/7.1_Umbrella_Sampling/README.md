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

Input과 output 경로는 `prepare.py`의 `WINDOWS_DIR`과 `OUTPUT_DIR`에서
설정합니다. `run.sh`는 이 script를 호출하며 input 검사와 결과 경로 출력도
`prepare.py`가 처리합니다.

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

### 결과 저장과 재실행

`prepare.py`는 모든 window의 series와 `summary.tsv`를 temporary directory에
만든 뒤 `output/`을 교체합니다. 뒤 window에서 실패해도 이전 결과를 유지합니다.
완료한 파일의 hash는 `output/.generation.json`에 기록합니다.

`anal.py`는 이 기록과 일치하는 series/summary만 읽습니다. 검증한 input을
별도 generation에 복사하고, PMF와 진단 파일이 모두 작성된 뒤 함께 반영합니다.
Preparation을 성공적으로 다시 실행하면 이전 PMF는 새 series와 섞이지 않도록
교체됩니다. 완료 기록이 없는 과거 결과는 `run.sh`로 다시 생성합니다.

게시가 중단되어 `.output.pending`이 남으면 preparation과 consumer가 중단합니다.
실행 process가 종료됐는지 확인한 뒤 marker에 적힌 previous/new directory를
보존하고 검사합니다. 여러 파일의 교체를 하나의 atomic write로 취급하지 않습니다.

공개 analysis entry는 자동으로 `writer_guard.py`를 호출해 같은 output의 동시 writer를 거부합니다. Engine 실행부터 결과 게시까지 보호하며, signal 종료 시 child가 멈춘 뒤 lock을 해제합니다. Lock을 임의로 삭제해 실행을 재개하지 않습니다.

## English

Per-window `us/work/NNN/distance.dat` files from the matching 2_US simulation
are converted to a one-dimensional terminal-distance PMF. The implementation
solves the binned WHAM equations directly with NumPy and does not require an
external WHAM executable.

Run `./run.sh` to discard the first 100 ps and prepare each distance series,
then run `python3 anal.py` to calculate and plot the PMF and neighboring-window
overlap. The default grid covers 5–25 Å with 100 bins at 300 K.

Set input and output paths with `WINDOWS_DIR` and `OUTPUT_DIR` in `prepare.py`.
`run.sh` calls this script, which also checks inputs and reports output paths.

The bias is evaluated directly as AMBER's `rk(r-r0)^2`. No factor-of-two
conversion for an external `1/2 k(r-r0)^2` convention is needed. Empty bins are
reported as `nan`, while samples outside the selected PMF range or failure to
reach the WHAM tolerance stop the calculation.

`pmf.tsv`, `window_offsets.tsv`, `overlap.tsv`, and `wham_diagnostics.tsv`
contain the numerical results. Histogram overlap diagnoses window placement but does not demonstrate
convergence. Bootstrap uncertainty and a radial Jacobian correction are outside
this example. The short terminal-distance PMF is neither an absolute binding
free energy nor a complete folding free energy.

### Result storage and reruns

`prepare.py` creates every window series and `summary.tsv` in a temporary
directory before replacing `output/`. Failure in a later window preserves the
previous results. Completed file hashes are recorded in `output/.generation.json`.

`anal.py` reads only series/summary files matching that record. It copies checked
inputs to a separate generation and publishes the PMF and diagnostics only after
all files have been written. A successful preparation rerun replaces the old PMF
along with its inputs rather than mixing it with new series. Regenerate older
results without a completion record by running `run.sh`.

If publication stops with `.output.pending` present, preparation and consumers
refuse to proceed. Check that the process has ended, then preserve and inspect
the previous/new directories listed in the marker. Multiple file replacements
are not treated as one atomic write.

## References / 참고 자료

- [Kumar et al., WHAM](https://doi.org/10.1002/jcc.540130812)

Public analysis entries automatically use `writer_guard.py` to reject concurrent writers to the same output. Protection covers engine execution through publication, and signal cleanup drains children before releasing the lock. Do not delete a lock to force a retry.
