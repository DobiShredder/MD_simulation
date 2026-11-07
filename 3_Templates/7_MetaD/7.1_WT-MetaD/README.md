# WT-MetaD template

## 한국어

`cv.dat`에 정의한 CV를 방문할 때마다 Gaussian hill을 추가합니다. 이미 bias가
쌓인 위치에서는 `BIASFACTOR=10`에 따라 새 hill이 작아져 conventional MetaD보다
완만하게 free-energy surface를 채웁니다. WT-MetaD 방식은 이 directory에서
고정되며 별도 config mode가 아닙니다.

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`로 설치합니다. 사용자가 직접 실행하는 파일은 이
directory의 root에 있고, `helpers/`는 자동 호출되는 내부 code입니다.

### 필요한 input과 실행

`download.sh PDB_ID`는 optional source PDB를 수정하지 않고 내려받습니다. 임시
파일에서 PDB atom record를 확인한 뒤 최종 파일로 교체합니다. `build.sh`는
준비한 PDB로 configured protein/water topology와 preproduction input을 만듭니다.

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

`run.sh`는 500 ps heating과 1 ns NPT equilibration 뒤 10×10 ns production을
실행합니다. 첫 segment는 새 `HILLS`를 만들고 이후 segment는 `RESTART`로 같은
file에 추가합니다.

### 주요 output

| 파일 | 내용 |
| --- | --- |
| `work/HILLS`, `work/COLVAR` | 모든 segment가 공유하는 누적 bias history와 CV |
| `work/001/` … | Segment별 restart, trajectory와 AMBER output |
| `work/analysis/production_summary.tsv` | CV와 bias 범위 |
| `work/analysis/fes.dat` | `plumed sum_hills`로 만든 FES |

`anal.py`는 모든 segment의 누적 `COLVAR`와 `HILLS`를 읽습니다. 기본적으로
`plumed sum_hills`를 실행하며 `--skip-fes`로 diagnostic TSV만 만들 수 있습니다.
`--skip-fes`의 새 결과에는 과거 FES를 포함하지 않습니다. PLUMED의 기본 unit인
energy kJ/mol, length nm, time ps를 사용합니다. `COLVAR`의 header나 finite 값이
잘못되면 기존 analysis 결과를 교체하지 않습니다.

### 결과 확인과 해석

모든 segment가 끝나면 `run.sh`가 `MetaD production segments completed: 1-10 of 10 (...)`와
`Next: python3 anal.py`를 출력합니다. `anal.py`는
`WT-MetaD diagnostics: .../production_summary.tsv`로 끝납니다.

Well-tempered `HILLS`에는 bias factor로 rescale한 height가 기록되므로
`sum_hills` 결과가 FES 추정값입니다(PLUMED `METAD` 문서). 기본 `PACE=500`에서
10,000 hill은 10 ns, 즉 segment 하나입니다. Segment마다 FES를 만들어 basin 사이
free-energy 차이가 일정해지는지 비교합니다.

```bash
mkdir -p work/fes_time
plumed sum_hills --hills work/HILLS --stride 10000 --mintozero --outfile work/fes_time/fes_
```

다른 observable은 `COLVAR`의 `metad.rbias`(= bias − c(t))로 reweight합니다. Frame
weight는 `w = exp(metad.rbias / kT)`, `kT = k_B · temperature`(300 K에서
2.494 kJ/mol)입니다(Tiwary & Parrinello, *J. Phys. Chem. B* 119:736, 2015). 초기
구간은 제외합니다.

### 주요 parameter

`config.toml`의 `collective_variable.arguments`는 `cv.dat`의 label과 같아야 합니다.
기본 φ/ψ atom 번호는 capped alanine 예시이므로 topology에 맞게 바꿉니다.
`sigma`, `grid_min`, `grid_max`와 `grid_bins`는 CV 수와 같은 길이여야 합니다.
Grid 경계가 ±π이면 generated `plumed.dat`에 periodic torsion domain과 같은
`-pi`/`pi`로 씁니다.

| Key | 기본값 | Unit | PLUMED keyword | 효과 |
| --- | --- | --- | --- | --- |
| `sigma` | 0.2, 0.2 | CV unit(torsion은 rad) | `SIGMA` | CV별 Gaussian width |
| `height` | 1.2 | kJ/mol | `HEIGHT` | 처음 hill height |
| `pace_steps` | 500 | step(1 ps) | `PACE` | Hill 추가 간격 |
| `bias_factor` | 10.0 | – | `BIASFACTOR` | Well-tempered tempering. 1보다 커야 합니다. |
| `grid_min`, `grid_max` | -π, π | CV unit | `GRID_MIN`, `GRID_MAX` | Bias grid 범위. CV 값이 이 범위를 벗어나지 않아야 합니다. |
| `grid_bins` | 200, 200 | bin | `GRID_BIN` | CV별 grid 해상도 |

`temperature`(`TEMP`)와 `trajectory_interval_steps`(`PRINT STRIDE`)는
[MetaD template README](../README.md)의 공통 option에 있습니다.

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

### 문제 해결

| Error message | 확인할 것 |
| --- | --- |
| `PLUMED action unavailable: METAD` | `PLUMED`가 PLUMED 2.10 executable을 가리키는지 봅니다. |
| `Config error in ...: sigma must contain N values` | `sigma`, `grid_min`, `grid_max`, `grid_bins`의 길이를 CV 수와 맞춥니다. |
| `each grid_min value must be smaller than grid_max`, `bias_factor must be greater than one` | 해당 값을 고친 뒤 새 `WORK_DIR`에서 build합니다. |

공통 error는 [MetaD template README](../README.md)의 문제 해결에 있습니다.

Segment layout, `--segments` option, engine 선택과 실패한 segment의 `HILLS` 복원은
[MetaD template README](../README.md)를 참고합니다. 실행 상태, 실패 후 재실행과
동시 실행 보호는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

WT-MetaD deposits a Gaussian hill each time the CVs defined in `cv.dat` are
visited. Where bias has already accumulated, `BIASFACTOR=10` shrinks new hills,
so the free-energy surface fills more gradually than with conventional MetaD.
The WT-MetaD method is fixed by this directory and is not a separate config
mode.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt`. User-facing entry points are in
this directory root; `helpers/` contains internal code called automatically.

### Required inputs and run

`download.sh PDB_ID` retrieves an optional, unmodified source PDB. It checks the
PDB atom records in a temporary file before replacing the final file.
`build.sh` creates the configured protein/water topology and preproduction
inputs from the prepared PDB.

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

`run.sh` runs 500 ps heating and 1 ns NPT equilibration, then 10×10 ns
production. The first segment creates `HILLS`; later segments use `RESTART` and
append to the same file.

### Main outputs

| File | Content |
| --- | --- |
| `work/HILLS`, `work/COLVAR` | Cumulative bias history and CVs shared by all segments |
| `work/001/` … | Restart, trajectory and AMBER output per segment |
| `work/analysis/production_summary.tsv` | CV and bias ranges |
| `work/analysis/fes.dat` | FES from `plumed sum_hills` |

`anal.py` reads the cumulative `COLVAR` and `HILLS` of all segments. It runs
`plumed sum_hills` by default; `--skip-fes` writes only the diagnostic TSV, and
that new result does not keep the old FES. PLUMED default units are used:
energy kJ/mol, length nm, time ps. An invalid `COLVAR` header or nonfinite
values leave previous analysis results in place.

### Success check and interpretation

After the last segment, `run.sh` prints
`MetaD production segments completed: 1-10 of 10 (...)` and
`Next: python3 anal.py`. `anal.py` ends with
`WT-MetaD diagnostics: .../production_summary.tsv`.

Well-tempered `HILLS` stores heights rescaled by the bias factor, so the
`sum_hills` output is the FES estimate (PLUMED `METAD` documentation). With the
default `PACE=500`, 10,000 hills are 10 ns, one segment. Write one FES per
segment and check whether free-energy differences between basins stop changing.

```bash
mkdir -p work/fes_time
plumed sum_hills --hills work/HILLS --stride 10000 --mintozero --outfile work/fes_time/fes_
```

Reweight other observables with `metad.rbias` (= bias − c(t)) from `COLVAR`. The
frame weight is `w = exp(metad.rbias / kT)` with `kT = k_B · temperature`
(2.494 kJ/mol at 300 K) (Tiwary & Parrinello, *J. Phys. Chem. B* 119:736, 2015).
Discard the initial part.

### Key parameters

CV labels in `collective_variable.arguments` must match `cv.dat`; the supplied
φ/ψ atom numbers are only a capped-alanine example, so change them for your
topology. `sigma`, `grid_min`, `grid_max` and `grid_bins` must have one entry
per CV. Grid bounds equal to ±π are written as `-pi`/`pi` in the generated
`plumed.dat`, matching the periodic torsion domain.

| Key | Default | Unit | PLUMED keyword | Effect |
| --- | --- | --- | --- | --- |
| `sigma` | 0.2, 0.2 | CV unit (rad for torsions) | `SIGMA` | Gaussian width per CV |
| `height` | 1.2 | kJ/mol | `HEIGHT` | Initial hill height |
| `pace_steps` | 500 | step (1 ps) | `PACE` | Hill deposition interval |
| `bias_factor` | 10.0 | – | `BIASFACTOR` | Well-tempered tempering; must exceed one. |
| `grid_min`, `grid_max` | -π, π | CV unit | `GRID_MIN`, `GRID_MAX` | Bias-grid range; CV values must stay inside it. |
| `grid_bins` | 200, 200 | bins | `GRID_BIN` | Grid resolution per CV |

`temperature` (`TEMP`) and `trajectory_interval_steps` (`PRINT STRIDE`) are among
the common options in the [MetaD template README](../README.md).

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

### Troubleshooting

| Error message | What to check |
| --- | --- |
| `PLUMED action unavailable: METAD` | Check that `PLUMED` points to a PLUMED 2.10 executable. |
| `Config error in ...: sigma must contain N values` | Give `sigma`, `grid_min`, `grid_max` and `grid_bins` one entry per CV. |
| `each grid_min value must be smaller than grid_max`, `bias_factor must be greater than one` | Fix the value and build in a new `WORK_DIR`. |

Common errors are listed under Troubleshooting in the
[MetaD template README](../README.md).

See the [MetaD template README](../README.md) for the segment layout, the
`--segments` option, engine selection and restoring `HILLS` after a failed
segment. See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state, reruns after
failure and concurrent-run protection.
