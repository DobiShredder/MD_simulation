# Weighted Ensemble template

## 한국어

`weighted_ensemble.mode`는 현재 `steady_state`만 지원합니다. 다른 WE mode는
이 template에 구현되어 있지 않습니다.

WESTPA 2가 walker weight와 매 iteration resampling을 관리하고 AMBER가 각
10 ps segment를 unbiased MD로 전파합니다. Steady-state recycling을 사용하며
progress coordinate, basis state, target state와 bin boundary는 system별
config input입니다.

## English

`weighted_ensemble.mode` currently supports only `steady_state`; other WE modes
are not implemented in this template.

WESTPA 2 manages walker weights and resampling while Amber propagates each
unbiased 10 ps segment. The template uses steady-state recycling and exposes
the progress coordinate, basis state, target state, and rectilinear bins as
system-specific config inputs.
