# Ratchet MD and umbrella sampling template

## 한국어

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

Ratchet MD(rMD)로 reaction coordinate가 목표 방향으로 증가하는 pathway를
만들고, ordered first-crossing frame을 umbrella window seed로 사용합니다.
rMD trajectory는 seed 생성에만 사용하며 PMF는 US production에서 계산합니다.

```bash
./build.sh prepared.pdb

cd rmd
./run.sh
python3 anal.py

cd ../us
./build.sh
./run.sh
```

`build.sh`는 rMD와 모든 umbrella window가 공유하는 topology와 restart를
만듭니다. `rmd/run.sh`는 tutorial과 같은 minimization, heating,
equilibration, PLUMED ABMD command 순서로 pathway를 생성합니다.
`rmd/anal.py`는 seed restart를 만들고 `us/build.sh`가 `windows.tsv`의
`CENTER_A FORCE_KCAL_MOL_A2` row를 window directory로 변환합니다.
`download.sh PDB_ID`는 RCSB source PDB를 수정하지 않고 `structure/`에
받습니다. Protonation, missing atom과 불필요한 chain은 build 전에 사용자가
정리합니다.

`[umbrella]` atom mask는 각각 한 atom을 선택해야 합니다.
`[ratchet_md] target_distance`는 Å로 입력하고 PLUMED `ABMD TO`의 nm로
변환합니다. `kappa`는 PLUMED ABMD의 ρ 정의를 따르며 일반
harmonic distance force constant와 같은 양이 아닙니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff19SB`만 지원 | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `OPC`, `TIP3P` | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NVT`, `NPT` | `NPT` | Seed와 window equilibration의 `ntb`와 `ntp`를 설정합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Window production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | `"random"`은 AMBER `ig=-1`, 정수는 고정 seed를 사용합니다. |

`windows_file`은 항상 명시적인 window center 목록을 읽습니다. 이 option에는
`auto`/`file` mode 구분이 없습니다. Blank line과 `#`로 시작하는 comment line을
제외한 각 행은 whitespace로 구분한 `CENTER_A FORCE` 두 값이어야 합니다. 두 값은
양수이고 center는 중복 없이 오름차순이어야 합니다. `production_segments`는
현재 `1`만 지원합니다.

## English

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff19SB` only | `ff19SB` | Selects the protein parameters. |
| `water_model` | `OPC`, `TIP3P` | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NVT`, `NPT` | `NPT` | Sets `ntb` and `ntp` for seed and window equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Sets window-production `ntb` and `ntp`. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | `"random"` maps to AMBER `ig=-1`; an integer fixes the seed. |

`windows_file` always supplies an explicit list of window centers. It does not
have separate `auto` and `file` modes. After blank lines and full-line `#`
comments are skipped, each row must contain two whitespace-separated values,
`CENTER_A FORCE`. Both values must be positive, and centers must be unique and
in increasing order. `production_segments` currently supports only `1`.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

Ratchet MD generates a target-directed pathway along the configured distance.
Ordered first-crossing frames seed the umbrella windows; only the umbrella
production trajectories are used for the PMF.

The shared `build.sh` creates one topology and restart for rMD and every
window. `rmd/run.sh` follows the tutorial minimization, heating, equilibration,
and PLUMED ABMD command structure. `rmd/anal.py` extracts seed restarts, and
`us/build.sh` converts the two-column `windows.tsv` table into window
directories before `us/run.sh` propagates them.
`download.sh PDB_ID` retrieves an unmodified RCSB PDB into `structure/`;
protonation, missing atoms, and unwanted chains remain user preparation steps.

Each umbrella atom mask must select one atom. `target_distance` is entered in
Å and converted to the PLUMED `ABMD TO` value in nm. `kappa` follows the
PLUMED ABMD ρ definition and is not an ordinary harmonic-distance force
constant.
