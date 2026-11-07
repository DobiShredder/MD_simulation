# GaMD templates

## 한국어

세 template는 conventional MD equilibration 뒤에 potential-energy 통계를 모아
GaMD boost parameter를 만들고, 그 state를 production segment 사이에 이어받습니다.
GaMD, LiGaMD3와 Pep-GaMD의 선택은 leaf directory로 고정되며 별도 config mode가
아닙니다.

| Directory | Boost |
| --- | --- |
| `4.1_GaMD` | System total potential과 dihedral dual boost |
| `4.2_LiGaMD3` | Ligand essential, 나머지 nonbonded, bonded triple boost |
| `4.3_Pep-GaMD` | Peptide와 나머지 system dual boost |

Preparation은 tutorial과 같은 whole-system minimization, restrained NVT
heating과 NPT equilibration 순서입니다. 기본 config의 GaMD parameter preparation과
production은 NVT입니다. `gamd-restart.dat`와 MD restart를 모두 이어받아야 같은
bias state가 유지됩니다.

`--preparation-only`는 GaMD parameter preparation까지 실행합니다.
`--production-only`와 1-based inclusive `--segments START-END`는 완료된
`gamd-restart.dat`와 MD restart부터 production을 이어갑니다.

LiGaMD3와 Pep-GaMD는 Amber 26의 serial `pmemd.cuda`가 필요합니다. 두 input은
`gti_add_sc=1`, `ntf=1`을 사용합니다. LiGaMD3는 Amber 26 GPU에서 미검증이므로
실제 engine 실행에 `--allow-unverified`가 필요합니다.

### 필요한 program

| Program | 사용하는 script |
| --- | --- |
| Amber 26 `pmemd.cuda` | `run.sh`. 세 template 모두 다른 executable을 거부합니다. |
| AmberTools 26 `tleap` (`TLEAP`로 변경 가능) | `build.sh` |
| Python 3와 leaf의 `requirements.txt`(ParmEd, NumPy, Python 3.11 미만에서는 `tomli`) | `build.sh`와 `run.sh`가 호출하는 `helpers/` |

### 기본 계산량

세 leaf의 기본 `config.toml`은 같은 길이를 사용합니다. `timestep`은 2 fs입니다.

| Stage | Config key | 기본 steps | 길이 |
| --- | --- | --- | --- |
| Minimization | `minimization_steps` | 5,000 cycles | — |
| Heating | `heating_steps` | 250,000 | 500 ps |
| Equilibration | `equilibration_steps` | 500,000 | 1 ns |
| GaMD parameter preparation | `conventional_statistics_steps` + `boost_statistics_steps` | 2,000,000 | 4 ns |
| Production | `production_steps` / `production_segments` | 50,000,000 / 10 | 10 ns × 10 = 100 ns |

`run.sh`는 GPU 하나에서 engine을 14번(preparation 4번, segment 10번) 순서대로
실행합니다. 각 segment가 앞 segment의 restart와 GaMD state를 이어받으므로
segment는 병렬로 실행하지 않습니다. Independent run은 서로 다른 `WORK_DIR`로 따로
build하고 실행합니다. 정수 `random_seed`를 쓰면 run마다 다른 값을 지정합니다.

### 결과 해석

Template에는 analysis entry가 없습니다. Segment별 `production.gamd.log`의 boost
distribution은 [GaMD tutorial README](../../1_Simulation/4_GaMD/README.md#결과-해석)와
같은 기준(anharmonicity, effective sample size, `sigma0*` 대비 폭)으로
확인합니다. 2차 cumulant reweighting은 boost distribution이 Gaussian에 가까울 때만
정확합니다(Miao et al. 2014, *J. Chem. Theory Comput.* 10, 2677).

## English

Each template collects potential-energy statistics after conventional MD
equilibration, constructs GaMD boost parameters, and continues that state across
production segments. GaMD, LiGaMD3, and Pep-GaMD are selected by leaf directory
and are not separate config modes.

| Directory | Boost |
| --- | --- |
| `4.1_GaMD` | System total-potential and dihedral dual boost |
| `4.2_LiGaMD3` | Ligand-essential, remaining nonbonded and bonded triple boost |
| `4.3_Pep-GaMD` | Peptide and remaining-system dual boost |

Preproduction follows the tutorial order: whole-system minimization, restrained
NVT heating, and NPT equilibration. By default, GaMD parameter preparation and
production use NVT. Both the MD restart and `gamd-restart.dat` must be continued
to keep the same bias state.

`--preparation-only` runs through GaMD parameter preparation.
`--production-only` and inclusive 1-based `--segments START-END` continue
production from the completed `gamd-restart.dat` and MD restart.

Amber 26 LiGaMD3 and Pep-GaMD require serial `pmemd.cuda`. Both inputs use
`gti_add_sc=1` and `ntf=1`. LiGaMD3 is unverified on the Amber 26 GPU engine, so
engine runs require `--allow-unverified`.

### Required programs

| Program | Used by |
| --- | --- |
| Amber 26 `pmemd.cuda` | `run.sh`. All three templates reject any other executable. |
| AmberTools 26 `tleap` (override with `TLEAP`) | `build.sh` |
| Python 3 and the leaf's `requirements.txt` (ParmEd, NumPy, `tomli` below Python 3.11) | `helpers/` called by `build.sh` and `run.sh` |

### Default computation

The default `config.toml` of all three leaves uses the same lengths, with a
2 fs `timestep`.

| Stage | Config key | Default steps | Length |
| --- | --- | --- | --- |
| Minimization | `minimization_steps` | 5,000 cycles | — |
| Heating | `heating_steps` | 250,000 | 500 ps |
| Equilibration | `equilibration_steps` | 500,000 | 1 ns |
| GaMD parameter preparation | `conventional_statistics_steps` + `boost_statistics_steps` | 2,000,000 | 4 ns |
| Production | `production_steps` / `production_segments` | 50,000,000 / 10 | 10 ns × 10 = 100 ns |

`run.sh` runs the engine 14 times in sequence on one GPU (four preparation
stages and ten segments). Each segment continues the previous restart and GaMD
state, so segments do not run in parallel. Build and run independent runs
separately with different `WORK_DIR`s; with an integer `random_seed`, give
each run a different value.

### Interpreting the results

The templates have no analysis entry. Check the boost distribution in each
segment's `production.gamd.log` with the criteria of the
[GaMD tutorial README](../../1_Simulation/4_GaMD/README.md#interpreting-the-results)
(anharmonicity, effective sample size, width relative to `sigma0*`).
Second-order cumulant reweighting is accurate only for a near-Gaussian boost
distribution (Miao et al. 2014, *J. Chem. Theory Comput.* 10, 2677).
