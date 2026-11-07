# RBFE template

## 한국어

Ligand A에서 ligand B로 변환하는 dual-topology AMBER RBFE window를 complex와
solvent environment에 각각 만듭니다. `atom_mapping.tsv`로 대응시킨 common core는
두 end state의 parameter를 lambda에 따라 linear mixing하고, 대응되지 않은 atom만
soft-core가 됩니다.

기본 lambda는 0.0–1.0의 11개 state이며 restraint stage는 없습니다. 각 window는
250,000-step heating, 500,000-step equilibration과 10,000,000-step production을
실행합니다. `ifmbar=1`, `bar_intervall=5000`으로 cross-state energy를 기록합니다.

### 필요한 input

- `build.sh`에 넘길 ligand를 제외한 reviewed protein PDB
- 서로 같은 coordinate frame에 배치한 두 ligand의 precharged MOL2와 matching
  frcmod (`config.toml`에서 지정)
- One-to-one atom-name mapping인 `atom_mapping.tsv`

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다. 필요한 program과 기본
계산량(22 windows, production 합계 440 ns)은 [FEP template README](../README.md#필요한-program)에
있습니다.

### 실행

```bash
./build.sh prepared_protein.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

| File | 역할 |
| --- | --- |
| `download.sh` | `download.sh PDB_ID`로 optional source protein PDB 다운로드 |
| `config.toml` | Force field, ligand file, mask, MD 길이와 lambda schedule |
| `atom_mapping.tsv` | Ligand A–B common-core atom pair |
| `build.sh` | 두 environment와 lambda window 생성 |
| `run.sh` | Window별 stage 실행 |
| `anal.py` | MBAR free energy와 overlap 계산 |

`helpers/`는 `build.sh`, `run.sh` 또는 `anal.py`가 자동 호출하는 leaf-local 내부
code입니다. `helpers/result_generation.py`는 외부 consumer에서 결과를 읽기 전
별도로 검사할 때도 사용합니다.

### Common core와 `atom_mapping.tsv`

Build는 두 ligand mask가 비어 있지 않고 겹치지 않는지, mapping atom 이름이
각 ligand에 존재하며 one-to-one인지 검사합니다. `helpers/generate_inputs.py`는
environment마다 다음을 수행합니다.

- Ligand mask가 residue 하나 전체를 고르는지, residue 이름이 topology에서
  유일한지 확인합니다.
- Mapping된 ligand B atom이 ligand A partner와 같은 순서로 놓였는지 확인합니다.
  Amber manual은 common atom의 같은 순서와 같은 시작 좌표를 요구합니다
  (Amber26 §27.1.6, p.555, sander 기준; pmemd 준비 예시 §27.1.8.1, p.568).
  순서가 다르면 MOL2 atom 순서나 mapping을 고칩니다.
- 대응 atom 좌표 차이가 0.1 Å 이하인지 확인하고, ligand B core 좌표를 ligand A
  대응 atom에 복사해 `work/build/{complex,solvent}_core.rst7`을 만듭니다.
  Window는 이 restart에서 시작합니다.
- 대응되지 않은 atom으로 `scmask1=':LGA@...'`, `scmask2=':LGB@...'`를 만듭니다.

함께 제공하는 `atom_mapping.tsv`는 benzene→toluene 예시입니다. 다른 ligand에서는
이 파일을 해당 MOL2 atom 이름으로 바꿉니다. Common core가 계속 결합 상태를
유지하므로 별도 ligand restraint는 두지 않습니다. Common core와 soft-core 사이의
SHAKE bond는 `pmemd.cuda` 기본값(`tishake=0`, 자동 `gti_syn_mass=3`)을 사용합니다
(§27.1.7.5, p.567). 실제 `pmemd.cuda` parsing과 DV/DL은 미검증입니다.

### Output

`build.sh`는 각 lambda 값을 complex와 solvent의 한 window로 만들고
`work/states.tsv`에 기록합니다. `anal.py`는 완료 기록이 있는 모든 production
output을 사용해 `mbar/`, `free_energy.tsv`, `mbar_diagnostics.tsv`,
`overlap_matrix.tsv`를 씁니다. Analysis가 실패하면 기존 결과를 유지하고 실패한
command의 최근 log를 stderr에 출력합니다.

외부 script에서 결과를 읽기 전에는 다음 검사를 사용합니다. 별도 `WORK_DIR`을
사용했다면 `work`를 그 경로로 바꿉니다.

```bash
python3 helpers/result_generation.py work
```

완료 기록은 `work/.analysis-generation.json`입니다. `work/.analysis.pending`이
남으면 게시가 중간에 멈춘 것이므로 GUIDE.md 부록의 `.output.pending`과 같은
방식으로 처리합니다.

### 성공 확인

| Command | 정상 종료 |
| --- | --- |
| `./build.sh prepared_protein.pdb` | Environment마다 `N common-core atoms (largest pre-sync gap ...)`와 두 `scmask`를 출력하고 `FEP systems and windows: work`로 끝납니다. |
| `./run.sh --dry-run` | `Dry run: RBFE: 22 environment/window states, 10000000 production steps per window` |
| `./run.sh` | `RBFE production completed: work/complex, work/solvent`. `--preparation-only`는 `RBFE preparation completed: work`로 끝납니다. |
| `python3 anal.py` | `RBFE free-energy results: work/free_energy.tsv`. 모든 window의 production이 끝나야 실행됩니다. |

부호, overlap 기준과 overlap이 부족할 때의 조치는
[FEP tutorial README](../../../1_Simulation/5_FEP/README.md#결과-해석)를 따릅니다.
Window를 추가할 때는 `lambda_values`에 해당 구간의 값을 넣고 새 `WORK_DIR`에서 다시
build합니다.

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
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | Heating만 새 velocity를 만듭니다. `"random"`은 `ig=-1`, 정수 N은 window마다 `ig=N + global window index`(1부터)를 씁니다. Equilibration과 production은 restart에서 이어가며 항상 `ig=-1`입니다. |
| `scalpha` | 0보다 큰 수 (unitless) | `0.5` | vdW soft-core의 α입니다. |
| `scbeta` | 0보다 큰 수 (Å²) | `12.0` | Electrostatic soft-core의 β입니다. |
| `gti_lam_sch` | 정수 `0`, `1` | `0` | `1`이면 `pmemd.cuda` smoothstep lambda scheduling을 켭니다. |
| `gti_ele_sc` | 정수 `0`, `1` | `0` | `1`이면 electrostatic soft-core에 smoothstep function을 씁니다. |
| `gti_vdw_sc` | 정수 `0`, `1` | `0` | `1`이면 vdW soft-core에 smoothstep function을 씁니다. |

`[alchemical]`의 soft-core 다섯 값은 모든 window의 minimization, heating,
equilibration, production input에 들어갑니다. 세 `gti_*`가 모두 0이면
`pmemd.cuda` 기본값과 같아 mdin에 쓰지 않고, 하나라도 1이면 셋을 모두 씁니다.
`gti_lam_sch=1`이면 `pmemd.cuda`의 기본값이 `gti_ele_sc=1`, `gti_vdw_sc=1`,
`scalpha=0.2`, `scbeta=50.0`으로 바뀝니다(Amber26 §27.1.7.1, p.559–560). Template은
config 값을 그대로 쓰므로 네 값을 함께 정합니다. Window directory에 `lambda.sch`가
없으면 `pmemd.cuda` 기본 `smooth_step2` schedule을 사용합니다. 기본값이 아닌 조합은
`pmemd.cuda`로 실행하지 않았습니다(미검증). Build가 사용한 값은
`work/resolved_config.toml`의 `[alchemical]`에 기록됩니다.

`lambda_values`는 0.0과 1.0을 포함하는 중복 없는 오름차순 list를 직접
지정합니다. Auto/file mode는 없습니다. `production_segments`는 `1`만 지원합니다.

### 숫자 option

| Key | 기본값 | Unit | Stage | 효과 |
| --- | --- | --- | --- | --- |
| `ligand_a_net_charge`, `ligand_b_net_charge` | `0` | e | Build | MOL2 charge 합과 0.01 e 이내로 맞아야 합니다. `anal.py`는 net-charge correction을 계산하지 않습니다. |
| `complex_box_distance` | `14.0` | Å | Build | Complex leg의 solute와 box edge 사이 `solvatebox` buffer |
| `solvent_box_distance` | `20.0` | Å | Build | Solvent leg의 `solvatebox` buffer |
| `salt_concentration` | `150.0` | mM | Build | 중화 ion 뒤 leg마다 `water 수 × M / 55.5`(반올림)개의 NaCl pair를 더합니다. |
| `temperature` | `300.0` | K | MD stage, `anal.py` | `temp0`와 `edgembar --temp` |
| `pressure` | `1.0` | bar | NPT stage | `pres0` |
| `timestep` | `2.0` | fs | MD stage | `dt`. 2 fs보다 크면 build가 거부합니다. |
| `minimization_steps` | `5000` | cycles | Minimization | `maxcyc` |
| `minimization_steepest_steps` | `2500` | cycles | 사용 안 함 | Softcore(`ifsc=1`) minimization은 pmemd.cuda에서 steepest descent만 허용하므로 RBFE input은 `ntmin=2`이고 이 값은 적용되지 않습니다. 공통 config 검사 때문에 key만 남아 있습니다. |
| `heating_initial_temperature` | `0.0` | K | Heating | `tempi` |
| `heating_steps` | `250000` | steps | Heating | NVT 500 ps |
| `equilibration_steps` | `500000` | steps | Equilibration | 1 ns |
| `production_steps_per_window` | `10000000` | steps | Production | Window당 20 ns |
| `trajectory_interval_steps` | `5000` | steps | MD stage | `ntwx`. Production은 window당 2,000 frames입니다. |
| `energy_interval_steps` | `5000` | steps | MD stage | mdout 기록 간격 `ntpr` |
| `restart_interval_steps` | `5000` | steps | MD stage | `ntwr` |
| `mbar_interval_steps` | `5000` | steps | Production | Cross-state energy 기록 간격 `bar_intervall` |

### Engine 선택

`AMBER_ENGINE`이 설정되어 있으면 이를 사용하며, 없으면 build가 기록한
`work/resolved_config.toml`의 `run.engine`을 읽습니다. 허용하는 executable 이름은
`pmemd.cuda`이며 설치 경로를 지정할 수 있습니다. 빈 override, 누락된 engine 설정과
지원하지 않는 executable은 기본값으로 대체하지 않고 error로 중단합니다. Runner가
`helpers/config_utils.py`를 자동 호출해 이 설정을 읽습니다.

### Window 재실행과 병렬 실행

Run은 선택한 environment/window에만 write scope를 등록하므로 서로 독립적인
window를 동시에 실행할 수 있습니다. 완료 기록이 있는 stage는 다시 실행하지
않습니다. Partial output이 있으면 error가 해당 window와 남은 파일, 다시 실행할
`./run.sh` command를 표시합니다. 그 밖의 실행 상태, 실패 후 재실행, 동시 실행
보호는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

### Engine option 직접 지정

Config key가 없는 AMBER option은 `[amber.<stage>.<namelist>]` table로 지정합니다. Stage 우선순위, 값 형식과 거부되는 keyword는 [3_Templates README](../../README.md#engine-option-직접-지정)를 따릅니다.

```toml
[amber.md.cntrl]
gamma_ln = 2.0

[amber.production.cntrl]
iwrap = 1
```

| Stage | Input |
| --- | --- |
| `minimization` | `minimize.in.template` |
| `heating` | `heat.in.template` |
| `equilibration` | `equilibrate.in.template` |
| `production` | `production.in.template` |

모든 environment와 lambda window에 같은 값을 씁니다. Window별 값은 지정할 수 없습니다.

### 문제 해결

| Message | 원인과 조치 |
| --- | --- |
| `ligand_a.mol2 charge ... does not match expected ...` | MOL2 charge 합이 `ligand_*_net_charge`와 0.01 e 이상 다릅니다. MOL2 charge나 config 값을 고칩니다. |
| `Common-core error (...): mapped ligand B atoms are not in the same order as their ligand A partners` | Ligand B MOL2 atom 순서가 mapping과 맞지 않습니다. MOL2 atom 순서나 `atom_mapping.tsv`를 고칩니다. |
| `Common-core error (...): mapped core atoms differ by ... A (limit 0.1 A)` | 두 ligand가 같은 coordinate frame에 놓이지 않았거나 mapping이 다른 atom을 짝지었습니다. |
| `Common-core error (...): ligand mask must select the whole residue` | `ligand_a_mask`/`ligand_b_mask`가 residue 일부만 고릅니다. `:LGA`처럼 residue 전체를 지정합니다. |
| `The coupled RBFE protocol has no separate charge or vdw stage` | RBFE에는 `--stage`가 없습니다. `--system`과 `--windows`만 사용합니다. |
| `Completed equilibration output is required` | `--production-only` 전에 `--preparation-only`가 해당 window를 끝내지 않았습니다. |

## English

This dual-topology Amber RBFE template creates complex and solvent windows for
transforming ligand A into ligand B. The common core mapped by
`atom_mapping.tsv` mixes the parameters of both end states linearly with lambda;
only unmapped atoms become soft-core.

The default schedule contains 11 lambda states from 0.0 to 1.0 and no restraint
stage. Each window runs 250,000 heating steps, 500,000 equilibration steps and
10,000,000 production steps, and records cross-state energies with `ifmbar=1`
and `bar_intervall=5000`.

### Required inputs

- A ligand-free reviewed protein PDB passed to `build.sh`
- Precharged MOL2 files of both ligands in the same coordinate frame, with
  matching frcmod files (set in `config.toml`)
- `atom_mapping.tsv`, a one-to-one atom-name map

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it. Required
programs and the default computation (22 windows, 440 ns of total production)
are listed in the [FEP template README](../README.md#required-programs).

### Run

```bash
./build.sh prepared_protein.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

| File | Role |
| --- | --- |
| `download.sh` | `download.sh PDB_ID` downloads an optional source protein PDB |
| `config.toml` | Force fields, ligand files, masks, MD lengths and lambda schedule |
| `atom_mapping.tsv` | Ligand A–B common-core atom pairs |
| `build.sh` | Creates both environments and their lambda windows |
| `run.sh` | Runs the stages of each window |
| `anal.py` | Estimates MBAR free energy and overlap |

`helpers/` contains leaf-local internal code called automatically by
`build.sh`, `run.sh`, or `anal.py`; `helpers/result_generation.py` also supports
a separate integrity check before an external consumer reads results.

### Common core and `atom_mapping.tsv`

The build checks that both ligand masks are non-empty and non-overlapping and
that the mapped atom names exist in each ligand and are one-to-one. For each
environment, `helpers/generate_inputs.py`:

- requires each ligand mask to select one whole, uniquely named residue;
- checks that mapped ligand B atoms follow the order of their ligand A partners
  (Amber26 §27.1.6, p.555, stated for sander; pmemd preparation example
  §27.1.8.1, p.568). Fix the MOL2 atom order or the mapping if they differ;
- refuses core gaps above 0.1 Å and copies the ligand B core coordinates onto
  ligand A in `work/build/{complex,solvent}_core.rst7`, which every window
  starts from;
- derives `scmask1=':LGA@...'` and `scmask2=':LGB@...'` from the unmapped atoms.

The shipped `atom_mapping.tsv` is a benzene→toluene example; replace it with the
atom names of your MOL2 files. Because the core stays coupled, no ligand
restraint is added. SHAKE bonds between core and soft-core atoms use the
`pmemd.cuda` defaults (`tishake=0`, automatic `gti_syn_mass=3`; §27.1.7.5,
p.567). Actual `pmemd.cuda` parsing and DV/DL remain unverified.

### Outputs

`build.sh` turns each lambda value into one complex and one solvent window and
records them in `work/states.tsv`. `anal.py` uses every production output with
a completion record and writes `mbar/`, `free_energy.tsv`,
`mbar_diagnostics.tsv`, and `overlap_matrix.tsv`. A failed analysis keeps the
previous results and prints recent log lines of the failed command to stderr.

Before reading results in an external script, run the check below. Replace
`work` with your `WORK_DIR` if using another directory.

```bash
python3 helpers/result_generation.py work
```

Completion is recorded in `work/.analysis-generation.json`. A leftover
`work/.analysis.pending` means publication stopped midway; handle it like
`.output.pending` in the GUIDE.md appendix.

### Success check

| Command | Normal finish |
| --- | --- |
| `./build.sh prepared_protein.pdb` | Prints `N common-core atoms (largest pre-sync gap ...)` and both `scmask` values per environment, then ends with `FEP systems and windows: work`. |
| `./run.sh --dry-run` | `Dry run: RBFE: 22 environment/window states, 10000000 production steps per window` |
| `./run.sh` | `RBFE production completed: work/complex, work/solvent`; `--preparation-only` ends with `RBFE preparation completed: work`. |
| `python3 anal.py` | `RBFE free-energy results: work/free_energy.tsv`; it requires finished production in every window. |

See the [FEP tutorial README](../../../1_Simulation/5_FEP/README.md#interpreting-the-results)
for the sign, the overlap guideline and what to do when overlap is poor. To add
windows, insert values in that region of `lambda_values` and rebuild in a new
`WORK_DIR`.

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
| `random_seed` | `"random"` or a positive integer | `"random"` | Only heating starts new velocities. `"random"` writes `ig=-1`; an integer N writes `ig=N + global window index` (starting at 1) per window. Equilibration and production continue from restarts with `ig=-1`. |
| `scalpha` | Number greater than zero (unitless) | `0.5` | vdW soft-core α. |
| `scbeta` | Number greater than zero (Å²) | `12.0` | Electrostatic soft-core β. |
| `gti_lam_sch` | Integer `0` or `1` | `0` | `1` enables `pmemd.cuda` smoothstep lambda scheduling. |
| `gti_ele_sc` | Integer `0` or `1` | `0` | `1` applies the smoothstep function to electrostatic soft-core. |
| `gti_vdw_sc` | Integer `0` or `1` | `0` | `1` applies the smoothstep function to vdW soft-core. |

The five soft-core values in `[alchemical]` go into the minimization, heating,
equilibration and production inputs of every window. While all three `gti_*`
are 0 they equal the `pmemd.cuda` defaults and are not written; if any is 1, all
three are written. With `gti_lam_sch=1`, `pmemd.cuda` changes its defaults to
`gti_ele_sc=1`, `gti_vdw_sc=1`, `scalpha=0.2` and `scbeta=50.0` (Amber26
§27.1.7.1, p.559–560). The template always writes the config values, so set all
four together. Without `lambda.sch` in the window directory, `pmemd.cuda` uses
its default `smooth_step2` schedule. Non-default combinations have not been run
with `pmemd.cuda` (unverified). The values used by the build are recorded under
`[alchemical]` in `work/resolved_config.toml`.

`lambda_values` is an explicit, unique, increasing list spanning 0.0 to 1.0.
It has no auto/file mode. `production_segments` supports only `1`.

### Numeric options

| Key | Default | Unit | Stage | Effect |
| --- | --- | --- | --- | --- |
| `ligand_a_net_charge`, `ligand_b_net_charge` | `0` | e | Build | Must match the MOL2 charge sum within 0.01 e. `anal.py` applies no net-charge correction. |
| `complex_box_distance` | `14.0` | Å | Build | `solvatebox` solute-to-edge buffer of the complex leg |
| `solvent_box_distance` | `20.0` | Å | Build | `solvatebox` buffer of the solvent leg |
| `salt_concentration` | `150.0` | mM | Build | After neutralization, adds `waters × M / 55.5` (rounded) NaCl pairs to each leg. |
| `temperature` | `300.0` | K | MD stages, `anal.py` | `temp0` and `edgembar --temp` |
| `pressure` | `1.0` | bar | NPT stages | `pres0` |
| `timestep` | `2.0` | fs | MD stages | `dt`; values above 2 fs are rejected by the build. |
| `minimization_steps` | `5000` | cycles | Minimization | `maxcyc` |
| `minimization_steepest_steps` | `2500` | cycles | Not used | Softcore (`ifsc=1`) minimization on pmemd.cuda allows steepest descent only, so the RBFE input uses `ntmin=2` and ignores this value. The key remains for the shared config checker. |
| `heating_initial_temperature` | `0.0` | K | Heating | `tempi` |
| `heating_steps` | `250000` | steps | Heating | 500 ps NVT |
| `equilibration_steps` | `500000` | steps | Equilibration | 1 ns |
| `production_steps_per_window` | `10000000` | steps | Production | 20 ns per window |
| `trajectory_interval_steps` | `5000` | steps | MD stages | `ntwx`; 2,000 production frames per window |
| `energy_interval_steps` | `5000` | steps | MD stages | mdout interval `ntpr` |
| `restart_interval_steps` | `5000` | steps | MD stages | `ntwr` |
| `mbar_interval_steps` | `5000` | steps | Production | Cross-state energy interval `bar_intervall` |

### Engine selection

`AMBER_ENGINE` overrides `run.engine` in the build-generated
`work/resolved_config.toml`. Accepted executable names are `pmemd.cuda`;
installation paths are accepted. Empty overrides, missing engine settings and
unsupported executables fail instead of falling back to a default. The runner
invokes `helpers/config_utils.py` automatically to read this setting.

### Rerunning and parallel windows

Run registers write scopes only for the selected environment/window paths, so
independent windows can run concurrently. Stages with a completion record are
not rerun. For partial output, the error names the window, the leftover files
and the `./run.sh` command to rerun. See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for
other run state, reruns after failure and concurrent-run protection.

### Engine option passthrough

AMBER options without a config key go into `[amber.<stage>.<namelist>]` tables. Stage precedence, value formats and refused keywords are described in the [3_Templates README](../../README.md#engine-option-passthrough).

```toml
[amber.md.cntrl]
gamma_ln = 2.0

[amber.production.cntrl]
iwrap = 1
```

| Stage | Input |
| --- | --- |
| `minimization` | `minimize.in.template` |
| `heating` | `heat.in.template` |
| `equilibration` | `equilibrate.in.template` |
| `production` | `production.in.template` |

Every environment and lambda window gets the same values; per-window values are not supported.

### Troubleshooting

| Message | Cause and fix |
| --- | --- |
| `ligand_a.mol2 charge ... does not match expected ...` | The MOL2 charge sum differs from `ligand_*_net_charge` by more than 0.01 e. Fix the MOL2 charges or the config value. |
| `Common-core error (...): mapped ligand B atoms are not in the same order as their ligand A partners` | The ligand B MOL2 atom order does not follow the mapping. Fix the MOL2 atom order or `atom_mapping.tsv`. |
| `Common-core error (...): mapped core atoms differ by ... A (limit 0.1 A)` | The ligands are not in the same coordinate frame, or the mapping pairs different atoms. |
| `Common-core error (...): ligand mask must select the whole residue` | `ligand_a_mask`/`ligand_b_mask` selects part of a residue. Select the whole residue, such as `:LGA`. |
| `The coupled RBFE protocol has no separate charge or vdw stage` | RBFE has no `--stage`; use only `--system` and `--windows`. |
| `Completed equilibration output is required` | `--preparation-only` has not finished that window before `--production-only`. |
