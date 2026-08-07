# Well-Tempered Metadynamics / Well-Tempered MetaD

References: Amber 2026 and PLUMED 2.10
([METAD](https://www.plumed.org/doc-v2.10/user-doc/html/_m_e_t_a_d.html)).

## 한국어

두 torsion(phi/psi)에 Gaussian hill을 추가합니다. 기본값은
`BIASFACTOR=10`, `SIGMA=0.2 rad`, `HEIGHT=1.2`, `PACE=500`입니다.
`metad/plumed.dat`의 atom 5,7,9,15,17과 grid는 example 값입니다.

~~~bash
cd 1_Simulation/7_MetaD/7.1_WT-MetaD
# wat.parm7/wat.rst7 준비 및 짧은 nstlim 설정
bash run.sh
~~~

Minimization과 heating 뒤 AMBER가 `metad/plumed.dat`을 읽습니다. Output은
`metad/metad.nc`, `HILLS`와 `COLVAR`입니다. Restart에는 AMBER restart와 bias
history를 함께 사용합니다. Analysis에서는 CV diffusion, transition과
block별 free-energy 변화를 비교합니다.

## English

Gaussian hills are deposited on two torsions and tempered with BIASFACTOR=10.
Replace atom indices, CVs, SIGMA, HEIGHT, PACE, and grid bounds.
Provide wat.parm7/wat.rst7, shorten nstlim, and run run.sh.

Inspect the metadynamics trajectory, HILLS, and COLVAR. Preserve both the
PLUMED bias history and AMBER restart state when continuing a run. Check CV
diffusion, repeated transitions, hill resolution, and block convergence of
the FES.
