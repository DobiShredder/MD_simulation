# REST2 template

## 한국어

이 directory의 runtime code는 별도로 복사해 사용할 수 있습니다. GROMACS를
build할 때는 상위 `patches/` directory의 correction도 함께 사용합니다. Python
dependency는 복사한 directory의 `requirements.txt`를 사용해 설치합니다.

Water와 ion을 제외한 solute 전체를 tempered region으로 사용합니다. Temperature
predictor에는 solute atom 수와 water 0을 전달하고, 생성한 effective temperature
`T_i`에서 `lambda_pp=T_0/T_i`, `lambda_pw=sqrt(lambda_pp)`를 계산합니다.

```bash
./download.sh 1UBQ
./build.sh structure/1UBQ.pdb
replicas=$(awk 'NR > 1 {count++} END {print count + 0}' work/states.tsv)
./run.sh --cpus "$replicas" --gpus 1
```

Production에는 PLUMED 2.10이 patch된 GROMACS 2024.3/2024.6 external-MPI build와
상위 directory의
[`HREX_WORKLOAD_FIX_1` correction](../patches/gromacs-2024.3-plumed-2.10-hrex-energy.patch)이
필요합니다. 적용 순서와 검증 범위는 [상위 README](../README.md)에 있습니다.
`run.sh`는 시작 전에 이 marker와 `-hrex` 지원을 검사합니다. Predictor의 목표
probability는 실제 HREX acceptance를 보장하지 않으므로 짧은 pilot run에서
`Repl average probabilities`를 확인합니다.
각 replica는 tutorial과 같이 minimization 뒤 300 K velocity를 생성하는 NPT
equilibration을 실행합니다. 별도 heating stage는 두지 않습니다. Build는
scale 1 topology와 원본 topology의 single-frame potential energy 차이가
0.1 kJ/mol 이하인지도 검사합니다. 첫 `grompp` 전에는 ParmEd가 출력한 긴
CMAP 실수를 GROMACS 2024.x가 읽을 수 있는 정밀도로 정규화합니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `tempered_region` | `solute`만 지원 | `solute` | Water와 ion을 제외한 전체 solute를 tempering합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Replica equilibration에 적용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | GROMACS production pressure coupling을 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 LINCS를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | State별 seed를 무작위로 만들거나 정수에서 파생합니다. |

| `temperature_mode` | 사용하는 설정 | 무시하는 설정 | 생성 결과 |
| --- | --- | --- | --- |
| `auto` (기본값) | `minimum_temperature`, `maximum_temperature`, `target_exchange_probability`, `generator_tolerance` | `temperature_file` | Tempered solute atom 수와 water 0으로 ladder를 계산합니다. |
| `file` | `temperature_file` | Auto ladder 설정 | File temperature에서 `lambda_pp=T0/T`, `lambda_pw=sqrt(lambda_pp)`를 계산합니다. |

Temperature file은 사용자가 생성해야 합니다. 구분자는 공백, comma, semicolon,
`|`이며 `#` 뒤는 comment입니다. 값은 양수이고 중복 없이 오름차순이어야 하며,
둘 이상이어야 하고 첫 값은 `run.temperature`와 같아야 합니다. 적용된 temperature,
λ와 seed는 `work/states.tsv`에 기록됩니다.

`maxwarn`은 public config option이 아닙니다. `grompp_utils.bash`는 `grompp`를
먼저 warning 우회 없이 실행합니다. 변환된 topology의 남은 전하가 ±0.01 e
이내이고 `System has non-zero total charge` warning 하나만 있을 때만
내부적으로 `-maxwarn 1`로 다시
실행합니다. 다른 warning은 해당 `*.grompp.log`를 남기고 계산을 중단합니다.

## English

`maxwarn` is not a public configuration option. `grompp_utils.bash` first runs
`grompp` without a warning override and retries it with `-maxwarn 1` only when the
converted topology has a residual charge within ±0.01 e and the log contains
exactly one `System has non-zero total charge` warning. Any other warning stops
the workflow and remains in the corresponding `*.grompp.log`.

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `tempered_region` | `solute` only | `solute` | Tempers the complete non-water, non-ion solute. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to replica equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Selects GROMACS production pressure coupling. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies LINCS to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | Creates random state seeds or derives them from the integer. |

| `temperature_mode` | Settings used | Settings ignored | Result |
| --- | --- | --- | --- |
| `auto` (default) | `minimum_temperature`, `maximum_temperature`, `target_exchange_probability`, `generator_tolerance` | `temperature_file` | Predicts the ladder from tempered-solute atoms and zero waters. |
| `file` | `temperature_file` | Auto-ladder settings | Computes `lambda_pp=T0/T` and `lambda_pw=sqrt(lambda_pp)` from the file temperatures. |

The user must create the temperature file. It accepts whitespace, commas,
semicolons, and `|` as separators; text after `#` is a comment. It must contain
at least two unique, increasing positive values, and its first value must equal
`run.temperature`. Applied temperatures, λ values, and seeds are written to
`work/states.tsv`.

This directory's runtime code can be copied on its own. Keep the parent
`patches/` correction available when building GROMACS. Install the Python
dependencies from the local `requirements.txt` after copying it.

The complete non-water, non-ion solute is the tempered region. The offline
predictor receives the solute atom count and zero waters, then the build derives
`lambda_pp=T_0/T_i` and `lambda_pw=sqrt(lambda_pp)` for every effective
temperature. Production requires the patched PLUMED 2.10 HREX integration and
the [`HREX_WORKLOAD_FIX_1` correction](../patches/gromacs-2024.3-plumed-2.10-hrex-energy.patch).
See the [parent README](../README.md) for application steps and validation
scope. Preproduction follows the
tutorial's minimization-to-NPT-equilibration sequence, and the build checks
scale-one energy identity with a 0.1 kJ/mol tolerance. Before the first
`grompp`, it normalizes long ParmEd-formatted CMAP numbers to a precision
accepted by GROMACS 2024.x.
