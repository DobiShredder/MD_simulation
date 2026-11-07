# GaREUS reweighting / GaREUS reweighting 분석

## 한국어

[`3.5_GaREUS`](../../../1_Simulation/3_REMD/3.5_GaREUS/README.md)의 terminal
Cα distance PMF를 two-step reweighting으로 계산합니다. MBAR로 REUS
restraint를 먼저 제거한 뒤, GaMD boost를 2차 cumulant expansion으로
제거합니다.

GaREUS production을 먼저 완료합니다. `prepare.py`는 state table의 모든
window에서 tutorial의 단일 production output인 `restraint.production.dat`과
`gamd.production.log`를 읽습니다. 생성 TSV의 `segment` column은 1이며,
template의 segmented output은 지원하지 않습니다.

GaREUS simulation이 최소 2개·짝수 replica만 지원하므로 analysis도 같은 조건을
검사합니다. 기본 schedule은 20개이며, preparation과 `anal.py` 모두 0개·1개·홀수
state를 기존 output 교체 전에 거부합니다.

PyMBAR 4(`pymbar>=4,<5`)가 필요합니다. 설치는
[Analysis README의 준비](../../README.md#준비)를 따릅니다.

이 directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`python3 anal.py --save-figure figures`처럼 실행하면 figure를 화면에 표시하면서
`figures/gareus_pmf.png`(150 dpi)로도 저장합니다. 저장 directory는 `output/` 밖에
둡니다. Option이 없으면 image file을 만들지 않습니다.

`run.sh`는 `prepare.py`를 호출해 각 window의 distance와 dual-boost record를
짝짓습니다. Record 수가 같지 않으면 중단합니다. Input 검사와 결과 경로 출력도
`prepare.py`가 처리합니다.

`anal.py`는 각 frame을 모든 umbrella Hamiltonian에서 평가하고, bias가 없는
sample weight를 PyMBAR로 계산합니다. 이 단계가 제거하는 것은 REUS bias뿐이며
GaMD bias는 남아 있습니다. 각 distance bin에서 MBAR weight를 사용해 boost의
평균과 분산을 구한 뒤 다음 2차 cumulant approximation을 적용합니다.

\[
\ln \langle e^{\beta\Delta U}\rangle_\xi
\simeq \beta\langle\Delta U\rangle_\xi
+\frac{\beta^2}{2}\operatorname{Var}_\xi(\Delta U)
\]

| Output | Column | 단위 |
| --- | --- | --- |
| `output/pmf.tsv` | `distance_A`, `count`, `mbar_probability`, `reweighted_probability`, `mbar_pmf_kcal_mol`(REUS bias만 제거), `reweighted_pmf_kcal_mol`(GaMD bias까지 제거), `boost_mean_kcal_mol`, `boost_variance_kcal2_mol2`, `mbar_effective_sample_size` | Å, kcal/mol, kcal²/mol² |
| `output/mbar_weights.tsv` | `window`, `frame`, `distance_A`, `boost_kcal_mol`, `mbar_weight`: window와 frame별 unbiased MBAR weight | Å, kcal/mol |
| `output/overlap_matrix.tsv` | `window`와 state별 column: sampled umbrella state 사이의 MBAR overlap matrix | 0–1 |
| `output/mbar_diagnostics.tsv` | `pymbar_version`, `frames`, `weight_sum`, `effective_sample_size`, `maximum_weight` | — |
| `output/summary.tsv`(`prepare.py`) | `window`, `center_A`, `amber_rk_kcal_mol_A2`, `frames` | Å, kcal·mol⁻¹·Å⁻² |
| `output/series/window_NNN.tsv`(`prepare.py`) | `frame`, `segment`, `distance_A`, `boost_kcal_mol` | Å, kcal/mol |

`weight_sum`은 1입니다. Overlap matrix에서 인접 state 사이 값이 0에 가까우면
MBAR가 그 state들을 연결할 sample이 부족합니다. 빈 bin의 PMF는 `nan`입니다.

`anal.py` 상단의 `TEMPERATURE_KELVIN`(300 K)은 GaREUS `inputs/production.in`의
`temp0`와 같아야 합니다. PMF grid는 `PMF_MIN_ANGSTROM`–`PMF_MAX_ANGSTROM`
(3–28 Å)과 `BIN_WIDTH_ANGSTROM`(0.2 Å)으로 정하며, 범위 밖 frame이 있으면
계산을 중단합니다.

Input과 output 경로는 `prepare.py`의 `SIMULATION_WORK`와 `OUTPUT_DIR`에서
설정합니다. `prepare.py`의 `RESTRAINT_FORCE_KCAL_MOL_A2`(AMBER rk, 1.0)는 GaREUS
`make_restraints.py`의 값과 같아야 합니다. 다르면 error 없이 MBAR 결과가 틀립니다. AMBER GaMD log 형식이 달라지면 `prepare.py`의 `read_boost()`에서
component column을 확인합니다.

이 계산은 모든 replica에 같은 GaMD parameter가 적용되고 umbrella restraint만
다르다는 조건을 사용합니다. Simulation README의 shared `gamd-restart.dat`
workflow를 바꾸면 MBAR reduced potential도 함께 수정해야 합니다.

1 ns 결과와 2차 cumulant approximation은 수렴된 정량 free energy를
보장하지 않습니다. Overlap, effective sample size, boost distribution의
Gaussian 성질, bin width와 independent run을 함께 확인합니다. Bootstrap,
2D PMF와 kinetic reweighting은 포함하지 않습니다.

이 directory에서는 `result_generation.py` 대신 `prepare.py`가 `output/` 교체와
`output/.generation.json` 기록을 맡습니다. Preparation을 다시 실행하면 이전
PMF도 새 series와 섞이지 않도록 함께 교체됩니다. 실패 처리와 동시 실행
보호(`writer_guard.py`)는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

This example calculates a one-dimensional terminal-Cα-distance PMF from the
[GaREUS simulation](../../../1_Simulation/3_REMD/3.5_GaREUS/README.md) by
two-step reweighting: MBAR removes the REUS umbrella restraints, then a
second-order cumulant expansion removes the GaMD boost.

Complete the GaREUS production first. `prepare.py` reads the tutorial's single
production outputs, `restraint.production.dat` and `gamd.production.log`, in
each window of the state table. The output TSV retains `segment = 1`;
segmented template outputs are not supported.

The GaREUS simulation supports only even replica counts of at least two, so the
analysis checks the same condition. The default has 20 states; preparation and
`anal.py` reject zero, one, or odd states before replacing outputs.

PyMBAR 4 (`pymbar>=4,<5`) is required; install it as described in the
analysis [Preparation](../../README.md#preparation) section.

Run `./run.sh` to pair distance and dual-boost records for every window, then
run `python3 anal.py`. Mismatched record counts stop the preparation.

`python3 anal.py --save-figure figures` also saves the figure as
`figures/gareus_pmf.png` (150 dpi) while displaying it. Keep that directory outside
`output/`; without the option no image file is written.

`anal.py` evaluates each frame in every umbrella Hamiltonian and uses PyMBAR to
assign unbiased sample weights. This removes only the REUS bias. Weighted,
bin-local boost means and variances are then used for the second-order
cumulant approximation, ln⟨e^{βΔU}⟩ ≈ β⟨ΔU⟩ + (β²/2) Var(ΔU), which removes
the GaMD bias.

| Output | Columns | Unit |
| --- | --- | --- |
| `output/pmf.tsv` | `distance_A`, `count`, `mbar_probability`, `reweighted_probability`, `mbar_pmf_kcal_mol` (REUS bias removed), `reweighted_pmf_kcal_mol` (GaMD bias also removed), `boost_mean_kcal_mol`, `boost_variance_kcal2_mol2`, `mbar_effective_sample_size` | Å, kcal/mol, kcal²/mol² |
| `output/mbar_weights.tsv` | `window`, `frame`, `distance_A`, `boost_kcal_mol`, `mbar_weight`: unbiased MBAR weight per window and frame | Å, kcal/mol |
| `output/overlap_matrix.tsv` | `window` and one column per state: MBAR overlap matrix between sampled umbrella states | 0–1 |
| `output/mbar_diagnostics.tsv` | `pymbar_version`, `frames`, `weight_sum`, `effective_sample_size`, `maximum_weight` | — |
| `output/summary.tsv` (`prepare.py`) | `window`, `center_A`, `amber_rk_kcal_mol_A2`, `frames` | Å, kcal·mol⁻¹·Å⁻² |
| `output/series/window_NNN.tsv` (`prepare.py`) | `frame`, `segment`, `distance_A`, `boost_kcal_mol` | Å, kcal/mol |

`weight_sum` is 1. Near-zero overlap between neighboring states means MBAR has
too few samples to connect them. Empty bins have `nan` PMFs.

`TEMPERATURE_KELVIN` (300 K) at the top of `anal.py` must match `temp0` in the
GaREUS `inputs/production.in`. The PMF grid spans `PMF_MIN_ANGSTROM` to
`PMF_MAX_ANGSTROM` (3–28 Å) with `BIN_WIDTH_ANGSTROM` (0.2 Å); frames outside
it stop the calculation.

Set input and output paths with `SIMULATION_WORK` and `OUTPUT_DIR` in
`prepare.py`. `RESTRAINT_FORCE_KCAL_MOL_A2` in `prepare.py` (AMBER rk, 1.0) must
match the GaREUS `make_restraints.py` value; a mismatch gives wrong MBAR results
without an error. If the AMBER GaMD log format changes, check the component columns
in `read_boost()` in `prepare.py`.

The reduced-potential construction assumes that all replicas share the same
GaMD parameters and differ only in their umbrella restraints. Changing the
shared `gamd-restart.dat` workflow in the simulation README requires changing
the MBAR reduced potential too.

The 1 ns result and the cumulant approximation do not guarantee a converged
quantitative free energy. Check overlap, effective sample size, Gaussianity of
the boost distribution, bin width, and independent runs together. Bootstrap
uncertainty, two-dimensional PMFs, and kinetic reweighting are not included.

Here `prepare.py`, not `result_generation.py`, replaces `output/` and writes
`output/.generation.json`. Rerunning the preparation also replaces the old PMF
so it never mixes with new series. Failure handling and concurrent-run
protection (`writer_guard.py`) are described in [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery).

## References / 참고 자료

- [Oshima et al., GaREUS](https://doi.org/10.1021/acs.jctc.9b00761)
- [GENESIS GaREUS tutorial](https://mdgenesis.org/tutorials/genesis_tutorial_12.5_2022/)
- [PyMBAR documentation](https://pymbar.readthedocs.io/)
