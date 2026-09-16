# WT-MetaD template

## 한국어

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Conventional equilibration에 적용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | WT-MetaD production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | `"random"`은 AMBER `ig=-1`, 정수는 고정 seed를 사용합니다. |

WT-MetaD 방식은 이 directory에서 고정되며 별도 config mode가 아닙니다.

`cv.dat`에 정의한 CV를 방문할 때마다 Gaussian hill을 추가합니다. 이미 bias가
쌓인 위치에서는 `BIASFACTOR=10`에 따라 새 hill이 작아져 conventional MetaD보다
완만하게 free-energy surface를 채웁니다.

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

`config.toml`의 `collective_variable.arguments`는 `cv.dat`의 label과 같아야 합니다.
기본 φ/ψ atom 번호는 capped alanine 예시이므로 topology에 맞게 바꿉니다.
`sigma`, `grid_min`, `grid_max`와 `grid_bins`는 CV 수와 같은 길이여야 합니다.
기본 hill은 1.2 kJ/mol, `PACE=500`, `BIASFACTOR=10`입니다.

`build.sh`는 configured protein/water topology와 preproduction input을 만듭니다. `run.sh`는
500 ps heating과 1 ns NPT equilibration 뒤 10×10 ns production을 실행합니다.
첫 segment는 새 `HILLS`를 만들고 이후 segment는 `RESTART`로 같은 file에
추가합니다. Partial production segment는 자동 삭제하지 않습니다.
`download.sh PDB_ID`는 optional source PDB를 수정하지 않고 내려받습니다.

`anal.py`는 모든 segment의 누적 `COLVAR`와 `HILLS`를 읽습니다. 기본적으로
`plumed sum_hills`를 실행하며 `--skip-fes`로 diagnostic TSV만 만들 수 있습니다.
PLUMED의 기본 unit인 energy kJ/mol, length nm, time ps를 사용합니다.

## English

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to conventional equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Sets WT-MetaD production `ntb` and `ntp`. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | `"random"` maps to AMBER `ig=-1`; an integer fixes the seed. |

The WT-MetaD method is fixed by this directory and is not a separate config
mode.

WT-MetaD deposits Gaussian hills along the CVs defined in `cv.dat`. The current
bias reduces subsequent hill heights through `BIASFACTOR=10`. CV labels in
`collective_variable.arguments` must match `cv.dat`; the supplied φ/ψ atom
numbers are only a capped-alanine example.

The defaults use 1.2 kJ/mol hills every 500 steps and ten 10 ns segments. The
first segment creates `HILLS`; later segments use `RESTART` and append to the
same bias history. Analysis summarizes the cumulative `COLVAR` and runs
`plumed sum_hills` unless `--skip-fes` is selected. `download.sh` can retrieve
an unmodified source PDB, while `build.sh`, `run.sh`, and `anal.py` create,
propagate, and analyze the configured workflow.
