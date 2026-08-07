# OPES Metadynamics / OPES_METAD

References: Amber 2026 and PLUMED 2.10
([OPES_METAD](https://www.plumed.org/doc-v2.10/user-doc/html/_o_p_e_s__m_e_t_a_d.html)).

## 한국어

OPES_METAD는 CV의 unbiased distribution을 추정하면서 target distribution을
sampling합니다. 기본 CV는 phi/psi torsion이며 `PACE=500`, `BARRIER=50`,
`SIGMA=0.15`를 사용합니다. `BARRIER`는 탐색할 free-energy 범위에 맞춥니다.

~~~bash
cd 1_Simulation/7_MetaD/7.3_OPES_METAD
# opes module이 활성화된 PLUMED–AMBER와 wat.parm7/wat.rst7 준비
bash run.sh
~~~

Output은 `opes.log`/`KERNELS`, `COLVAR`와 `opes/opes.nc`입니다. Restart에는
`STATE_WFILE`/`STATE_RFILE`과 AMBER restart를 함께 사용합니다. Analysis에서는
sampled range, effective sample size와 block별 reweighted FES를 비교합니다.
출력 `c(t)`는 reweighting weight가 아닙니다.

## English

OPES_METAD estimates the unbiased CV distribution on the fly and samples a
target distribution. The input biases phi/psi with PACE=500, BARRIER=50, and
SIGMA=0.15. Choose BARRIER near the highest barrier to overcome and adapt all
atom indices and CV parameters.

Use an OPES-enabled PLUMED build, provide AMBER inputs, and run a short run.sh
test. Preserve exact PLUMED state with STATE_WFILE/STATE_RFILE when restarting.
Check CV degeneracy, sampled range, effective sample size, and block convergence;
do not use the printed c(t) as a reweighting weight.
