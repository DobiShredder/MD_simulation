# KcsA AMBER simulation / KcsA AMBER 시뮬레이션

## 한국어

2단계의 `work/system.parm7`과 `work/system.rst7`을 기본 input으로
사용합니다. 다른 파일은 `TOPOLOGY`와 `COORDINATES`로 지정합니다.

### 파일 역할

| 파일 | 역할 |
| --- | --- |
| `run.sh` | Input preflight와 두 minimization, heating, equilibration, production을 순서대로 실행합니다. |
| `inputs/min-environment.in` | Protein과 filter K+ heavy atom을 고정하고 lipid·water·bulk ion을 완화합니다. |
| `inputs/min-all.in` | 전체 system restraint를 제거한 minimization입니다. |
| `inputs/heat.in` | 20→310 K velocity 생성과 restrained NVT heating입니다. |
| `inputs/equil.in` | 약한 protein/filter restraint를 둔 1 ns anisotropic NPT equilibration입니다. |
| `inputs/production.in` | Restraint 없는 10 ns anisotropic NPT production입니다. |

~~~bash
cd 1_Simulation/1_MD/1.3_Membrane_Protein/3_Simulation
./run.sh --dry-run
./run.sh
~~~

Protein과 filter ion을 restraint한 minimization·heating 뒤 1 ns
equilibration과 10 ns production을 실행합니다. 기본값은 310 K와 anisotropic
pressure coupling입니다. 기본 engine은 `pmemd.cuda`입니다.

### 주요 option

| Option | 의미 |
| --- | --- |
| `ntp=2`, `barostat=2` | Monte Carlo barostat로 x·y·z box dimension을 anisotropic하게 조절합니다. |
| `temp0=310`, `ntt=3`, `gamma_ln=1.0` | 310 K Langevin thermostat 설정입니다. |
| `restraintmask=':1-419 & !@H='` | KcsA 412 residues와 filter K+ 7개 heavy atom을 초기 stage에서 restraint합니다. Topology residue 순서가 바뀌면 수정합니다. |
| `ntc=2`, `ntf=2`, `dt=0.002` | 수소 bond SHAKE와 2 fs timestep을 사용합니다. |
| `ntmin=2`, `dx0=0.0001` | PACKMOL 좌표의 큰 초기 force를 완화하도록 두 minimization에서 작은 step의 steepest descent만 사용합니다. |
| `TOPOLOGY`, `COORDINATES`, `WORK_DIR` | 다른 build 또는 independent run의 input/output 경로를 지정합니다. |

1 ns로 mixed membrane이 안정화되었다고 가정하지 않습니다. Area per lipid,
bilayer thickness, lipid order, density와 box vector를 production 분석 전에
확인합니다.

## English

The stage-2 topology and restart are the default inputs. Set `TOPOLOGY` and
`COORDINATES` only to use different files. Protein and filter ions are
restrained during minimization and heating, followed by 1 ns equilibration and
10 ns production at 310 K with anisotropic pressure coupling.

`run.sh` executes environment minimization, unrestrained minimization, heating,
equilibration, and production using the matching files under `inputs/`.
`ntp=2` with `barostat=2` enables anisotropic Monte Carlo pressure coupling;
`ntt=3` and `gamma_ln=1.0` define the Langevin thermostat. The initial
`:1-419 & !@H=` mask covers KcsA and seven filter ions and must be updated if
topology residue ordering changes. SHAKE permits the 2 fs timestep.
Both minimizations use steepest descent (`ntmin=2`) with `dx0=0.0001` to
relax large initial forces in packed coordinates before dynamics.

The default engine is `pmemd.cuda`; `AMBER_ENGINE` overrides it. Before
analyzing production, check area per lipid, bilayer thickness, lipid order,
density, and box-vector stability.
