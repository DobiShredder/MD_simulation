# OPES_EXPANDED multithermal template

## 한국어

Potential energy `ene`에서 300–500 K multithermal target을 만들고
OPES_EXPANDED가 temperature state의 free-energy offset을 학습합니다. 물리적인 MD
temperature는 300 K이며, bias를 통해 설정 범위의 energy fluctuation을
sampling합니다. OPES_EXPANDED 방식은 이 directory에서 고정되며 별도 config
mode가 아닙니다.

이 template는 multithermal expansion입니다. Hamiltonian expansion을 사용하려면
Hamiltonian state 정의와 engine coupling을 별도로 구성해야 합니다.

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`로 설치합니다. 사용자가 직접 실행하는 파일은 이
directory의 root에 있고, `helpers/`는 자동 호출되는 내부 code입니다.

### 필요한 input과 실행

`download.sh PDB_ID`는 optional source PDB를 내려받습니다. 임시 파일에서 PDB atom
record를 확인한 뒤 최종 파일로 교체합니다. `build.sh`는 준비한 PDB로 NPT
equilibration과 NVT expanded-ensemble input을 만들고, `run.sh`는 state를 이어받아
segment를 실행하며, `anal.py`는 누적 output을 요약합니다.

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

첫 segment는 `DELTAFS`와 `opes.state`를 만들고 이후 segment는 `RESTART`와
`STATE_RFILE=opes.state`로 이어받습니다. PLUMED 2.10은 어느 file에서도 restart할
수 있지만, 이 template는 readable checkpoint인 `opes.state`를 continuation의
단일 기준으로 사용하고 `DELTAFS`는 state별 free-energy estimate와 분석용으로
보존합니다.

### 주요 output

| 파일 | 내용 |
| --- | --- |
| `work/DELTAFS`, `work/opes.state`, `work/COLVAR` | 모든 segment가 공유하는 state별 free-energy estimate, adaptive state와 CV |
| `work/001/` … | Segment별 restart, trajectory와 AMBER output |
| `work/analysis/production_summary.tsv` | Energy, expanded CV, bias 범위와 생성된 state 수 |

`COLVAR`의 header나 finite 값이 잘못되면 기존 analysis 결과를 교체하지 않습니다.

### 결과 확인과 해석

모든 segment가 끝나면 `run.sh`가 `MetaD production segments completed: 1-10 of 10 (...)`와
`Next: python3 anal.py`를 출력합니다. `DELTAFS`에서 temperature state 수를
확인합니다.

Temperature `T`의 observable은 `COLVAR`의 `ene`와 `opes.bias`(둘 다 kJ/mol)로
reweight합니다(Invernizzi, Piaggi & Parrinello, *Phys. Rev. X* 10:041034, 2020).
안내용 식이며 이 template는 구현하지 않았습니다.

```text
w_T ∝ exp(β₀ · opes.bias − (β_T − β₀) · ene)
β = 1 / (k_B T), k_B = 0.0083144626 kJ mol⁻¹ K⁻¹, T₀ = temperature
```

Segment 1 앞부분의 observation 구간(`observation_steps × pace_steps`, PLUMED 기본
100 × 500 steps)은 bias가 0이므로 제외하고, `T`는 `minimum_temperature`–
`maximum_temperature` 안에서만 고릅니다.

### 주요 parameter

`minimum_temperature`와 `maximum_temperature`는 base temperature를 포함해야
합니다. State grid는 `ECV_MULTITHERMAL`이 자동으로 만듭니다.

자동 temperature grid는 system 전체 potential energy fluctuation으로 temperature 수를
정합니다. Explicit-solvent system에서는 temperature가 많이 필요할 수 있습니다.
`[opes_expanded]`의 선택 key로 grid를 직접 지정할 수 있습니다. Key가 없으면 keyword를
쓰지 않고 PLUMED 기본값을 사용합니다.

| Key | PLUMED keyword | 의미와 제한 |
| --- | --- | --- |
| `temperature_steps` | `ECV_MULTITHERMAL TEMP_STEPS` | `minimum_temperature`부터 `maximum_temperature`까지의 temperature 수입니다. 2 이상의 정수입니다. 없으면 초기 unbiased step에서 자동으로 정합니다. |
| `observation_steps` | `OPES_EXPANDED OBSERVATION_STEPS` | Grid 초기화 전 unbiased observation 길이이며 `pace_steps` 단위입니다(PLUMED 기본 100). 양의 정수이고 `observation_steps * pace_steps`가 segment당 step 수보다 작아야 합니다. Observation이 끝나기 전에는 `opes.state`를 쓰지 않습니다. |

두 key를 쓴 PLUMED input의 parsing과 실행은 미검증입니다.

`state_write_interval_steps`는 `pace_steps`로 나누어떨어져야 하고, segment당
step 수(`production_steps / production_segments`)도 이 값으로 나누어떨어져야
합니다. 그래야 마지막 `opes.state`가 segment 끝 상태가 됩니다.

Production은 NVT만 지원합니다. PLUMED 2.10의 `ECV_MULTITHERMAL`은 고정
pressure에서 `E+pV`를 요구하지만, 이 input은 `ENERGY`만 사용합니다.
`production_ensemble="NPT"`는 build/dry-run과 input 생성 전에 거부하며, 과거 NPT
config도 run과 analysis에서 거부합니다. Conventional NPT equilibration은
유지합니다.

| Key | 기본값 | Unit | PLUMED keyword | 효과 |
| --- | --- | --- | --- | --- |
| `minimum_temperature`, `maximum_temperature` | 300.0, 500.0 | K | `ECV_MULTITHERMAL TEMP_MIN`, `TEMP_MAX` | Multithermal target 범위. `temperature`를 포함해야 합니다. |
| `pace_steps` | 500 | step(1 ps) | `OPES_EXPANDED PACE` | `ΔF_n(T)`와 bias update 간격 |
| `state_write_interval_steps` | 50000 | step(100 ps) | `STATE_WSTRIDE` | `opes.state` 쓰기 간격. 위 나누어떨어짐 조건이 있습니다. |

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Conventional equilibration에 적용합니다. |
| `production_ensemble` | `NVT`만 지원 | `NVT` | Production에서 `ntb=1`, `ntp=0`을 사용합니다. |
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
CALC_WORK = true   # OPES_EXPANDED: work done by the bias (flag)
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
| `PLUMED action unavailable: ECV_MULTITHERMAL` 또는 `OPES_EXPANDED` | `opes` module을 넣어 PLUMED를 다시 build합니다. |
| `run.production_ensemble must be NVT` | `production_ensemble = "NVT"`로 두고 새 `WORK_DIR`에서 build합니다. |
| `temperature range must contain the simulation temperature` | `minimum_temperature ≤ temperature ≤ maximum_temperature`로 맞춥니다. |
| `observation_steps * pace_steps (...) must be smaller than the production steps per segment` | `observation_steps`를 줄이거나 segment를 늘립니다. |

공통 error는 [MetaD template README](../README.md)의 문제 해결에 있습니다.

Segment layout, `--segments` option, engine 선택과 실패한 segment의
`DELTAFS`/`opes.state` 복원은 [MetaD template README](../README.md)를 참고합니다.
실행 상태, 실패 후 재실행과 동시 실행 보호는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을
참고합니다.

## English

This template builds a 300–500 K multithermal target from the potential energy
`ene`, and OPES_EXPANDED learns the free-energy offsets of the temperature
states. The physical MD thermostat stays at 300 K while the bias samples the
energy fluctuations of the configured range. The OPES_EXPANDED method is fixed
by this directory and is not a separate config mode.

This is a multithermal expansion. A Hamiltonian expansion needs a separate
Hamiltonian-state definition and engine coupling.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt`. User-facing entry points are in
this directory root; `helpers/` contains internal code called automatically.

### Required inputs and run

`download.sh PDB_ID` retrieves an optional source PDB. It checks the PDB atom
records in a temporary file before replacing the final file. `build.sh` creates
the NPT equilibration and NVT expanded-ensemble inputs from the prepared PDB,
`run.sh` continues the state through the segments, and `anal.py` summarizes the
cumulative output.

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

The first segment creates `DELTAFS` and `opes.state`; later segments continue
with `RESTART` and `STATE_RFILE=opes.state`. PLUMED 2.10 can restart from either
file; this template consistently reads the readable `opes.state` checkpoint and
retains `DELTAFS` for state free-energy estimates and analysis.

### Main outputs

| File | Content |
| --- | --- |
| `work/DELTAFS`, `work/opes.state`, `work/COLVAR` | State free-energy estimates, adaptive state and CVs shared by all segments |
| `work/001/` … | Restart, trajectory and AMBER output per segment |
| `work/analysis/production_summary.tsv` | Energy, expanded-CV and bias ranges plus the generated state count |

An invalid `COLVAR` header or nonfinite values leave previous analysis results
in place.

### Success check and interpretation

After the last segment, `run.sh` prints
`MetaD production segments completed: 1-10 of 10 (...)` and
`Next: python3 anal.py`. Read the number of temperature states from `DELTAFS`.

Reweight observables at temperature `T` with `ene` and `opes.bias` from
`COLVAR`, both in kJ/mol (Invernizzi, Piaggi & Parrinello, *Phys. Rev. X*
10:041034, 2020). The formula is guidance; this template does not implement it.

```text
w_T ∝ exp(β₀ · opes.bias − (β_T − β₀) · ene)
β = 1 / (k_B T), k_B = 0.0083144626 kJ mol⁻¹ K⁻¹, T₀ = temperature
```

Exclude the observation period at the start of segment 1
(`observation_steps × pace_steps`, PLUMED default 100 × 500 steps), where the
bias is zero, and choose `T` only within `minimum_temperature`–
`maximum_temperature`.

### Key parameters

`minimum_temperature` and `maximum_temperature` must contain the base
temperature. `ECV_MULTITHERMAL` builds the state grid automatically.

The automatic temperature grid depends on the potential-energy fluctuations of
the whole system, so explicit-solvent systems may need many temperatures.
Optional `[opes_expanded]` keys set the grid directly. When a key is absent, the
keyword is omitted and PLUMED uses its default.

| Key | PLUMED keyword | Meaning and limits |
| --- | --- | --- |
| `temperature_steps` | `ECV_MULTITHERMAL TEMP_STEPS` | Number of temperatures from `minimum_temperature` to `maximum_temperature`; an integer of at least 2. When absent, PLUMED chooses it from the initial unbiased steps. |
| `observation_steps` | `OPES_EXPANDED OBSERVATION_STEPS` | Length of the unbiased observation before grid initialization, in units of `pace_steps` (PLUMED default 100). A positive integer; `observation_steps * pace_steps` must be smaller than the steps per segment, because `opes.state` is not written until the observation ends. |

PLUMED parsing and runs with these keys are unverified.

`state_write_interval_steps` must be a multiple of `pace_steps` and must divide
the steps per segment (`production_steps / production_segments`), so the last
`opes.state` matches the segment end.

Production supports NVT only. PLUMED 2.10 `ECV_MULTITHERMAL` requires `E+pV` at
fixed pressure, whereas this input uses only `ENERGY`.
`production_ensemble="NPT"` is rejected before build/dry-run and input
generation, and legacy NPT configs are rejected by run and analysis.
Conventional NPT equilibration is retained.

| Key | Default | Unit | PLUMED keyword | Effect |
| --- | --- | --- | --- | --- |
| `minimum_temperature`, `maximum_temperature` | 300.0, 500.0 | K | `ECV_MULTITHERMAL TEMP_MIN`, `TEMP_MAX` | Multithermal target range; must contain `temperature`. |
| `pace_steps` | 500 | step (1 ps) | `OPES_EXPANDED PACE` | `ΔF_n(T)` and bias-update interval |
| `state_write_interval_steps` | 50000 | step (100 ps) | `STATE_WSTRIDE` | `opes.state` write interval, with the divisibility rule above |

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to conventional equilibration. |
| `production_ensemble` | `NVT` only | `NVT` | Uses `ntb=1`, `ntp=0` for production. |
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
CALC_WORK = true   # OPES_EXPANDED: work done by the bias (flag)
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
| `PLUMED action unavailable: ECV_MULTITHERMAL` or `OPES_EXPANDED` | Rebuild PLUMED with the `opes` module. |
| `run.production_ensemble must be NVT` | Set `production_ensemble = "NVT"` and build in a new `WORK_DIR`. |
| `temperature range must contain the simulation temperature` | Keep `minimum_temperature ≤ temperature ≤ maximum_temperature`. |
| `observation_steps * pace_steps (...) must be smaller than the production steps per segment` | Reduce `observation_steps` or lengthen the segments. |

Common errors are listed under Troubleshooting in the
[MetaD template README](../README.md).

See the [MetaD template README](../README.md) for the segment layout, the
`--segments` option, engine selection and restoring `DELTAFS`/`opes.state` after
a failed segment. See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state, reruns
after failure and concurrent-run protection.
