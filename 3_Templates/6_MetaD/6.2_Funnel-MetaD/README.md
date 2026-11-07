# Funnel-MetaD template

## 한국어

Ligand COM의 funnel-axis projection `fps.lp`에 WT-MetaD bias를 쌓고 transverse
distance `fps.ld`를 funnel restraint로 제한합니다. Bulk solvent 전체를 bias하지
않으면서 binding/unbinding 방향을 sampling하는 구성입니다. Funnel-MetaD 방식은
이 directory에서 고정되며 별도 config mode가 아닙니다.

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`로 설치합니다. 사용자가 직접 실행하는 파일은 이
directory의 root에 있고, `helpers/`는 자동 호출되는 내부 code입니다.

### 필요한 input과 실행

`ligand/ligand.mol2`와 `ligand/ligand.frcmod`는 config의 residue name과 net charge가
반영된 precharged GAFF2 input이어야 합니다. Template는 RESP charge를 다시
계산하지 않습니다. Complex PDB의 ligand residue name과 MOL2 template가 같아야
합니다. MOL2의 residue name과 total charge가 config와 맞지 않으면 LEaP를 시작하기
전에 중단합니다.

`download.sh PDB_ID`는 optional source complex를 내려받으며 ligand parameter를
생성하지 않습니다. 임시 파일에서 PDB atom record를 확인한 뒤 최종 파일로
교체합니다.

```bash
./build.sh prepared-complex.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

`build.sh`가 mask를 topology atom number로 변환하고 initial ligand COM이 configured
funnel 안에 있는지 검사합니다. `run.sh`는 누적 bias state를 이어받아 segment를
실행하고 `anal.py`는 `COLVAR`와 free-energy reconstruction을 처리합니다.

### 주요 output

| 파일 | 내용 |
| --- | --- |
| `work/HILLS`, `work/COLVAR`, `work/FUNNEL_GRID` | 10 production segments가 공유하는 root bias state와 CV |
| `work/001/` … | Segment별 restart, trajectory와 AMBER output |
| `work/analysis/production_summary.tsv` | Projection, transverse distance와 bias 범위 |
| `work/analysis/fes.dat` | `plumed sum_hills`로 만든 FES |

`anal.py --skip-fes`는 hill reconstruction 없이 projection, transverse distance와
bias 범위만 기록하며, 새 결과에는 과거 FES를 포함하지 않습니다. `COLVAR`의
header나 finite 값이 잘못되면 기존 analysis 결과를 교체하지 않습니다.

### 결과 확인과 해석

모든 segment가 끝나면 `run.sh`가 `MetaD production segments completed: 1-10 of 10 (...)`와
`Next: python3 anal.py`를 출력합니다. `anal.py`는
`Funnel-MetaD diagnostics: .../production_summary.tsv`로 끝납니다.

`fes.dat`은 `fps.lp`에 대한 1D FES `W(lp)`입니다. Binding free energy는 다음 안내
절차로 계산하며 이 template는 구현하지 않았습니다(Limongelli, Bonomi &
Parrinello, *PNAS* 110:6358, 2013).

1. Cylinder 구간(`lp > zcc`)에서 FES가 평평한 unbound 값 `W_ref`를 정합니다.
2. Bound site 구간에서 `I = ∫ exp(−[W(lp) − W_ref] / kT) dlp`를 적분합니다.
3. `ΔG° = −kT ln(C° · π R_cyl² · I)`를 계산합니다. `C° = 1/1660 Å⁻³ = 0.6022 nm⁻³`,
   `R_cyl = cylinder_radius`(nm), `kT = k_B · temperature`입니다.

Bound–unbound recrossing이 여러 번 일어나고 segment마다 `ΔG°`가 일정할 때만 이
값을 보고합니다.

### 주요 parameter

`funnel_selection`의 protein/ligand/alignment mask, anchor atom과 두 axis point의
AMBER mask를 system에 맞게 지정합니다. Axis point의 각 mask는 atom 하나를
선택합니다.

Funnel geometry, hill과 20 Å solvent padding은 system 크기와 최대 projection에
맞게 확인합니다.

| Key | 기본값 | Unit | PLUMED keyword | 효과 |
| --- | --- | --- | --- | --- |
| `ligand_net_charge` | 0 | e | – | Build 전 MOL2 total charge와 비교합니다. |
| `zcc` | 1.8 | nm | `FUNNEL ZCC` | Cone에서 cylinder로 바뀌는 `fps.lp` |
| `alpha` | 0.55 | rad | `FUNNEL ALPHA` | Cone 각도. π/2보다 작아야 합니다. |
| `cylinder_radius` | 0.1 | nm | `FUNNEL RCYL` | Cylinder 반지름. Standard-state correction의 `R_cyl`입니다. |
| `minimum_projection`, `maximum_projection` | -0.5, 3.7 | nm | `MINS`, `MAXS`, `METAD GRID_MIN/MAX` | Funnel과 bias grid의 `fps.lp` 범위 |
| `lower_wall`, `upper_wall` | -0.3, 3.5 | nm | `LOWER_WALLS AT`, `UPPER_WALLS AT` | `minimum < lower < zcc < upper < maximum`이어야 합니다. |
| `wall_force` | 35100.0 | kJ mol⁻¹ nm⁻² | `FUNNEL KAPPA`, wall `KAPPA` | Funnel 경계와 axial wall의 force constant |
| `radial_grid_bins`, `axial_grid_bins` | 500, 500 | bin | `NBINS`, `NBINZ` | `FUNNEL_GRID` 해상도 |
| `sigma` | 0.05 | nm | `METAD SIGMA` | `fps.lp` Gaussian width |
| `height` | 1.2 | kJ/mol | `HEIGHT` | 처음 hill height |
| `pace_steps` | 500 | step(1 ps) | `PACE` | Hill 추가 간격 |
| `bias_factor` | 10.0 | – | `BIASFACTOR` | 1보다 커야 합니다. |
| `grid_bins` | 420 | bin | `GRID_BIN` | `fps.lp` bias grid 해상도 |

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `ligand_force_field` | `GAFF2`만 지원 | `GAFF2` | Ligand parameter 형식을 결정합니다. |
| `charge_method` | precharged `RESP` MOL2만 지원 | `RESP` | `ligand_mol2`의 RESP charge를 그대로 사용합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`만 지원 | `rectangular` | Funnel geometry에 필요한 rectangular box를 만듭니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Conventional equilibration에 적용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Funnel-MetaD production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | `"random"`은 AMBER `ig=-1`, 정수는 고정 seed를 사용합니다. |

### Engine option 직접 지정

Config key가 없는 AMBER option은 `[amber.<stage>.<namelist>]` table로 지정합니다. Stage 우선순위, 값 형식과 거부되는 keyword는 [3_Templates README](../../README.md#engine-option-직접-지정)를 따릅니다.

```toml
[amber.md.cntrl]
gamma_ln = 2.0

[amber.production.cntrl]
iwrap = 1

[plumed.bias_options]
GRID_WFILE = "metad.grid"   # METAD: write the bias grid
GRID_WSTRIDE = 50000
```

| Stage | Input |
| --- | --- |
| `minimization` | `min-solvent.in`, `min-all.in` |
| `heating` | `heat.in` |
| `equilibration` | `equilibrate.in` |
| `production` | `production.in.template` |

`[plumed]`는 production `plumed.dat`에 적용되며 bias action label은 `metad`입니다.

### 문제 해결

| Error message | 확인할 것 |
| --- | --- |
| `PLUMED action unavailable: FUNNEL_PS. Rebuild PLUMED 2.10 with --enable-modules=funnel.` | `funnel` module을 넣어 PLUMED를 다시 build합니다. |
| `Ligand validation: MOL2 residue name mismatch`, `MOL2 charge mismatch` | `ligand_residue_name`, `ligand_net_charge`와 MOL2를 맞춥니다. |
| `Funnel setup error: AMBER mask must select one atom` | `axis_point_a_masks`, `axis_point_b_masks`, `anchor_atom_mask`의 각 mask가 atom 하나를 고르게 합니다. |
| `Funnel setup error: Initial ligand COM is outside the funnel` | Axis point, `zcc`, `alpha`, `cylinder_radius`를 다시 정합니다. |
| `funnel projection limits must satisfy min < lower < zcc < upper < max` | `[funnel]`의 projection 값 순서를 고칩니다. |

공통 error는 [MetaD template README](../README.md)의 문제 해결에 있습니다.

Segment layout, `--segments` option, engine 선택과 실패한 segment의 bias 복원은
[MetaD template README](../README.md)를 참고합니다. 실행 상태, 실패 후 재실행과
동시 실행 보호는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

Funnel-MetaD biases the ligand-COM projection on the funnel axis, `fps.lp`, with
WT-MetaD and confines the transverse distance `fps.ld` with a funnel restraint.
This samples the binding/unbinding direction without biasing the whole bulk
solvent. The Funnel-MetaD method is fixed by this directory and is not a
separate config mode.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt`. User-facing entry points are in
this directory root; `helpers/` contains internal code called automatically.

### Required inputs and run

`ligand/ligand.mol2` and `ligand/ligand.frcmod` must be a precharged GAFF2 pair
that matches the configured residue name and net charge. RESP charges are not
recomputed. The ligand residue name in the complex PDB must match the MOL2
template. A MOL2 residue name or total charge that differs from the config stops
the build before LEaP runs.

`download.sh PDB_ID` retrieves an optional source complex and does not generate
ligand parameters. It checks the PDB atom records in a temporary file before
replacing the final file.

```bash
./build.sh prepared-complex.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

`build.sh` converts the masks to topology atom numbers and checks that the
initial ligand COM lies inside the configured funnel. `run.sh` continues the
cumulative bias state across segments, and `anal.py` handles `COLVAR` and the
free-energy reconstruction.

### Main outputs

| File | Content |
| --- | --- |
| `work/HILLS`, `work/COLVAR`, `work/FUNNEL_GRID` | Root bias state and CVs shared by the ten production segments |
| `work/001/` … | Restart, trajectory and AMBER output per segment |
| `work/analysis/production_summary.tsv` | Projection, transverse distance and bias ranges |
| `work/analysis/fes.dat` | FES from `plumed sum_hills` |

`anal.py --skip-fes` records only projection, transverse distance and bias
ranges without hill reconstruction, and the new result does not keep the old
FES. An invalid `COLVAR` header or nonfinite values leave previous analysis
results in place.

### Success check and interpretation

After the last segment, `run.sh` prints
`MetaD production segments completed: 1-10 of 10 (...)` and
`Next: python3 anal.py`. `anal.py` ends with
`Funnel-MetaD diagnostics: .../production_summary.tsv`.

`fes.dat` is the 1D FES `W(lp)` along `fps.lp`. The binding free energy follows
the guidance below; this template does not implement it (Limongelli, Bonomi &
Parrinello, *PNAS* 110:6358, 2013).

1. Take the flat unbound value `W_ref` of the FES in the cylinder region
   (`lp > zcc`).
2. Integrate `I = ∫ exp(−[W(lp) − W_ref] / kT) dlp` over the bound site.
3. Compute `ΔG° = −kT ln(C° · π R_cyl² · I)` with
   `C° = 1/1660 Å⁻³ = 0.6022 nm⁻³`, `R_cyl = cylinder_radius` (nm) and
   `kT = k_B · temperature`.

Report the value only after repeated bound–unbound recrossings and when `ΔG°`
stays constant across segments.

### Key parameters

Set the protein/ligand/alignment masks, the anchor atom and the AMBER masks of
both axis points in `funnel_selection` for your system. Each axis-point mask
must select one atom.

Check the funnel geometry, hills and the 20 Å solvent padding against the system
size and the maximum projection.

| Key | Default | Unit | PLUMED keyword | Effect |
| --- | --- | --- | --- | --- |
| `ligand_net_charge` | 0 | e | – | Compared with the MOL2 total charge before the build. |
| `zcc` | 1.8 | nm | `FUNNEL ZCC` | `fps.lp` where the cone turns into the cylinder |
| `alpha` | 0.55 | rad | `FUNNEL ALPHA` | Cone angle; must be below π/2. |
| `cylinder_radius` | 0.1 | nm | `FUNNEL RCYL` | Cylinder radius; `R_cyl` in the standard-state correction. |
| `minimum_projection`, `maximum_projection` | -0.5, 3.7 | nm | `MINS`, `MAXS`, `METAD GRID_MIN/MAX` | `fps.lp` range of the funnel and the bias grid |
| `lower_wall`, `upper_wall` | -0.3, 3.5 | nm | `LOWER_WALLS AT`, `UPPER_WALLS AT` | Must satisfy `minimum < lower < zcc < upper < maximum`. |
| `wall_force` | 35100.0 | kJ mol⁻¹ nm⁻² | `FUNNEL KAPPA`, wall `KAPPA` | Force constant of the funnel boundary and axial walls |
| `radial_grid_bins`, `axial_grid_bins` | 500, 500 | bins | `NBINS`, `NBINZ` | `FUNNEL_GRID` resolution |
| `sigma` | 0.05 | nm | `METAD SIGMA` | `fps.lp` Gaussian width |
| `height` | 1.2 | kJ/mol | `HEIGHT` | Initial hill height |
| `pace_steps` | 500 | step (1 ps) | `PACE` | Hill deposition interval |
| `bias_factor` | 10.0 | – | `BIASFACTOR` | Must exceed one. |
| `grid_bins` | 420 | bins | `GRID_BIN` | `fps.lp` bias-grid resolution |

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `ligand_force_field` | `GAFF2` only | `GAFF2` | Sets the ligand parameter format. |
| `charge_method` | Precharged `RESP` MOL2 only | `RESP` | Uses RESP charges already present in `ligand_mol2`. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular` only | `rectangular` | Builds the rectangular box required by the funnel geometry. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to conventional equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Sets Funnel-MetaD production `ntb` and `ntp`. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | `"random"` maps to AMBER `ig=-1`; an integer fixes the seed. |

### Engine option passthrough

AMBER options without a config key go into `[amber.<stage>.<namelist>]` tables. Stage precedence, value formats and refused keywords are described in the [3_Templates README](../../README.md#engine-option-passthrough).

```toml
[amber.md.cntrl]
gamma_ln = 2.0

[amber.production.cntrl]
iwrap = 1

[plumed.bias_options]
GRID_WFILE = "metad.grid"   # METAD: write the bias grid
GRID_WSTRIDE = 50000
```

| Stage | Input |
| --- | --- |
| `minimization` | `min-solvent.in`, `min-all.in` |
| `heating` | `heat.in` |
| `equilibration` | `equilibrate.in` |
| `production` | `production.in.template` |

`[plumed]` applies to the production `plumed.dat`; the bias action label is `metad`.

### Troubleshooting

| Error message | What to check |
| --- | --- |
| `PLUMED action unavailable: FUNNEL_PS. Rebuild PLUMED 2.10 with --enable-modules=funnel.` | Rebuild PLUMED with the `funnel` module. |
| `Ligand validation: MOL2 residue name mismatch`, `MOL2 charge mismatch` | Match `ligand_residue_name` and `ligand_net_charge` to the MOL2. |
| `Funnel setup error: AMBER mask must select one atom` | Make each mask in `axis_point_a_masks`, `axis_point_b_masks` and `anchor_atom_mask` select one atom. |
| `Funnel setup error: Initial ligand COM is outside the funnel` | Redefine the axis points, `zcc`, `alpha` or `cylinder_radius`. |
| `funnel projection limits must satisfy min < lower < zcc < upper < max` | Fix the order of the projection values in `[funnel]`. |

Common errors are listed under Troubleshooting in the
[MetaD template README](../README.md).

See the [MetaD template README](../README.md) for the segment layout, the
`--segments` option, engine selection and restoring bias after a failed
segment. See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state, reruns after
failure and concurrent-run protection.
