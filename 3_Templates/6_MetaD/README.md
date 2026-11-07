# MetaD and OPES templates

## 한국어

네 template는 AMBER가 coordinate를 적분하고 PLUMED가 bias를 계산하는 같은
workflow를 사용합니다. WT-MetaD와 Funnel-MetaD는 방문한 CV 위치에 hill을 직접
누적합니다. OPES는 방문 sample로 분포를 추정한 뒤 target distribution에 필요한
bias를 갱신합니다. Method는 leaf directory로 고정되며 별도 config mode가 아닙니다.

| Directory | Bias와 state |
| --- | --- |
| [`6.1_WT-MetaD`](6.1_WT-MetaD/) | CV 공간의 well-tempered hill, `HILLS` |
| [`6.2_Funnel-MetaD`](6.2_Funnel-MetaD/) | ligand projection hill과 funnel restraint, `HILLS` |
| [`6.3_OPES_METAD`](6.3_OPES_METAD/) | Adaptive density estimate, `KERNELS`와 `opes.state` |
| [`6.4_OPES_EXPANDED`](6.4_OPES_EXPANDED/) | 300–500 K multithermal target, `DELTAFS`와 `opes.state` |

### 준비

| 항목 | 조건 |
| --- | --- |
| MD engine | PLUMED가 연결된 `pmemd.cuda`, `pmemd` 또는 `sander`(아래 Engine 선택) |
| PLUMED | PLUMED 2.10. Funnel은 `funnel`, OPES는 `opes` optional module이 필요합니다(`--enable-modules=funnel+opes`). `PLUMED`로 executable을 바꿉니다. |
| AmberTools | `tleap`. Funnel ligand는 미리 만든 GAFF2 MOL2/frcmod를 사용합니다. |
| Python | Leaf의 `requirements.txt`: `numpy`, `parmed`, Python 3.11 미만에서는 `tomli` |

`run.sh`는 action availability와 generated input을 production 전에 검사합니다.

### 공통 workflow

WT-MetaD와 두 OPES template는 한 번의 whole-system minimization을 사용하고,
Funnel-MetaD만 restrained solvent minimization을 먼저 수행합니다. Production은
generated AMBER input의 `plumed=1`, `plumedfile='plumed.dat'`로 segment-local
PLUMED input을 연결합니다.

모든 기본 production은 2 fs에서 50,000,000 steps, 즉 100 ns이며 10 segments로
나뉩니다. Segment가 여러 개이면 coordinate와 trajectory는 `work/001` 형식으로
저장하고 누적 bias state와 `COLVAR`는 `work/`에 유지합니다. 다음 segment는 AMBER
restart와 PLUMED bias state를 모두 이어받습니다.

처음 numbered layout으로 실행했다면 segment 수를 줄여도 첫 output은 `work/001/`에
유지합니다. 한 segment를 root `work/production.*`로 완료한 뒤 segment 수를
늘렸다면 첫 output은 그대로 두고 후속 output만 `work/002/`, `work/003/`에
생성합니다.

### Bias 이어받기

Segment 2부터 generated `plumed.dat` 첫 줄에 `RESTART`를 넣습니다. PLUMED는
`HILLS`, `KERNELS`, `DELTAFS`, `COLVAR`를 새로 쓰지 않고 이어 쓰며, OPES는
`STATE_RFILE`로 직전 segment 끝의 adaptive state를 읽습니다.

| Method | Segment 1이 만드는 file | Segment K ≥ 2가 `RESTART`와 함께 이어받는 file |
| --- | --- | --- |
| WT-MetaD | `HILLS` | `HILLS` |
| Funnel-MetaD | `HILLS`, `FUNNEL_GRID` | `HILLS`, `FUNNEL_GRID` |
| OPES_METAD | `KERNELS`, `opes.state`(`STATE_WFILE`) | `opes.state`(`STATE_RFILE`), `KERNELS` |
| OPES_EXPANDED | `DELTAFS`, `opes.state`(`STATE_WFILE`) | `opes.state`(`STATE_RFILE`), `DELTAFS` |

PLUMED 문서에 따르면 OPES_METAD는 `KERNELS`로도 restart할 수 있지만 정확한
restart에는 `STATE_RFILE`이 필요합니다. 그래서 OPES template의
`state_write_interval_steps`는 segment 끝에 `opes.state`가 쓰이도록 검사합니다.

### 계산량

| Stage | 기본 길이 | 설정 |
| --- | --- | --- |
| Minimization | 5000 cycles(steepest descent 2500) | Funnel은 solute 10.0 kcal mol⁻¹ Å⁻² restraint를 건 solvent minimization을 먼저 실행합니다. |
| Heating | 250,000 steps(500 ps) | NVT, 10 K → `temperature`, solute restraint 2.0 kcal mol⁻¹ Å⁻² |
| Equilibration | 500,000 steps(1 ns) | NPT. Funnel만 0.5 kcal mol⁻¹ Å⁻² restraint를 유지합니다. |
| Production | 50,000,000 steps(100 ns) = 10 segments × 10 ns | `PACE=500`이면 bias update 100,000회, `COLVAR`는 5000 steps마다 1행(10,000행) |

모든 stage는 GPU 하나에서 순서대로 실행하며 segment도 하나씩 이어서 실행합니다.

### 공통 numeric option

Method별 PLUMED option은 각 leaf README에 있습니다.

| Key | 기본값 | Unit | 적용 stage | 효과 |
| --- | --- | --- | --- | --- |
| `solute_box_distance` | 14.0(Funnel 20.0) | Å | Build | Solute와 box edge 사이 최소 거리 |
| `salt_concentration` | 150.0 | mM | Build | Neutralization 뒤 bulk salt 농도 |
| `temperature` | 300.0 | K | Heating 이후 전체 | AMBER `temp0`와 PLUMED `TEMP` |
| `pressure` | 1.0 | bar | NPT stage | `pres0` |
| `timestep` | 2.0 | fs | 모든 MD | AMBER `dt`(ps로 변환) |
| `minimization_steps`, `minimization_steepest_steps` | 5000, 2500 | cycle | Minimization | `maxcyc`, `ncyc` |
| `heating_initial_temperature` | 10.0 | K | Heating | `tempi`와 `TEMP0` ramp 시작값 |
| `heating_steps`, `equilibration_steps` | 250000, 500000 | step | Heating, equilibration | 500 ps, 1 ns |
| `production_steps`, `production_segments` | 50000000, 10 | step, segment | Production | 100 ns를 10 segments로 나눕니다. 나누어떨어져야 합니다. |
| `trajectory_interval_steps` | 5000 | step | MD와 PLUMED | AMBER `ntwx`와 `COLVAR`의 `PRINT STRIDE` |
| `energy_interval_steps`, `restart_interval_steps` | 5000, 5000 | step | Heating 이후 | `ntpr`, `ntwr` |

### 실행 option

`--segment N`과 1-based inclusive `--segments START-END`는 동시에 사용할 수
없습니다. `--preparation-only`는 bias deposition 직전까지 실행하고,
`--production-only`는 완료된 equilibration과 기존 bias state에서 시작합니다.

### Engine 선택

`AMBER_ENGINE`이 설정되어 있으면 이를 사용하며, 없으면 build가 기록한
`work/resolved_config.toml`의 `run.engine`을 읽습니다. Build 전 dry-run에 한해서
resolved config가 없으면 `config.toml`을 읽습니다. 허용하는 executable 이름은
`pmemd.cuda`, `pmemd`, `sander`이며 설치 경로를 지정할 수 있습니다. PLUMED 연동이
가능한 AMBER build가 필요합니다. 빈 override, 누락된 engine 설정과 지원하지 않는
executable은 기본값으로 대체하지 않고 중단합니다. 이 설정은 자동 호출되는
`helpers/config_utils.py`가 읽습니다.

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
미검증입니다. pmemd 안에서 난 PLUMED error는 segment의 engine stdout/stderr
log(`work/K/engine.production.log`)에 남습니다.

### 문제 해결

| Error message | 확인할 것 |
| --- | --- |
| `PLUMED action unavailable: ... Rebuild PLUMED 2.10 with --enable-modules=...` | 해당 optional module을 넣어 PLUMED를 다시 build합니다. |
| `PLUMED parse-only check failed: ...` | `work/plumed.parse.log`. `config.toml` 값이나 CV label을 고친 뒤 새 `WORK_DIR`에서 build합니다. |
| `Config error in ...` | Error에 나온 key의 길이, 부호, 나누어떨어짐 조건을 확인합니다. |
| `Bias state required for continuation was not found` | 직전 segment의 root bias file이 지워졌습니다. 위 복구 절차로 되돌립니다. |
| `Bias output exists before the first production segment` | 실패한 segment 1의 file입니다. Error에 출력된 `mv` command를 실행합니다. |

그 밖의 실행 상태, 실패 후 재실행과 동시 실행 보호는
[GUIDE.md 부록](../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

AMBER propagates coordinates and PLUMED evaluates the bias in all four
templates. WT-MetaD and Funnel-MetaD directly deposit hills at visited CV
positions. OPES first estimates a sampled distribution and updates the bias
needed for its target distribution. The method is fixed by the leaf directory
and is not a separate config mode.

| Directory | Bias and state |
| --- | --- |
| [`6.1_WT-MetaD`](6.1_WT-MetaD/) | Well-tempered hills in CV space, `HILLS` |
| [`6.2_Funnel-MetaD`](6.2_Funnel-MetaD/) | Ligand-projection hills and funnel restraint, `HILLS` |
| [`6.3_OPES_METAD`](6.3_OPES_METAD/) | Adaptive density estimate, `KERNELS` and `opes.state` |
| [`6.4_OPES_EXPANDED`](6.4_OPES_EXPANDED/) | 300–500 K multithermal target, `DELTAFS` and `opes.state` |

### Prerequisites

| Item | Requirement |
| --- | --- |
| MD engine | PLUMED-enabled `pmemd.cuda`, `pmemd` or `sander` (see Engine selection) |
| PLUMED | PLUMED 2.10. Funnel needs the optional `funnel` module and OPES the optional `opes` module (`--enable-modules=funnel+opes`). `PLUMED` selects the executable. |
| AmberTools | `tleap`; the Funnel ligand uses prepared GAFF2 MOL2/frcmod files. |
| Python | The leaf `requirements.txt`: `numpy`, `parmed`, and `tomli` below Python 3.11 |

`run.sh` checks action availability and parses the generated input before
production.

### Common workflow

WT-MetaD and both OPES templates use one whole-system minimization; only
Funnel-MetaD adds restrained solvent minimization first. Production connects the
segment-local PLUMED input through `plumed=1` and `plumedfile='plumed.dat'` in
the generated AMBER input.

Each default production is 50,000,000 steps at 2 fs, or 100 ns, divided into
ten segments. Segment coordinates and trajectories use `work/001` directories,
while cumulative bias state and `COLVAR` remain in `work/`. Every continuation
inherits both the AMBER restart and the method-specific PLUMED state.

If the first run used numbered directories, reducing the segment count keeps the
first output under `work/001/`. If one segment completed as `work/production.*`,
increasing the count keeps that output and writes later segments under
`work/002/`, `work/003/`, etc.

### Bias continuation

From segment 2 on, the generated `plumed.dat` starts with `RESTART`. PLUMED then
appends to `HILLS`, `KERNELS`, `DELTAFS` and `COLVAR` instead of starting them
again, and OPES reads the adaptive state at the end of the previous segment
through `STATE_RFILE`.

| Method | Files written by segment 1 | Files carried into segment K ≥ 2 with `RESTART` |
| --- | --- | --- |
| WT-MetaD | `HILLS` | `HILLS` |
| Funnel-MetaD | `HILLS`, `FUNNEL_GRID` | `HILLS`, `FUNNEL_GRID` |
| OPES_METAD | `KERNELS`, `opes.state` (`STATE_WFILE`) | `opes.state` (`STATE_RFILE`), `KERNELS` |
| OPES_EXPANDED | `DELTAFS`, `opes.state` (`STATE_WFILE`) | `opes.state` (`STATE_RFILE`), `DELTAFS` |

The PLUMED documentation allows an OPES_METAD restart from `KERNELS` but needs
`STATE_RFILE` for an exact restart. The OPES templates therefore check that
`state_write_interval_steps` writes `opes.state` at each segment end.

### Expected computation

| Stage | Default length | Settings |
| --- | --- | --- |
| Minimization | 5000 cycles (2500 steepest descent) | Funnel first runs a solvent minimization with a 10.0 kcal mol⁻¹ Å⁻² solute restraint. |
| Heating | 250,000 steps (500 ps) | NVT, 10 K → `temperature`, 2.0 kcal mol⁻¹ Å⁻² solute restraint |
| Equilibration | 500,000 steps (1 ns) | NPT; only Funnel keeps a 0.5 kcal mol⁻¹ Å⁻² restraint. |
| Production | 50,000,000 steps (100 ns) = 10 segments × 10 ns | With `PACE=500`, 100,000 bias updates; one `COLVAR` row per 5000 steps (10,000 rows) |

All stages run in order on one GPU, and segments run one after another.

### Common numeric options

Method-specific PLUMED options are in each leaf README.

| Key | Default | Unit | Stage | Effect |
| --- | --- | --- | --- | --- |
| `solute_box_distance` | 14.0 (Funnel 20.0) | Å | Build | Minimum solute–box-edge distance |
| `salt_concentration` | 150.0 | mM | Build | Bulk salt added after neutralization |
| `temperature` | 300.0 | K | Heating onward | AMBER `temp0` and PLUMED `TEMP` |
| `pressure` | 1.0 | bar | NPT stages | `pres0` |
| `timestep` | 2.0 | fs | All MD | AMBER `dt` (converted to ps) |
| `minimization_steps`, `minimization_steepest_steps` | 5000, 2500 | cycle | Minimization | `maxcyc`, `ncyc` |
| `heating_initial_temperature` | 10.0 | K | Heating | `tempi` and the start of the `TEMP0` ramp |
| `heating_steps`, `equilibration_steps` | 250000, 500000 | step | Heating, equilibration | 500 ps, 1 ns |
| `production_steps`, `production_segments` | 50000000, 10 | step, segment | Production | Splits 100 ns into 10 segments; must divide evenly. |
| `trajectory_interval_steps` | 5000 | step | MD and PLUMED | AMBER `ntwx` and the `COLVAR` `PRINT STRIDE` |
| `energy_interval_steps`, `restart_interval_steps` | 5000, 5000 | step | Heating onward | `ntpr`, `ntwr` |

### Run options

`--segment N` and the inclusive 1-based `--segments START-END` are mutually
exclusive. `--preparation-only` stops before bias deposition;
`--production-only` starts from completed equilibration and the existing bias
state.

### Engine selection

`AMBER_ENGINE` overrides `run.engine` in the build-generated
`work/resolved_config.toml`. Before the build, dry-run alone may read
`config.toml` when the resolved file is absent. Accepted executable names are
`pmemd.cuda`, `pmemd` and `sander`; installation paths are accepted. An AMBER
build with PLUMED integration is required. Empty overrides, missing engine
settings and unsupported executables fail instead of falling back to a default.
The automatically called `helpers/config_utils.py` reads this setting.

### Recovering a failed production segment

Before segment K (K ≥ 2) starts, `run.sh` copies the root bias files and
`COLVAR` into `work/K/bias_start/`. A failed segment may already have appended
hills, kernels or state to the root files, so continuing from them would not
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
is unverified. PLUMED errors raised inside pmemd appear in the segment's engine
stdout/stderr log (`work/K/engine.production.log`).

### Troubleshooting

| Error message | What to check |
| --- | --- |
| `PLUMED action unavailable: ... Rebuild PLUMED 2.10 with --enable-modules=...` | Rebuild PLUMED with that optional module. |
| `PLUMED parse-only check failed: ...` | `work/plumed.parse.log`. Fix `config.toml` values or CV labels and build in a new `WORK_DIR`. |
| `Config error in ...` | Check the length, sign and divisibility rules of the key named in the error. |
| `Bias state required for continuation was not found` | A root bias file of the previous segment is missing; restore it as described above. |
| `Bias output exists before the first production segment` | The files come from a failed segment 1; run the printed `mv` command. |

See [GUIDE.md appendix](../../GUIDE.md#4-appendix-run-state-and-recovery) for other run-state rules, reruns after
failure and concurrent-run protection.
