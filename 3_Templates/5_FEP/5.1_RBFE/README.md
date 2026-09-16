# RBFE template

## 한국어

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

Ligand A에서 ligand B로 변환하는 dual-topology AMBER RBFE window를 complex와
solvent environment에 각각 만듭니다. `build.sh`에는 ligand를 제외한 reviewed
protein PDB를 전달합니다. 서로 같은 coordinate frame에 배치한 precharged MOL2,
matching frcmod와 one-to-one `atom_mapping.tsv`는 `config.toml`에서 지정합니다.

```bash
./build.sh prepared_protein.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

기본 lambda는 0.0–1.0의 11개 state이며 restraint stage는 없습니다. 각 window는
250,000-step heating, 500,000-step equilibration과 10,000,000-step production을
실행합니다. `ifmbar=1`, `bar_intervall=5000`으로 cross-state energy를 기록합니다.
Build는 두 ligand mask가 비어 있지 않고 겹치지 않는지, mapping atom 이름이
각 ligand에 존재하며 one-to-one인지 검사합니다.

Production 일부만 존재하면 자동으로 덮어쓰지 않습니다. `anal.py`는 완료 marker가
있는 모든 production output을 사용하며 FE-ToolKit의
`edgembar-amber2dats.py`와 `edgembar`가 필요합니다.
`download.sh PDB_ID`는 optional source protein PDB를 내려받습니다. `build.sh`는
두 environment와 lambda window를 생성하고, `run.sh`는 window별 stage를
실행하며, `anal.py`는 MBAR free energy와 overlap을 계산합니다.

### Config 선택값

| Option | 현재 지원값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `ligand_force_field` | `GAFF2`만 지원 | `GAFF2` | 두 ligand의 parameter 형식을 결정합니다. |
| `charge_method` | precharged `RESP` MOL2만 지원 | `RESP` | 두 MOL2의 RESP charge를 그대로 사용합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Complex와 solvent leg의 water model을 선택합니다. |
| `box_shape` | `rectangular`만 실제 적용 | `rectangular` | FEP builder는 두 leg에 `solvatebox`를 사용합니다. |
| `salt_type` | `NaCl`만 실제 적용 | `NaCl` | FEP builder는 `Na+`와 `Cl-`를 기록합니다. |
| `equilibration_ensemble` | `NVT`, `NPT` | `NPT` | Generated equilibration input의 `ntb`와 `ntp`를 설정합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Generated production input의 `ntb`와 `ntp`를 설정합니다. |
| `random_seed` | 현재 config override 미적용 | `"random"` | Window seed는 `51000 + global window index`로 생성됩니다. |

`lambda_values`는 0.0과 1.0을 포함하는 중복 없는 오름차순 list를 직접
지정합니다. Auto/file mode는 없으며, 각 값이 complex와 solvent의 한 window가
되어 `work/states.tsv`에 기록됩니다. `production_segments`는 현재 `1`만
지원합니다.

## English

### Config choices

| Option | Current support | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `ligand_force_field` | `GAFF2` only | `GAFF2` | Selects the parameter format for both ligands. |
| `charge_method` | Precharged `RESP` MOL2 only | `RESP` | Uses the RESP charges already present in both MOL2 files. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects the water model for complex and solvent legs. |
| `box_shape` | Only `rectangular` is applied | `rectangular` | The FEP builder uses `solvatebox` for both legs. |
| `salt_type` | Only `NaCl` is applied | `NaCl` | The FEP builder writes `Na+` and `Cl-`. |
| `equilibration_ensemble` | `NVT`, `NPT` | `NPT` | Sets `ntb` and `ntp` in generated equilibration input. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Sets `ntb` and `ntp` in generated production input. |
| `random_seed` | Config override is not currently applied | `"random"` | Window seeds are `51000 + global window index`. |

`lambda_values` is an explicit, unique, increasing list spanning 0.0 to 1.0.
It has no auto/file mode. Each value creates one complex and one solvent window
recorded in `work/states.tsv`. `production_segments` currently supports only
`1`.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

This dual-topology Amber RBFE template creates complex and solvent windows for
ligand A to ligand B. Pass a ligand-free reviewed protein PDB to `build.sh` and
configure aligned precharged MOL2 files, matching frcmod files, two ligand
masks, and a one-to-one atom-name map. The default schedule contains 11 states;
each window runs 10,000,000 production steps and records cross-state energies
with `ifmbar`. `download.sh` can retrieve a source protein PDB, `build.sh`
creates both environments and their windows, `run.sh` executes them, and
`anal.py` estimates MBAR free energy and overlap. Partial production is not
overwritten automatically. The analysis requires FE-ToolKit
`edgembar-amber2dats.py` and `edgembar` on `PATH`.
