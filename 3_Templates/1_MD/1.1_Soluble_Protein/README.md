# Soluble-protein MD template / 수용성 단백질 MD template

## 한국어

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

사용자가 준비한 protein PDB를 선택한 protein–water compatibility pair의
explicit solvent에서 계산합니다.
기본 config는 14 Å solute-to-box-edge distance, 0.15 M salt, 500 ps heating,
1 ns NPT equilibration과 10×10 ns production을 사용합니다.

```bash
./download.sh 1UBQ
# Review and process structure/1UBQ.pdb before building.
./build.sh structure/1UBQ.pdb
./run.sh --dry-run
./run.sh
```

`download.sh`는 PDB를 수정하지 않습니다. Protonation, alternate location,
missing residue/atom, crystal water와 biological assembly를 사용자가 결정합니다.
`build.sh`는 먼저 water 수를 세어 150 mM에 가까운 salt formula-unit 수를 계산한 뒤
neutralization과 salt addition을 포함한 최종 topology를 만듭니다.

`config.toml`의 계산 길이는 MD steps로 입력합니다. 2 fs timestep에서 기본
heating 250,000 steps는 500 ps, equilibration 500,000 steps는 1 ns,
production 50,000,000 steps는 100 ns입니다. 실제 적용값과 salt formula-unit 수는
`work/resolved_config.toml`에서 확인합니다.

Production segment가 하나이면 output을 `work/`에 직접 저장합니다. 여러 개이면
`work/001`, `work/002` 순서로 저장합니다.
Preproduction partial output은 해당 stage를 다시 실행하지만 production partial
output은 자동 삭제하지 않습니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NVT`, `NPT` | `NPT` | Equilibration의 `ntb`와 `ntp`를 설정합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | `"random"`은 AMBER `ig=-1`, 정수는 고정 seed를 사용합니다. |

## English

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NVT`, `NPT` | `NPT` | Sets equilibration `ntb` and `ntp`. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Sets production `ntb` and `ntp`. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | `"random"` maps to AMBER `ig=-1`; an integer fixes the seed. |

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

This template runs a user-prepared protein PDB with the selected protein–water
compatibility pair. The default uses a 14 Å solute-to-box-edge distance, approximately
0.15 M salt, 500 ps heating, 1 ns NPT equilibration, and ten 10 ns production
segments.

`download.sh` does not modify the PDB. Review protonation, alternate locations,
missing atoms or residues, crystallographic waters, and the biological assembly
before calling `build.sh`. The build first counts waters, estimates the number
of salt formula units, and then generates the neutralized final topology.

Run lengths in `config.toml` are specified as MD steps. At the default 2 fs
timestep, 250,000 heating steps are 500 ps, 500,000 equilibration steps are
1 ns, and 50,000,000 production steps are 100 ns. Resolved values are written
to `work/resolved_config.toml`. A single production segment is stored directly
under `work/`; multiple segments use `work/001`, `work/002`, and so on.
