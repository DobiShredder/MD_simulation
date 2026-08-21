# MetaD and OPES templates

## 한국어

네 template는 AMBER가 coordinate를 적분하고 PLUMED가 bias를 계산하는 같은
workflow를 사용합니다. WT-MetaD와 Funnel-MetaD는 방문한 CV 위치에 hill을 직접
누적합니다. OPES는 방문 sample로 분포를 추정한 뒤 target distribution에 필요한
bias를 갱신합니다.

| Directory | Bias와 state |
| --- | --- |
| `7.1_WT-MetaD` | CV 공간의 well-tempered hill, `HILLS` |
| `7.2_Funnel-MetaD` | ligand projection hill과 funnel restraint, `HILLS` |
| `7.3_OPES_METAD` | Adaptive density estimate, `KERNELS`와 `opes.state` |
| `7.4_OPES_EXPANDED` | 300–500 K multithermal target, `DELTAFS`와 `opes.state` |

모든 기본 production은 2 fs에서 50,000,000 steps, 즉 100 ns이며 10 segments로
나뉩니다. Segment가 여러 개이면 coordinate와 trajectory는 `work/001` 형식으로
저장하고 누적 bias state와 `COLVAR`는 `work/`에 유지합니다. 다음 segment는 AMBER
restart와 PLUMED bias state를 모두 이어받습니다.

PLUMED 2.10 build에는 method별 action이 포함되어야 합니다. Funnel은 `funnel`,
OPES는 `opes` module이 필요합니다. `run.sh`는 action availability와 generated
input을 production 전에 검사합니다.
WT-MetaD와 두 OPES template는 한 번의 whole-system minimization을 사용하고,
Funnel-MetaD만 restrained solvent minimization을 먼저 수행합니다. Production은
generated AMBER input의 `plumed=1`, `plumedfile='plumed.dat'`로 segment-local
PLUMED input을 연결합니다.

기존 `--segment N`과 1-based inclusive `--segments START-END`를 함께
제공하되 동시에 사용할 수는 없습니다. `--preparation-only`는 bias deposition
직전까지 실행하고, `--production-only`는 완료된 equilibration과 기존 bias
state에서 시작합니다.

## English

AMBER propagates coordinates and PLUMED evaluates the bias in all four
templates. WT-MetaD and Funnel-MetaD directly deposit hills at visited CV
positions. OPES first estimates a sampled distribution and updates the bias
needed for its target distribution.

Each default production is 50,000,000 steps at 2 fs, or 100 ns, divided into
ten segments. Segment coordinates and trajectories use `work/001` directories,
while cumulative bias state and `COLVAR` remain in `work/`. Every continuation
inherits both the AMBER restart and the method-specific PLUMED state. Funnel
and OPES require the corresponding optional PLUMED 2.10 modules; `run.sh`
checks the actions and parses the generated input before production.
WT-MetaD and both OPES templates use one whole-system minimization; only
Funnel-MetaD adds restrained solvent minimization. Production connects the
segment-local PLUMED input through `plumed=1` and
`plumedfile='plumed.dat'` in the generated AMBER input.
The existing `--segment N` selector and inclusive 1-based
`--segments START-END` are mutually exclusive. `--preparation-only` stops
before bias deposition; `--production-only` requires completed equilibration
and the applicable bias state.
