# Gaussian accelerated MD / GaMD

Reference syntax: Amber 2026. GaMD is available in pmemd, not sander.

## 한국어

`igamd=3` dual boost를 사용합니다. `gamd1.in`이 conventional 통계와 boost
parameter를 만들고 `gamd2.in`은 `gamd-restart.dat`을 이어받습니다.

~~~bash
cd 1_Simulation/4_GaMD/4.1_GaMD
# wat.parm7과 wat.rst7 준비
bash run.sh
~~~

기본 input은 수백 ns입니다. Test에서는 `nstlim`, `ntcmdprep`, `ntcmd`,
`ntebprep`과 `nteb`를 함께 줄입니다. `gamd1.rst7`과 boost 통계가 production에
전달되어야 합니다. Reweighting에는 `sigma0P/D`, boost distribution,
anharmonicity와 effective sample size를 사용합니다.

## English

GaMD adds a harmonic boost to lower effective barriers. The input uses
`igamd=3` dual boost. `gamd1.in` gathers conventional statistics and initializes
the boost; `gamd2.in` uses `irest_gamd=1` and continues from `gamd-restart.dat`
and the MD restart state.

Provide `wat.parm7`/`wat.rst7` and run `run.sh` only after reducing the
production-sized defaults for a short test. Check boost distributions, sigma limits,
anharmonicity, effective sample size, restart continuity, and reweighting.
