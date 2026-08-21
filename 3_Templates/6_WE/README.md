# Weighted Ensemble template

## 한국어

WESTPA 2가 walker weight와 매 iteration resampling을 관리하고 AMBER가 각
10 ps segment를 unbiased MD로 전파합니다. Steady-state recycling을 사용하며
progress coordinate, basis state, target state와 bin boundary는 system별
config input입니다.

## English

WESTPA 2 manages walker weights and resampling while Amber propagates each
unbiased 10 ps segment. The template uses steady-state recycling and exposes
the progress coordinate, basis state, target state, and rectilinear bins as
system-specific config inputs.
