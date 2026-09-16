# GaMD template

## 한국어

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

`igamd=3`으로 total potential과 dihedral energy에 dual boost를 적용합니다.
`config.toml`의 200,000-step preparation, 1,000,000-step statistics 구간을
conventional MD와 boost equilibration에 각각 사용합니다. `sigma0P`와
`sigma0D`의 기본값은 6 kcal/mol입니다.

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
```

| File | 역할 |
| --- | --- |
| `download.sh` | 선택한 source PDB 다운로드 |
| `config.toml` | build, MD 길이와 GaMD 통계 parameter |
| `build.sh` | configured protein/water topology와 GaMD input 생성 |
| `run.sh` | minimization부터 segmented production까지 실행 |
| `generate_gamd_inputs.py` | `gamd_prepare.in`과 `production.in` 생성; `build.sh`가 자동 호출 |

Production이 여러 segment이면 `work/001`, `work/002`, ...에 저장합니다.
완료된 segment는 marker와 output이 모두 있을 때 건너뜁니다. Partial production
또는 GaMD state는 덮어쓰지 않습니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Conventional equilibration에 적용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NVT` | GaMD preparation과 production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | `"random"`은 AMBER `ig=-1`, 정수는 고정 seed를 사용합니다. |

GaMD boost 종류는 이 directory에서 dual boost로 고정되어 있으며 별도 config
mode가 아닙니다.

## English

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to conventional equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NVT` | Sets `ntb` and `ntp` for GaMD preparation and production. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | `"random"` maps to AMBER `ig=-1`; an integer fixes the seed. |

The GaMD boost type is fixed to dual boost in this directory and is not a
config mode.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

This template applies the `igamd=3` dual boost to total potential and dihedral
energies. Build a reviewed PDB, inspect the generated inputs and dry run, then
start the calculation. `download.sh` retrieves an unmodified source PDB,
`build.sh` creates the solvated system and inputs, and `run.sh` executes the
stages. Multi-segment production uses `work/001`, `work/002`,
and so on while preserving both MD and GaMD restart state.
