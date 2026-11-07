# Free-energy templates

## 한국어

RBFE와 ABFE는 AMBER alchemical window를 생성하고 `ifmbar` energy matrix를
기록합니다. 각 window는 20 ns production을 기본으로 합니다.

Precharged ligand MOL2와 matching frcmod를 input으로 사용하며 charge fitting은
template가 수행하지 않습니다. RBFE는 두 ligand mask와 atom mapping을, ABFE는
ligand mask와 여섯 restraint anchor를 config에서 받습니다.

### 필요한 program

| Program | 사용하는 script |
| --- | --- |
| Amber 26 `pmemd.cuda` | `run.sh`. `pmemd.cuda` 외 executable은 거부합니다. |
| AmberTools `tleap` | `build.sh` |
| Python package `numpy`, `parmed`, `tomli`(Python 3.11 미만) | `build.sh`, `anal.py`. 각 leaf의 `requirements.txt`로 설치합니다. |
| FE-ToolKit `edgembar-amber2dats.py`, `edgembar` | `anal.py`. `PATH`에 있어야 합니다. |

### 기본 계산량

모든 window는 minimization 5,000 cycles, heating 250,000 steps(500 ps), NPT
equilibration 500,000 steps(1 ns), production 10,000,000 steps(20 ns)를
실행합니다. Timestep은 2 fs이고 production frame은 window당 2,000개입니다.

| Template | Window | `pmemd.cuda` 실행 | MD 합계 | Production 합계 |
| --- | --- | --- | --- | --- |
| RBFE | 22 (complex 11, solvent 11) | 88 | 473 ns | 440 ns |
| ABFE | 65 (restraint 11, charge 22, vdW 32) | 260 | 1,397.5 ns | 1,300 ns |

`./run.sh` 한 번은 선택한 window를 순서대로 실행합니다. Window를 여러 GPU에
나누려면 겹치지 않는 `--system`/`--stage`/`--windows` 조합으로 `run.sh`를 여러 번
동시에 실행합니다. 각 실행이 쓸 GPU는 scheduler나 `CUDA_VISIBLE_DEVICES` 같은 실행
환경에서 정합니다. 결과의 부호와 overlap 기준은
[FEP tutorial README](../../1_Simulation/5_FEP/README.md#결과-해석)를 따릅니다.

두 runner는 `--system complex|solvent`, 0-based inclusive
`--windows START-END`, `--preparation-only`와 `--production-only`를 지원합니다.
ABFE의 `--stage restraint|charge|vdw`는 생성된 leg만 선택합니다. RBFE protocol은
charge와 vdW를 하나의 alchemical path에서 함께 바꾸므로 별도 `--stage`를 허용하지
않습니다.

Lambda schedule은 config의 explicit list를 항상 사용하며 `auto`/`file` mode가
아닙니다. Segmented production은 지원하지 않아 `production_segments=1`만
사용합니다.

## English

The RBFE and ABFE templates generate Amber alchemical windows and record an
`ifmbar` energy matrix. Production defaults to 20 ns per window.

They require precharged ligand MOL2/frcmod inputs; the templates do not fit
charges. RBFE takes two ligand masks and an atom map; ABFE takes a ligand mask
and six explicit restraint anchors.

### Required programs

| Program | Used by |
| --- | --- |
| Amber 26 `pmemd.cuda` | `run.sh`; other executables are rejected. |
| AmberTools `tleap` | `build.sh` |
| Python packages `numpy`, `parmed`, `tomli` (Python < 3.11) | `build.sh`, `anal.py`; install from each leaf's `requirements.txt`. |
| FE-ToolKit `edgembar-amber2dats.py`, `edgembar` | `anal.py`; must be on `PATH`. |

### Default computation

Every window runs 5,000 minimization cycles, 250,000 heating steps (500 ps),
500,000 NPT equilibration steps (1 ns) and 10,000,000 production steps (20 ns).
The timestep is 2 fs, giving 2,000 production frames per window.

| Template | Windows | `pmemd.cuda` runs | Total MD | Total production |
| --- | --- | --- | --- | --- |
| RBFE | 22 (complex 11, solvent 11) | 88 | 473 ns | 440 ns |
| ABFE | 65 (restraint 11, charge 22, vdW 32) | 260 | 1,397.5 ns | 1,300 ns |

One `./run.sh` call runs its selected windows in sequence. To spread windows
over several GPUs, start concurrent `run.sh` calls with non-overlapping
`--system`/`--stage`/`--windows` selections. The GPU of each call is set by the
execution environment, such as the scheduler or `CUDA_VISIBLE_DEVICES`. See the
[FEP tutorial README](../../1_Simulation/5_FEP/README.md#interpreting-the-results)
for the sign convention and overlap guideline.

Both runners support `--system complex|solvent`, inclusive 0-based
`--windows START-END`, `--preparation-only`, and `--production-only`. ABFE
adds `--stage restraint|charge|vdw`, which selects only generated legs. The RBFE
protocol couples charge and vdW along one alchemical path and therefore rejects
a separate stage.

Lambda schedules always use the explicit config lists rather than an
`auto`/`file` mode. Segmented production is not supported, so only
`production_segments=1` is accepted.
