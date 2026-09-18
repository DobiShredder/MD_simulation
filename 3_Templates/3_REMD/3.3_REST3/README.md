# REST3 template

## 한국어

이 directory의 runtime code는 별도로 복사해 사용할 수 있습니다. GROMACS를
build할 때는 상위 `patches/` directory의 correction도 함께 사용합니다. Python
dependency는 복사한 directory의 `requirements.txt`를 사용해 설치합니다.

REST2 scaling에 κ schedule을 추가합니다. 기본 schedule은 357 K까지 κ=1.0을
유지하고 450 K에서 1.020이 되도록 선형 보간합니다. 이 값은 universal default가
아니며 IDP와 force-field/water 조합별 pilot simulation에서 compactness와 exchange를
확인해야 합니다. κ 효과는 temperature predictor에 포함되지 않습니다.

```bash
./download.sh 1UBQ
./build.sh structure/1UBQ.pdb
replicas=$(awk 'NR > 1 {count++} END {print count + 0}' work/states.tsv)
./run.sh --cpus "$replicas" --gpus 1
```

명시적인 κ 목록은 `[rest3_kappa]`의 `mode = "file"`과 `file`로 입력합니다.
Temperature와 κ 목록의 길이는 같아야 합니다. Runtime에는 REST2와 같은 patched
GROMACS/PLUMED HREX build와 상위 directory의
[`HREX_WORKLOAD_FIX_1` correction](../patches/gromacs-2024.3-plumed-2.10-hrex-energy.patch)이
필요합니다. 적용 순서와 검증 범위는 [상위 README](../README.md)에 있습니다.
`download.sh`는 source PDB와 함께
검증된 `repex-topology-parser` 0.2.2 source를 내려받습니다.
기본 OPC 설정에서는 `kappa_atom_names=['OW']`가 water oxygen type을 선택합니다.
`verify_rest3.py`는 O/H1/H2/EP의 type·charge·mass와 solvent interaction이
replica 사이에서 보존되는지 검사합니다. `water_model = "TIP3P"` compatibility
option도 유지합니다.
각 replica의 preproduction은 tutorial과 같은 minimization과 NPT equilibration
순서이며 별도 heating stage는 사용하지 않습니다. 첫 `grompp` 전에는 ParmEd가
출력한 긴 CMAP 실수를 GROMACS 2024.x가 읽을 수 있는 정밀도로 정규화합니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 REST3 water atom type을 함께 결정합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `tempered_region` | `solute`만 지원 | `solute` | Water와 ion을 제외한 전체 solute를 tempering합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Replica equilibration에 적용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | GROMACS production pressure coupling을 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 LINCS를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | State별 seed를 무작위로 만들거나 정수에서 파생합니다. |

| Mode option | Mode | 사용하는 설정 | 무시하는 설정과 결과 |
| --- | --- | --- | --- |
| `temperature_mode` | `auto` (기본값) | `minimum_temperature`, `maximum_temperature`, `target_exchange_probability`, `generator_tolerance` | `temperature_file`을 무시하고 tempered-solute atom 수로 ladder를 계산합니다. |
| `temperature_mode` | `file` | `temperature_file` | Auto 설정을 무시하고 file temperature에서 `lambda_pp`와 `lambda_pw`를 계산합니다. |
| `rest3_kappa.mode` | `linear` (기본값) | `onset_temperature`, `maximum_temperature`, `maximum_kappa` | `file`을 무시하고 onset 이하 1.0, 이후 선형 κ를 계산합니다. |
| `rest3_kappa.mode` | `file` | `file` | Linear 설정을 무시하고 κ 목록을 순서대로 사용합니다. |

Temperature와 κ file은 사용자가 생성해야 합니다. 두 file 모두 공백, comma,
semicolon, `|`를 구분자로 받고 `#` comment를 허용합니다. Temperature는 둘 이상의
양수여야 하고 중복 없이 오름차순이며 첫 값은 `run.temperature`와 같아야 합니다.
κ 개수는 temperature state 수와 같아야 하고 모든 κ는 1.0 이상이어야 합니다.
두 mode를 조합할 수 있으며 최종 temperature, λ, κ와 seed는
`work/states.tsv`에서 확인합니다.

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
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects both LEaP water and REST3 water atom types. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `tempered_region` | `solute` only | `solute` | Tempers the complete non-water, non-ion solute. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to replica equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Selects GROMACS production pressure coupling. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies LINCS to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | Creates random state seeds or derives them from the integer. |

| Mode option | Mode | Settings used | Ignored settings and result |
| --- | --- | --- | --- |
| `temperature_mode` | `auto` (default) | `minimum_temperature`, `maximum_temperature`, `target_exchange_probability`, `generator_tolerance` | Ignores `temperature_file` and predicts a ladder from tempered-solute atoms. |
| `temperature_mode` | `file` | `temperature_file` | Ignores auto settings and computes `lambda_pp` and `lambda_pw` from file temperatures. |
| `rest3_kappa.mode` | `linear` (default) | `onset_temperature`, `maximum_temperature`, `maximum_kappa` | Ignores `file`; κ is 1.0 through onset and then increases linearly. |
| `rest3_kappa.mode` | `file` | `file` | Ignores linear settings and uses the κ list in order. |

The user must create the temperature and κ files. Both accept whitespace,
commas, semicolons, and `|` as separators and allow `#` comments. Temperatures
must contain at least two unique, increasing positive values, with the first
equal to `run.temperature`. The κ count must equal the temperature-state count,
and every κ must be at least 1.0. The two modes can be combined; final
temperatures, λ values, κ values, and seeds are recorded in `work/states.tsv`.

This directory's runtime code can be copied on its own. Keep the parent
`patches/` correction available when building GROMACS. Install the Python
dependencies from the local `requirements.txt` after copying it.

Production requires the same patched GROMACS/PLUMED HREX build as REST2 and
the [`HREX_WORKLOAD_FIX_1` correction](../patches/gromacs-2024.3-plumed-2.10-hrex-energy.patch).
See the [parent README](../README.md) for application steps and validation
scope.

REST3 adds a κ schedule to REST2 scaling. The default keeps κ at 1.0 through
357 K and linearly reaches 1.020 at 450 K. This is not a universal value; assess
compactness and exchange in a system- and force-field-specific pilot run. The
temperature predictor does not model the κ correction. File mode accepts an
explicit κ list with one value per state. Replica preproduction uses the same
minimization-to-NPT-equilibration sequence as the fixed tutorial.
With the default OPC model, `kappa_atom_names=['OW']` selects the water oxygen
type. `verify_rest3.py` checks preservation of O/H1/H2/EP atom records and
solvent interactions across replicas. The optional `water_model = "TIP3P"`
compatibility path remains available. Before the first `grompp`, the build
normalizes long ParmEd-formatted CMAP numbers to a precision accepted by
GROMACS 2024.x.
