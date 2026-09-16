# LiGaMD3 template

## 한국어

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

Amber 26 `igamd=28` triple boost를 사용합니다. `ligand_mask`와
`receptor_mask`는 residue 이름으로 추정하지 않고 `config.toml`에서 받습니다.
Build 과정에서 두 mask가 atom을 선택하는지, 겹치지 않는지, receptor가
LiGaMD3의 `bgpro2atm`–`edpro2atm`에 필요한 연속 atom 범위인지 검사합니다.

```bash
./build.sh prepared_complex.pdb
./run.sh --dry-run
./run.sh
```

Precharged RESP MOL2와 matching frcmod 경로도 config에서 지정합니다. 이
workflow는 serial `pmemd.cuda`만 지원합니다. Production segment는 MD restart와
`gamd-restart.dat`를 함께 이어받습니다.
`download.sh PDB_ID`는 source complex만 내려받으며 ligand parameter를 만들지
않습니다. `build.sh`는 topology와 GaMD input을 만들고 `run.sh`는 각 stage를
순서대로 실행합니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff19SB`만 지원 | `ff19SB` | Protein parameter를 선택합니다. |
| `ligand_force_field` | `GAFF2`만 지원 | `GAFF2` | Ligand parameter 형식을 결정합니다. |
| `charge_method` | precharged `RESP` MOL2만 지원 | `RESP` | `ligand_mol2`의 RESP charge를 그대로 사용합니다. |
| `water_model` | `OPC`, `TIP3P` | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Conventional equilibration에 적용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NVT` | LiGaMD3 preparation과 production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | `"random"`은 AMBER `ig=-1`, 정수는 고정 seed를 사용합니다. |

Triple-boost LiGaMD3는 이 directory의 고정 method이며 별도 config mode가
아닙니다. `ligand_mask`와 `receptor_mask`는 서로의 역할을 명시하는 system별
selection입니다.

## English

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff19SB` only | `ff19SB` | Selects the protein parameters. |
| `ligand_force_field` | `GAFF2` only | `GAFF2` | Selects the ligand parameter format. |
| `charge_method` | Precharged `RESP` MOL2 only | `RESP` | Uses the RESP charges already present in `ligand_mol2`. |
| `water_model` | `OPC`, `TIP3P` | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to conventional equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NVT` | Sets `ntb` and `ntp` for LiGaMD3 preparation and production. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | `"random"` maps to AMBER `ig=-1`; an integer fixes the seed. |

Triple-boost LiGaMD3 is fixed by this directory and is not a config mode.
`ligand_mask` and `receptor_mask` are system-specific selections that assign
the two roles.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

This template uses the Amber 26 `igamd=28` triple boost. The ligand and receptor
masks are explicit config inputs. The build validates non-empty, non-overlapping
selections and requires the receptor to form the contiguous atom range used by
`bgpro2atm` and `edpro2atm`. Serial `pmemd.cuda` is required.
`download.sh` retrieves only a source complex; `build.sh` creates the system and
GaMD inputs, and `run.sh` propagates the stages while continuing GaMD state.
