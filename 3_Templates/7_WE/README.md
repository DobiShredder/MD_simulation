# Weighted Ensemble template

## 한국어

WESTPA 2가 walker weight와 매 iteration resampling을 관리하고 AMBER가 각
10 ps segment를 unbiased MD로 전파합니다. Steady-state recycling을 사용하며
progress coordinate, basis state, target state와 bin boundary는 system별
config input입니다.

- [WESTPA + AMBER](7.1_WESTPA_AMBER/)

`weighted_ensemble.mode`는 `steady_state`만 지원합니다. 다른 WE mode는
이 template에 구현되어 있지 않습니다.

### 준비

| 항목 | 조건 |
| --- | --- |
| WESTPA | WESTPA 2의 `w_init`, `w_run`. 미완료 segment 처리와 `WM_PROCESS_INDEX` GPU 배정은 WESTPA 2022.15 동작 기준입니다. |
| AMBER | AmberTools `tleap`, `cpptraj`와 `pmemd.cuda`, `pmemd` 또는 `sander` |
| Python | Leaf의 `requirements.txt`: `numpy`, `parmed`, `h5py`, Python 3.11 미만에서는 `tomli` |

## English

WESTPA 2 manages walker weights and resampling at every iteration while AMBER
propagates each unbiased 10 ps segment. The template uses steady-state recycling
and exposes the progress coordinate, basis state, target state and bin
boundaries as system-specific config inputs.

- [WESTPA + AMBER](7.1_WESTPA_AMBER/)

`weighted_ensemble.mode` supports only `steady_state`; other WE modes are not
implemented in this template.

### Prerequisites

| Item | Requirement |
| --- | --- |
| WESTPA | WESTPA 2 `w_init` and `w_run`. Incomplete-segment handling and `WM_PROCESS_INDEX` GPU assignment follow WESTPA 2022.15. |
| AMBER | AmberTools `tleap` and `cpptraj`, plus `pmemd.cuda`, `pmemd` or `sander` |
| Python | The leaf `requirements.txt`: `numpy`, `parmed`, `h5py`, and `tomli` below Python 3.11 |
