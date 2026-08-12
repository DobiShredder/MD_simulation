# KcsA AMBER simulation / KcsA AMBER 시뮬레이션

## 한국어

2단계의 `work/system.parm7`과 `work/system.rst7`을 기본 input으로 사용합니다.
다른 파일은 `TOPOLOGY`와 `COORDINATES`로 지정합니다.

### 파일 역할

| 파일 | 역할 |
| --- | --- |
| `run.sh` | Input preflight와 두 minimization, heating, equilibration, production을 순서대로 실행합니다. |
| `inputs/min-environment.in` | Protein과 filter K+ heavy atom을 고정하고 lipid·water·bulk ion을 minimize합니다. |
| `inputs/min-all.in` | 전체 system restraint를 제거한 minimization입니다. |
| `inputs/heat.in` | 20→310 K heating을 진행하고 velocity를 생성합니다. |
| `inputs/equil.in` | 약한 protein/filter restraint를 둔 100 ps anisotropic NPT equilibration입니다. |
| `inputs/production.in` | Restraint 없는 1 ns anisotropic NPT production입니다. |

~~~bash
cd 1_Simulation/1_MD/1.3_Membrane_Protein/3_Simulation
./run.sh --dry-run
./run.sh
~~~

Protein과 filter ion을 minimization, heating을 진행하고 나서
100 ps equilibration과 1 ns production을 실행합니다.
기본값은 310 K와 anisotropic pressure coupling입니다.
기본 engine은 `pmemd.cuda`입니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `ntp=2`, `barostat=2` | Monte Carlo barostat로 x·y·z box dimension을 anisotropic하게 조절합니다. |
| `temp0=310`, `ntt=3`, `gamma_ln=1.0` | 310 K Langevin thermostat 설정입니다. |
| `restraintmask=':1-415 & !@H='` | KcsA 408 residues와 filter K+ 7개 heavy atom을 초기 stage에서 restraint합니다. Topology residue 순서가 바뀌면 수정합니다. |
| `ntc=2`, `ntf=2`, `dt=0.002` | 수소 bond SHAKE와 2 fs timestep을 사용합니다. |
| `ntmin=2`, `dx0=0.0001` | 초기 protein side-chain contact를 완화하도록 두 minimization에서 작은 step의 steepest descent만 사용합니다. |
| `TOPOLOGY`, `COORDINATES`, `WORK_DIR` | 다른 build 또는 independent run의 input/output 경로를 지정합니다. |

1 ns는 어디까지나 튜토리얼을 위한 시간일 뿐, 대부분의 경우 훨씬 긴 계산을 수행해야 합니다.

## English

The stage-2 topology and restart are the default inputs. Set `TOPOLOGY` and
`COORDINATES` only to use different files. Protein and filter ions are
restrained during minimization and heating, followed by 100 ps equilibration and
1 ns production at 310 K with anisotropic pressure coupling.

`run.sh` executes environment minimization, unrestrained minimization, heating,
equilibration, and production using the matching files under `inputs/`.
`ntp=2` with `barostat=2` enables anisotropic Monte Carlo pressure coupling;
`ntt=3` and `gamma_ln=1.0` define the Langevin thermostat. The initial
`:1-415 & !@H=` mask covers KcsA and seven filter ions and must be updated if
topology residue ordering changes. SHAKE permits the 2 fs timestep.
Both minimizations use steepest descent (`ntmin=2`) with `dx0=0.0001` to
relax initial side-chain contacts before dynamics.

The default engine is `pmemd.cuda`; `AMBER_ENGINE` overrides it. Before
analyzing production, check area per lipid, bilayer thickness, lipid order,
density, and box-vector stability.
