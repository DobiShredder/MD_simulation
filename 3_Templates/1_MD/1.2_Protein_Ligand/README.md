# Protein–ligand MD template / Protein–ligand MD template

## 한국어

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

사용자가 준비한 complex PDB와 RESP charge가 포함된 ligand MOL2로 conventional
MD를 구성합니다. Protein은 ff19SB, ligand는 GAFF2, solvent는 OPC를 사용합니다.

`config.toml`에서 다음 경로와 chemical identity를 먼저 수정합니다.

```toml
ligand_residue_name = "LIG"
ligand_net_charge = 0
charge_method = "RESP"
ligand_mol2 = "inputs/ligand.mol2"
ligand_frcmod = "inputs/ligand.frcmod"
```

MOL2에는 RESP charge와 GAFF2 atom type이 이미 들어 있어야 합니다. 이 template는
Gaussian/ESP/RESP 계산이나 atom mapping을 자동으로 만들지 않습니다. Build는
MOL2 residue name과 net charge가 config 및 complex PDB와 일치하는지 검사합니다.

```bash
./download.sh 3HTB
# Prepare the complex PDB and place reviewed ligand parameters under inputs/.
./build.sh structure/3HTB.pdb
./run.sh --dry-run
./run.sh
```

기본값은 14 Å OPC box, 0.15 M salt, 250,000-step heating, 500,000-step
equilibration과 10×5,000,000-step production입니다. Segment가 여러 개이면
`work/001`부터 저장하며 production partial output은 자동 삭제하지 않습니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff19SB`만 지원 | `ff19SB` | Protein parameter를 선택합니다. |
| `ligand_force_field` | `GAFF2`만 지원 | `GAFF2` | Ligand parameter 형식을 결정합니다. |
| `charge_method` | precharged `RESP` MOL2만 지원 | `RESP` | `ligand_mol2`의 RESP charge를 그대로 사용합니다. |
| `water_model` | `OPC`, `TIP3P` | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Equilibration의 pressure coupling을 활성화합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | `"random"`은 AMBER `ig=-1`, 정수는 고정 seed를 사용합니다. |

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
| `equilibration_ensemble` | `NPT` only | `NPT` | Enables pressure coupling during equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Sets production `ntb` and `ntp`. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | `"random"` maps to AMBER `ig=-1`; an integer fixes the seed. |

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

This template builds conventional protein–ligand MD from a reviewed complex
PDB and a ligand MOL2 containing precomputed RESP charges and GAFF2 atom types.
Set the ligand residue, integer net charge, MOL2 path, and frcmod path in
`config.toml`. The build checks the MOL2 residue name and total charge against
the config and verifies that the complex PDB contains that residue.

The template does not perform quantum chemistry, RESP fitting, or atom mapping.
Its default run uses a 14 Å OPC box, approximately 0.15 M salt, 500 ps heating,
1 ns equilibration, and ten 10 ns production segments at a 2 fs timestep.
