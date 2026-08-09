# Enhanced-sampling analysis / Enhanced-sampling 분석

## 한국어

Bias·replica simulation의 PMF, reweighting, replica mixing, flux와 rate를
다룹니다. 공통 trajectory processing과 구조 계산은 1–6번 category에 둡니다.

- [Umbrella sampling PMF](7.1_Umbrella_Sampling/README.md)
- [GaMD reweighting](7.2_GaMD_Reweighting/README.md)

US 예제는 histogram overlap과 WHAM PMF를 계산합니다. GaMD 예제는 method별
CV와 boost log를 맞추고 2차 cumulant PMF를 계산합니다.

## English

Method-specific PMF, reweighting, replica mixing, flux, and rate calculations
are kept separate from reusable trajectory processing and structural features.

The US example calculates histogram overlap and a WHAM PMF. The GaMD example
matches profile-specific CVs to boost logs and applies second-order cumulant
reweighting.
