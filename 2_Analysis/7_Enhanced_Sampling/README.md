# Enhanced-sampling analysis / Enhanced-sampling 분석

## 한국어

Bias·replica simulation의 PMF와 reweighting을 다룹니다. Replica mixing은 각
simulation folder의 `anal.py`가 진단합니다. Flux와 rate estimator는 현재
analysis tutorial에 포함하지 않습니다. 공통 trajectory processing과 구조
계산은 1–6번 category에 둡니다.

- [Umbrella sampling PMF](7.1_Umbrella_Sampling/README.md)
- [GaMD reweighting](7.2_GaMD_Reweighting/README.md)
- [GaREUS reweighting](7.3_GaREUS_Reweighting/README.md)

US 예제는 NumPy로 histogram overlap과 WHAM PMF를 계산합니다. GaMD 예제는
method별 CV와 boost log를 맞추고 2차 cumulant PMF를 계산합니다. GaREUS
예제는 MBAR와 2차 cumulant expansion을 순서대로 적용합니다.

## English

This category contains method-specific PMF and reweighting workflows. Replica
mixing is diagnosed by each simulation folder, while flux and rate estimators
are not included. Reusable trajectory processing and structural features stay
in categories 1–6.

The US example calculates histogram overlap and a NumPy WHAM PMF. The GaMD
example matches profile-specific CVs to boost logs and applies second-order
cumulant reweighting. The GaREUS example removes REUS and GaMD biases in two
separate reweighting steps.
