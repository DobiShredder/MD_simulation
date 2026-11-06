# MetaD and OPES templates

## 한국어

WT-MetaD, Funnel-MetaD, OPES_METAD와 OPES_EXPANDED의 선택은 leaf directory로
고정되며 별도 config mode가 아닙니다.

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

### 실패한 production segment 복구

Segment K(K ≥ 2)를 시작하기 전에 `run.sh`는 root bias file과 `COLVAR`를
`work/K/bias_start/`에 복사합니다. 실패한 segment는 root bias file에 hill,
kernel 또는 state를 이미 추가했을 수 있으므로 그대로 이어서 실행하면
`work/K-1/production.rst7`과 bias가 맞지 않습니다. `run.sh`는 이런 segment를
자동으로 지우거나 되돌리지 않고, 다시 실행하면 중단하면서 다음 command를
출력합니다. WT-MetaD의 segment 3 예시입니다.

```bash
mkdir -p work.failed
mv work/003 work.failed/
cp -p work.failed/003/bias_start/HILLS work/HILLS
cp -p work.failed/003/bias_start/COLVAR work/COLVAR
./run.sh --segments 3-10
```

복사할 file은 method별 bias state(`HILLS`, `KERNELS`/`opes.state`,
`DELTAFS`/`opes.state`, Funnel의 `FUNNEL_GRID`)와 `COLVAR`입니다. Segment 1이
실패하면 snapshot 대신 `work/001`과 root bias file을 `work.failed/`로 옮깁니다.
PLUMED backup file(`work/bck.*`)은 restart에서 읽지 않으므로 함께 옮깁니다.
PLUMED log의 위치(`work/K/plumed.log`)는 AMBER 기본 이름을 가정한 것으로
미검증입니다.

## English

WT-MetaD, Funnel-MetaD, OPES_METAD, and OPES_EXPANDED are selected by leaf
directory and are not separate config modes.

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

### Recovering a failed production segment

Before segment K (K ≥ 2) starts, `run.sh` copies the root bias files and
`COLVAR` into `work/K/bias_start/`. A failed segment may already have appended
hills, kernels, or state to the root files, so continuing from them would not
match `work/K-1/production.rst7`. `run.sh` never deletes or restores such a
segment; a rerun stops and prints the restore commands. Example for WT-MetaD
segment 3:

```bash
mkdir -p work.failed
mv work/003 work.failed/
cp -p work.failed/003/bias_start/HILLS work/HILLS
cp -p work.failed/003/bias_start/COLVAR work/COLVAR
./run.sh --segments 3-10
```

The restored files are the method's bias state (`HILLS`, `KERNELS`/`opes.state`,
`DELTAFS`/`opes.state`, plus `FUNNEL_GRID` for Funnel) and `COLVAR`. If segment 1
fails, move `work/001` and the root bias files to `work.failed/` instead.
PLUMED backup files (`work/bck.*`) are not read on restart; move them as well.
The PLUMED log location (`work/K/plumed.log`) assumes the AMBER default name and
is unverified.
