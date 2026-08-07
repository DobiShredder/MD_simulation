# KcsA AMBER simulation / KcsA AMBER 시뮬레이션

## 한국어

2단계의 `work/system.parm7`과 `work/system.rst7`을 기본 input으로
사용합니다. 다른 파일은 `TOPOLOGY`와 `COORDINATES`로 지정합니다.

~~~bash
cd 1_Simulation/1_MD/1.3_Membrane_Protein/3_Simulation
./run.sh --dry-run
./run.sh
~~~

Protein과 filter ion을 restraint한 minimization·heating 뒤 1 ns
equilibration과 10 ns production을 실행합니다. 기본값은 310 K와 anisotropic
pressure coupling입니다. 기본 engine은 `pmemd.cuda`입니다.

1 ns로 mixed membrane이 안정화되었다고 가정하지 않습니다. Area per lipid,
bilayer thickness, lipid order, density와 box vector를 production 분석 전에
확인합니다.

## English

The stage-2 topology and restart are the default inputs. Set `TOPOLOGY` and
`COORDINATES` only to use different files. Protein and filter ions are
restrained during minimization and heating, followed by 1 ns equilibration and
10 ns production at 310 K with anisotropic pressure coupling.

The default engine is `pmemd.cuda`; `AMBER_ENGINE` overrides it. Before
analyzing production, check area per lipid, bilayer thickness, lipid order,
density, and box-vector stability.
