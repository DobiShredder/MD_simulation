# T-REMD template

## 한국어

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

사용자가 준비한 protein PDB로 AMBER temperature replica exchange를 구성합니다.
`build.sh`는 configured protein/water system을 만든 뒤 topology의 solute/ion atom 수와 water
molecule 수를 읽어 300–450 K ladder를 자동 생성합니다. 기본 목표 neighboring
exchange probability는 0.20이며 예측값은 initial schedule을 정하는 근사치입니다.

```bash
./download.sh 1UBQ
./build.sh structure/1UBQ.pdb
./run.sh --dry-run
./run.sh
```

`pmemd.cuda`가 각 replica의 minimization, heating과 equilibration을 실행합니다.
Production은 replica 수와 같은 수의 MPI process에서 `pmemd.cuda.MPI -rem 1`로
실행합니다. 실제 replica 수는 `work/states.tsv`에서 확인합니다. MPI process의
node와 GPU 배치는 `MPI_OPTIONS`와 cluster scheduler에서 설정합니다.

`temperature_mode = "file"`을 쓰면 `temperature_file`의 값을 그대로 사용합니다.
Comma, semicolon, vertical bar와 whitespace를 구분자로 받습니다. Generated
input과 적용값은 `work/resolved_config.toml`에 기록됩니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | 각 physical-temperature replica의 equilibration에 적용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Replica production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | State별 seed를 무작위로 만들거나 정수에서 재현성 있게 파생합니다. |

| `temperature_mode` | 사용하는 설정 | 무시하는 설정 | 생성 결과 |
| --- | --- | --- | --- |
| `auto` (기본값) | `minimum_temperature`, `maximum_temperature`, `target_exchange_probability`, `generator_tolerance` | `temperature_file` | 전체 solvated system을 predictor에 넣어 `work/states.tsv`를 생성합니다. |
| `file` | `temperature_file` | Auto ladder 설정 | File 값을 순서대로 `work/states.tsv`에 기록합니다. |

Temperature file은 사용자가 생성해야 합니다. 공백, comma, semicolon, `|`를
구분자로 사용할 수 있고 `#` 뒤는 comment입니다. 값은 양수이고 중복 없이
오름차순이어야 하며, 둘 이상이어야 하고 첫 값은 `run.temperature`와 같아야
합니다. `work/states.tsv`가 실제 replica schedule입니다.

## English

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to equilibration at each physical temperature. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Sets replica-production `ntb` and `ntp`. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | Creates random state seeds or derives reproducible seeds from the integer. |

| `temperature_mode` | Settings used | Settings ignored | Result |
| --- | --- | --- | --- |
| `auto` (default) | `minimum_temperature`, `maximum_temperature`, `target_exchange_probability`, `generator_tolerance` | `temperature_file` | Runs the predictor on the full solvated system and writes `work/states.tsv`. |
| `file` | `temperature_file` | Auto-ladder settings | Copies the file values in order into `work/states.tsv`. |

The user must create the temperature file. It accepts whitespace, commas,
semicolons, and `|` as separators; text after `#` is a comment. It must contain
at least two unique, increasing positive values, and its first value must equal
`run.temperature`. `work/states.tsv` is the applied replica schedule.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

This template builds AMBER temperature replica exchange from a user-prepared
protein PDB. In automatic mode, the configured protein/water topology supplies solute/ion atom
and water-molecule counts to the offline temperature predictor. The default
range is 300–450 K with a target neighboring exchange probability of 0.20.

`pmemd.cuda` runs preproduction for each replica. Production uses
`pmemd.cuda.MPI -rem 1` with one MPI process per replica; process and GPU
placement remain scheduler settings. The generated replica count and
temperatures are recorded in `work/states.tsv`. File mode accepts comma,
semicolon, vertical-bar, or whitespace-separated temperatures.
