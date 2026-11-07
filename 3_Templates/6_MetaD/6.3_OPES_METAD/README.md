# OPES_METAD template

## 한국어

OPES_METAD는 방문한 위치에 hill을 그대로 누적하지 않습니다. CV sample로
probability distribution을 추정하고 target distribution에 필요한 bias를
갱신합니다. `KERNELS`는 압축된 distribution estimate이고 `opes.state`는 restart에
필요한 adaptive state입니다. OPES_METAD 방식은 이 directory에서 고정되며 별도
config mode가 아닙니다.

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`로 설치합니다. 사용자가 직접 실행하는 파일은 이
directory의 root에 있고, `helpers/`는 자동 호출되는 내부 code입니다.

### 필요한 input과 실행

`download.sh PDB_ID`는 optional source PDB를 내려받습니다. 임시 파일에서 PDB atom
record를 확인한 뒤 최종 파일로 교체합니다. `build.sh`는 준비한 PDB로 topology와
PLUMED input을 만들고 `run.sh`는 `opes.state`를 이어받아 segmented production을
실행합니다.

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

100 ns production은 10 segments로 나뉩니다. 첫 segment가 `KERNELS`와
`opes.state`를 만들고, 이후 segment는 `RESTART`와 `STATE_RFILE`로 두 state를
이어받습니다. Root `COLVAR`도 append됩니다. State file이 하나라도 없으면 다음
segment를 시작하지 않습니다.

### 주요 output

| 파일 | 내용 |
| --- | --- |
| `work/KERNELS`, `work/opes.state`, `work/COLVAR` | 모든 segment가 공유하는 adaptive state와 CV |
| `work/001/` … | Segment별 restart, trajectory와 AMBER output |
| `work/analysis/production_summary.tsv` | CV와 bias 범위, final effective sample 수와 kernel 수 |

`anal.py`가 기록하는 effective sample 수와 kernel 수는 convergence 판정 자체가
아니며 CV coverage와 독립 run을 함께 봅니다. `COLVAR`의 header나 finite 값이
잘못되면 기존 analysis 결과를 교체하지 않습니다.

### 결과 확인과 해석

모든 segment가 끝나면 `run.sh`가 `MetaD production segments completed: 1-10 of 10 (...)`와
`Next: python3 anal.py`를 출력합니다. `anal.py`는
`OPES_METAD diagnostics: .../production_summary.tsv`로 끝납니다.

FES는 `COLVAR`의 bias로 reweight해서 얻습니다(Invernizzi & Parrinello,
*J. Phys. Chem. Lett.* 11:2731, 2020; PLUMED `OPES_METAD` 문서). 초기 구간을
제외한 각 행에 `w = exp(opes.bias / kT)`, `kT = k_B · temperature`를 주고, 가중
CV histogram `P(s)`에서 `F = −kT ln P`를 계산합니다. `opes.rct`는 c(t) 추정값이며
PLUMED 문서에 따라 reweighting에 쓰지 않습니다. Segment마다 얻은 FES가 더 이상
변하지 않는지 비교합니다.

### 주요 parameter

`cv.dat`의 label과 `collective_variable.arguments`를 함께 수정합니다. 기본
alanine φ/ψ atom 번호는 다른 topology에 적용하지 않습니다. CV마다 sigma 하나가
필요합니다.

`state_write_interval_steps`는 `pace_steps`로 나누어떨어져야 하고, segment당
step 수(`production_steps / production_segments`)도 이 값으로 나누어떨어져야
합니다. 그래야 마지막 `opes.state`가 segment 끝 상태가 됩니다.

| Key | 기본값 | Unit | PLUMED keyword | 효과 |
| --- | --- | --- | --- | --- |
| `sigma` | 0.15, 0.15 | CV unit(torsion은 rad) | `SIGMA` | CV별 처음 kernel width. Simulation이 진행되면 PLUMED가 줄입니다. |
| `barrier` | 50.0 | kJ/mol | `BARRIER` | 넘어야 할 barrier 추정값. PLUMED가 bias factor, regularization과 kernel cutoff 기본값을 정합니다. |
| `pace_steps` | 500 | step(1 ps) | `PACE` | Kernel 추가와 bias update 간격 |
| `state_write_interval_steps` | 50000 | step(100 ps) | `STATE_WSTRIDE` | `opes.state` 쓰기 간격. 위 나누어떨어짐 조건이 있습니다. |

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Conventional equilibration에 적용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | OPES_METAD production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | `"random"`은 AMBER `ig=-1`, 정수는 고정 seed를 사용합니다. |

### Engine option 직접 지정

Config key가 없는 AMBER option은 `[amber.<stage>.<namelist>]` table로 지정합니다. Stage 우선순위, 값 형식과 거부되는 keyword는 [3_Templates README](../../README.md#engine-option-직접-지정)를 따릅니다.

```toml
[amber.md.cntrl]
gamma_ln = 2.0

[amber.production.cntrl]
iwrap = 1

[plumed.bias_options]
NLIST = true   # OPES_METAD: kernel neighbor list (flag)
```

| Stage | Input |
| --- | --- |
| `minimization` | `minimize.in` |
| `heating` | `heat.in` |
| `equilibration` | `equilibrate.in` |
| `production` | `production.in.template` |

`[plumed]`는 production `plumed.dat`에 적용되며 bias action label은 `opes`입니다.

### 문제 해결

| Error message | 확인할 것 |
| --- | --- |
| `PLUMED action unavailable: OPES_METAD. Rebuild PLUMED 2.10 with --enable-modules=opes.` | `opes` module을 넣어 PLUMED를 다시 build합니다. |
| `state_write_interval_steps must be divisible by pace_steps` | `state_write_interval_steps`를 `pace_steps`의 배수로 바꿉니다. |
| `production steps per segment (...) must be divisible by state_write_interval_steps` | Segment 길이나 `state_write_interval_steps`를 바꿉니다. |
| `sigma must contain N values`, `sigma values must be positive` | CV마다 양수 sigma 하나를 적습니다. |

공통 error는 [MetaD template README](../README.md)의 문제 해결에 있습니다.

Segment layout, `--segments` option, engine 선택과 실패한 segment의
`KERNELS`/`opes.state` 복원은 [MetaD template README](../README.md)를 참고합니다.
실행 상태, 실패 후 재실행과 동시 실행 보호는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을
참고합니다.

## English

OPES_METAD does not simply accumulate hills at visited positions. It estimates
the probability distribution from CV samples and updates the bias needed for a
target distribution. `KERNELS` stores the compressed distribution estimate and
`opes.state` stores the adaptive state needed for restart. The OPES_METAD method
is fixed by this directory and is not a separate config mode.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt`. User-facing entry points are in
this directory root; `helpers/` contains internal code called automatically.

### Required inputs and run

`download.sh PDB_ID` retrieves an optional source PDB. It checks the PDB atom
records in a temporary file before replacing the final file. `build.sh` creates
the topology and PLUMED input from the prepared PDB, and `run.sh` continues
`opes.state` through the segmented production.

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

The 100 ns production is split into ten segments. The first segment creates
`KERNELS` and `opes.state`; later segments read both through `RESTART` and
`STATE_RFILE`. The root `COLVAR` is appended as well. If either state file is
missing, the next segment does not start.

### Main outputs

| File | Content |
| --- | --- |
| `work/KERNELS`, `work/opes.state`, `work/COLVAR` | Adaptive state and CVs shared by all segments |
| `work/001/` … | Restart, trajectory and AMBER output per segment |
| `work/analysis/production_summary.tsv` | CV and bias ranges, final effective sample size and kernel count |

The effective sample size and kernel count from `anal.py` are not a convergence
test by themselves; check them together with CV coverage and independent runs.
An invalid `COLVAR` header or nonfinite values leave previous analysis results
in place.

### Success check and interpretation

After the last segment, `run.sh` prints
`MetaD production segments completed: 1-10 of 10 (...)` and
`Next: python3 anal.py`. `anal.py` ends with
`OPES_METAD diagnostics: .../production_summary.tsv`.

Obtain the FES by reweighting with the bias in `COLVAR` (Invernizzi &
Parrinello, *J. Phys. Chem. Lett.* 11:2731, 2020; PLUMED `OPES_METAD`
documentation). After discarding the initial part, give each row
`w = exp(opes.bias / kT)` with `kT = k_B · temperature`, and compute
`F = −kT ln P` from the weighted CV histogram `P(s)`. `opes.rct` is the c(t)
estimate; the PLUMED documentation says not to use it for reweighting. Compare
the FES from successive segments until it stops changing.

### Key parameters

Edit the labels in `cv.dat` and `collective_variable.arguments` together. The
supplied alanine φ/ψ atom numbers do not apply to other topologies. One sigma is
needed per CV.

`state_write_interval_steps` must be a multiple of `pace_steps` and must divide
the steps per segment (`production_steps / production_segments`), so the last
`opes.state` matches the segment end.

| Key | Default | Unit | PLUMED keyword | Effect |
| --- | --- | --- | --- | --- |
| `sigma` | 0.15, 0.15 | CV unit (rad for torsions) | `SIGMA` | Initial kernel width per CV; PLUMED shrinks it as the run proceeds. |
| `barrier` | 50.0 | kJ/mol | `BARRIER` | Estimated barrier; PLUMED derives default bias factor, regularization and kernel cutoff from it. |
| `pace_steps` | 500 | step (1 ps) | `PACE` | Kernel deposition and bias-update interval |
| `state_write_interval_steps` | 50000 | step (100 ps) | `STATE_WSTRIDE` | `opes.state` write interval, with the divisibility rule above |

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to conventional equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Sets OPES_METAD production `ntb` and `ntp`. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | `"random"` maps to AMBER `ig=-1`; an integer fixes the seed. |

### Engine option passthrough

AMBER options without a config key go into `[amber.<stage>.<namelist>]` tables. Stage precedence, value formats and refused keywords are described in the [3_Templates README](../../README.md#engine-option-passthrough).

```toml
[amber.md.cntrl]
gamma_ln = 2.0

[amber.production.cntrl]
iwrap = 1

[plumed.bias_options]
NLIST = true   # OPES_METAD: kernel neighbor list (flag)
```

| Stage | Input |
| --- | --- |
| `minimization` | `minimize.in` |
| `heating` | `heat.in` |
| `equilibration` | `equilibrate.in` |
| `production` | `production.in.template` |

`[plumed]` applies to the production `plumed.dat`; the bias action label is `opes`.

### Troubleshooting

| Error message | What to check |
| --- | --- |
| `PLUMED action unavailable: OPES_METAD. Rebuild PLUMED 2.10 with --enable-modules=opes.` | Rebuild PLUMED with the `opes` module. |
| `state_write_interval_steps must be divisible by pace_steps` | Make `state_write_interval_steps` a multiple of `pace_steps`. |
| `production steps per segment (...) must be divisible by state_write_interval_steps` | Change the segment length or `state_write_interval_steps`. |
| `sigma must contain N values`, `sigma values must be positive` | Give one positive sigma per CV. |

Common errors are listed under Troubleshooting in the
[MetaD template README](../README.md).

See the [MetaD template README](../README.md) for the segment layout, the
`--segments` option, engine selection and restoring `KERNELS`/`opes.state` after
a failed segment. See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state, reruns
after failure and concurrent-run protection.
