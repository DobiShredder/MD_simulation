# Enhanced-sampling analysis / Enhanced-sampling 분석

## 한국어

Bias·replica simulation의 PMF, reweighting, replica mixing, flux와 rate를
다룹니다. 공통 trajectory processing과 구조 계산은 1–6번 category에 둡니다.

- [Umbrella sampling PMF](7.1_Umbrella_Sampling/README.md)

구현된 예제는 umbrella sampling 하나입니다. 다른 method에 적용할 때는 bias
convention, unit, equilibration 제거와 uncertainty 계산을 먼저 바꿉니다.

## English

Method-specific PMF, reweighting, replica mixing, flux, and rate calculations
are kept separate from reusable trajectory processing and structural features.

Only umbrella sampling is implemented. Adapt bias conventions, units,
equilibration removal, correlation, and uncertainty before using it elsewhere.
