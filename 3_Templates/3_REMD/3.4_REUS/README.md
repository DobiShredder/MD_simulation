# REUS template

## 한국어

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

Reaction coordinate의 각 umbrella center를 replica state로 두고 AMBER
multidimensional replica exchange로 인접 state를 교환합니다. `windows.tsv`에는
center를 Å 단위로 한 줄에 하나씩 적고 `config.toml`에는 두 AMBER atom mask,
force constant와 exchange interval을 지정합니다.

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
```

Build는 두 mask가 각각 한 atom을 선택하는지 확인하고 `work/states.tsv`와
window directory를 만듭니다. AMBER에서는 `nstlim`이 exchange 사이 MD steps,
`numexchg`가 segment의 exchange 횟수입니다. MPI process 수는 window 수와 같아야
하며 `MPI_PROCESSES`, `MPI_OPTIONS`로 실행 환경을 조정합니다.
`download.sh PDB_ID`는 source PDB를 내려받고 `run.sh`는 preproduction과
multidimensional replica exchange를 순서대로 실행합니다.

기본 production은 window당 200 ns입니다. 2 fs timestep과 1000-step exchange
interval에서 input은 `nstlim=1000`, `numexchg=100000`으로 생성됩니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff19SB`만 지원 | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `OPC`, `TIP3P` | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Window equilibration에 적용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Exchange production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | Window별 seed를 무작위로 만들거나 정수에서 파생합니다. |

`windows_file`은 항상 명시적인 center 목록을 읽으며 `auto`/`file` mode가
아닙니다. Blank line과 `#`로 시작하는 comment line을 제외하고 각 행에는 center
하나만 적습니다. Center 목록은 비어 있지 않고 중복 없이 오름차순이어야 합니다.
각 행이 한 exchange state가 되고 최종 mapping은 `work/states.tsv`에 기록됩니다.

## English

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff19SB` only | `ff19SB` | Selects the protein parameters. |
| `water_model` | `OPC`, `TIP3P` | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to window equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Sets exchange-production `ntb` and `ntp`. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | Creates random window seeds or derives them from the integer. |

`windows_file` always supplies an explicit center list and is not an
`auto`/`file` mode. After blank lines and full-line `#` comments are skipped,
each row must contain exactly one center. The list must be nonempty, unique,
and increasing. Each row becomes one exchange state, and the final mapping is
written to `work/states.tsv`.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

Each umbrella center is a replica state. Amber multidimensional replica
exchange swaps neighboring states while every replica samples its harmonic
window. The build resolves two one-atom AMBER masks and writes dynamic states.
`download.sh` retrieves a source PDB, and `run.sh` executes preproduction and
multidimensional replica exchange.
Amber uses `nstlim` for steps between attempts and `numexchg` for attempts per
segment; the MPI process count must equal the number of windows. The default is
200 ns per window, rendered as `nstlim=1000` and `numexchg=100000` at 2 fs.
