# GaREUS reweighting / GaREUS reweighting 분석

## 한국어

[`3.5_GaREUS`](../../../1_Simulation/3_REMD/3.5_GaREUS/README.md)의 terminal
Cα distance PMF를 two-step reweighting으로 계산합니다. MBAR로 REUS
restraint를 먼저 제거한 뒤, GaMD boost를 2차 cumulant expansion으로
제거합니다.

GaREUS production을 완료한 다음 이 directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

PyMBAR 4가 필요합니다.

```bash
conda activate ambertools26
conda install -c conda-forge "pymbar>=4,<5"
```

`run.sh`는 20개 window의 `restraint.production.NNN.dat`과
`gamd.production.NNN.log`를 읽습니다. 각 segment에서 distance와 dual-boost
record 수가 같지 않으면 중단합니다. AMBER GaMD log 형식이 달라지면
`prepare.py`의 `read_boost()`에서 component column을 확인합니다.

`anal.py`는 각 frame을 모든 umbrella Hamiltonian에서 평가하고, bias가 없는
sample weight를 PyMBAR로 계산합니다. 이 단계가 제거하는 것은 REUS bias뿐이며
GaMD bias는 남아 있습니다. 각 distance bin에서 MBAR weight를 사용해 boost의
평균과 분산을 구한 뒤 다음 2차 cumulant approximation을 적용합니다.

\[
\ln \langle e^{\beta\Delta U}\rangle_\xi
\simeq \beta\langle\Delta U\rangle_\xi
+\frac{\beta^2}{2}\operatorname{Var}_\xi(\Delta U)
\]

| Output | 내용 |
| --- | --- |
| `output/pmf.tsv` | REUS bias만 제거한 PMF와 GaMD bias까지 제거한 1D PMF |
| `output/mbar_weights.tsv` | Window와 frame별 unbiased MBAR weight |
| `output/overlap_matrix.tsv` | Sampled umbrella state 사이의 MBAR overlap matrix |
| `output/mbar_diagnostics.tsv` | PyMBAR version, weight normalization과 effective sample size |

이 계산은 모든 replica에 같은 GaMD parameter가 적용되고 umbrella restraint만
다르다는 조건을 사용합니다. Simulation README의 shared
`gamd-restart.dat` workflow를 바꾸면 MBAR reduced potential도 함께 수정해야
합니다.

1 ns 결과와 2차 cumulant approximation은 수렴된 정량 free energy를
보장하지 않습니다. Overlap, effective sample size, boost distribution의
Gaussian 성질, bin width와 independent run을 함께 확인합니다. Bootstrap,
2D PMF와 kinetic reweighting은 포함하지 않습니다.

## English

This example calculates a one-dimensional terminal-Cα-distance PMF from the
matching GaREUS simulation. PyMBAR first assigns snapshot probabilities after
removing the REUS umbrella restraints. Weighted, bin-local boost means and
variances are then used for a second-order cumulant approximation that removes
the GaMD bias.

Run `./run.sh` to pair distance and dual-boost records for all 20 windows, then
run `python3 anal.py`. The outputs include the PMF before and after GaMD
reweighting, per-frame MBAR weights, the state-overlap matrix, and weight
diagnostics.

The reduced-potential construction assumes that all replicas share the same
GaMD parameters and differ only in their umbrella restraints. The 1 ns result
is a workflow exercise rather than a converged quantitative free energy.
Bootstrap uncertainty, two-dimensional PMFs, and kinetic reweighting are not
included.

## References / 참고 자료

- [Oshima et al., GaREUS](https://doi.org/10.1021/acs.jctc.9b00761)
- [GENESIS GaREUS tutorial](https://mdgenesis.org/tutorials/genesis_tutorial_12.5_2022/)
- [PyMBAR documentation](https://pymbar.readthedocs.io/)
