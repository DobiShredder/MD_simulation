# Pep-GaMD template

## 한국어

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

`igamd=15`로 peptide potential과 나머지 system potential에 dual boost를
적용합니다. `peptide_mask`는 `config.toml`에서 지정하며 build가 실제 atom
selection을 확인합니다.

```bash
./build.sh prepared_complex.pdb
./run.sh --dry-run
./run.sh
```

Amber 26 serial `pmemd.cuda`가 필요합니다. `gamd_prepare.gamd.rst`에서 시작한
GaMD state는 각 production segment의 `production.gamd.rst`로 이어집니다.
`download.sh PDB_ID`는 source complex를 내려받고, `build.sh`는 peptide mask를
검증한 뒤 topology와 input을 생성하며, `run.sh`는 segmented GaMD를 실행합니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein과 peptide parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Conventional equilibration에 적용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NVT` | Pep-GaMD preparation과 production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | `"random"`은 AMBER `ig=-1`, 정수는 고정 seed를 사용합니다. |

Peptide-selective boost는 이 directory의 고정 method이며 별도 config mode가
아닙니다. `peptide_mask`가 boost 대상 peptide를 지정합니다.

## English

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects protein and peptide parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to conventional equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NVT` | Sets `ntb` and `ntp` for Pep-GaMD preparation and production. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | `"random"` maps to AMBER `ig=-1`; an integer fixes the seed. |

The peptide-selective boost is fixed by this directory and is not a config
mode. `peptide_mask` selects the peptide to boost.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

This template uses `igamd=15` to boost peptide potential energy and the
remaining system potential. Set `peptide_mask` in `config.toml`; the build
verifies that it selects atoms. Amber 26 serial `pmemd.cuda` is required, and
each production segment continues both coordinate and GaMD state. `download.sh`
retrieves a source complex, `build.sh` validates the selection and writes
inputs, and `run.sh` executes the segmented workflow.
