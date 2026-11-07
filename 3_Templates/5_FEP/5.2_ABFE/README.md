# ABFE template

## 한국어

Ligand restraint removal, complex/solvent charge decoupling과 vdW decoupling을
포함하는 double-decoupling ABFE window를 만듭니다. `anal.py`가 restraint
correction과 각 alchemical contribution을 합산합니다.

Restraint/charge는 11-state schedule, vdW는 16-state schedule을 사용해 총 65개
window를 만듭니다. 각 window production은 10,000,000 steps이며
`bar_intervall=5000`으로 MBAR energy를 기록합니다.

### 필요한 input

- `build.sh`에 넘길 ligand가 포함된 reviewed complex PDB
- Complex와 같은 residue name과 atom name을 가진 precharged MOL2와 frcmod
  (`config.toml`에서 지정)
- 정확히 한 atom씩 선택하는 protein anchor 3개와 ligand anchor 3개. Protein
  anchor는 기본값이 없습니다.

Window 생성 전에 ligand anchor 세 개는 `ligand_mask` 안에, protein anchor 세 개는
밖에 있는지 검사합니다. 여섯 mask는 서로 다른 atom을 하나씩 선택해야 합니다.

Neutral ligand만 지원합니다. `build.ligand_net_charge`는 정수 0이어야 하며,
MOL2 charge 합은 이 값과 0.01 e 이내로 일치해야 합니다. Build와 dry-run은
output을 복사하거나 생성하기 전에 ParmEd로 이를 확인합니다. 과거 charged config도
input 생성, run과 analysis에서 거부합니다.

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다. 필요한 program과 기본
계산량(65 windows, production 합계 1,300 ns)은 [FEP template README](../README.md#필요한-program)에
있습니다.

### Boresch anchor 선택

`protein_anchor_1`–`3`이 비어 있으면 build와 dry-run이 tleap 실행 전에 멈춥니다.

- Protein anchor는 binding pocket 가까이의 rigid backbone atom(예: helix나 sheet의
  `CA`)으로 고릅니다. Flexible loop와 side chain 끝 atom은 피합니다. 세 atom이 한
  직선 위에 놓이면 안 됩니다.
- Ligand anchor도 ring처럼 rigid한 부분의 heavy atom으로 고릅니다.
- Build는 시작 구조에서 distance r(P1–L1), angle θA(P2–P1–L1)와 θB(P1–L1–L2),
  dihedral 세 개(P3–P2–P1–L1, P2–P1–L1–L2, P1–L1–L2–L3)를 계산합니다. P와 L의
  번호는 `protein_anchor_N`과 `ligand_anchor_N`입니다.
- θA나 θB가 30°–150° 밖이면 window를 만들지 않고 멈춥니다. 직선에 가까운 anchor는
  restraint를 불안정하게 하고, sin θA·sin θB로 나누는 analytical standard-state
  correction을 발산시킵니다. Dihedral을 정의하는 P3–P2–P1과 L1–L2–L3 각도에도 같은
  범위를 적용합니다.
- Build는 여섯 reference 값과 `work/restraints.tsv` 경로를 출력합니다. Run 전에
  거리와 각도가 의도한 anchor 배치와 맞는지 봅니다.

Angle 검사는 tleap build 뒤에 실행됩니다. 여기서 멈추면 anchor를 고친 뒤 기존
`work/`를 지우거나 새 `WORK_DIR`을 지정해 다시 build합니다.

### 실행

```bash
./build.sh prepared_complex.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

| File | 역할 |
| --- | --- |
| `download.sh` | `download.sh PDB_ID`로 optional source complex 다운로드 |
| `config.toml` | Force field, ligand file, mask, anchor, MD 길이와 lambda schedule |
| `build.sh` | Double-decoupling system과 65개 window 생성 |
| `run.sh` | Stage별 window 실행 |
| `anal.py` | FE-ToolKit의 `edgembar-amber2dats.py`와 `edgembar`로 restraint correction과 alchemical contribution 합산 |

`helpers/`는 `build.sh`, `run.sh` 또는 `anal.py`가 자동 호출하는 leaf-local 내부
code입니다. `helpers/result_generation.py`는 외부 consumer에서 결과를 읽기 전
별도로 검사할 때도 사용합니다.

### Stage와 restraint

Build는 초기 구조에서 1 distance, 2 angle, 3 torsion reference를 계산합니다. 기본
force constant는 distance 5 kcal/mol/Å², angle/torsion 100 kcal/mol/rad²이고
standard state는 1 M, 300 K입니다. Mask 번호는 build가 topology에서 읽습니다.

| Stage | Topology | 주요 설정 |
| --- | --- | --- |
| Restraint | `complex.parm7` | TI 없음. `DISANG` force constant를 `(1-λ)`배로 줄이고 `production.restraint.dat`에 restraint 값을 기록 |
| Charge | `{complex,solvent}_charge.parm7` (ligand 두 copy) | `timask1`=첫 copy, `timask2`=`crgmask`=두 번째 copy, `ifsc=0` |
| vdW | `{complex,solvent}_uncharged.parm7` | `timask1=scmask1=ligand_mask`, `timask2=''`, `ifsc=1`, `aces26=1` |

Charge stage는 Amber manual 27.1.8.1의 linear-scaling TI입니다. `build.sh`가 같은
좌표의 ligand를 solute 뒤에 하나 더 붙인 `complex_charge`/`solvent_charge`
system을 LEaP로 만들고, 같은 salt 수를 사용합니다. 원래 solute의 atom 번호는
그대로라 restraint anchor도 바뀌지 않습니다. `helpers/generate_inputs.py`는 두
copy의 atom 이름, charge, 좌표와 restraint atom을 확인한 뒤 residue 번호로 mask를
만듭니다. Pmemd의 `crgmask`는 두 endpoint 모두에 적용되므로 같은 ligand를
`timask1`과 `timask2`에 함께 두면 charge leg가 0이 됩니다.

Restraint stage는 일반 MD입니다. ACES26에서는 SC/CC `ele,vdw`가 항상 λ로
scaling되어(manual 27.1.7.4) soft-core TI로는 restraint만 바꿀 수 없습니다.
`anal.py`는 DUMPAVE 값으로 full-strength restraint energy `U`를 계산하고 state j의
energy를 `(1-λj)U`로 넣어 MBAR를 계산합니다. 이 restraint energy 식은 AmberTools 26
sander 값과 0.02 kcal/mol 이내로 일치했습니다. `pmemd.cuda` 실행으로는
확인하지 않았습니다(미검증). 특히 두 copy charge stage에서 첫 copy의 restraint가
`DV/DL`에 섞이지 않는지, `rk=0`인 λ=1 restraint window도 DUMPAVE를 쓰는지 짧은
run으로 먼저 확인합니다.

### Output

`build.sh`는 각 lambda 값을 해당 leg의 한 window로 만들고 `work/states.tsv`에
기록합니다. `anal.py`는 완료 기록이 있는 production output을 사용해 `mbar/`,
`free_energy.tsv`, `mbar_diagnostics.tsv`, `overlap_matrix.tsv`를 씁니다. Summary의
`leading_pme_net_charge_correction`은 0과 `not_applicable_neutral_ligand`를
기록하며, charged correction을 계산한 값이 아닙니다. Analysis가 실패하면 기존
결과를 유지하고 실패한 command의 최근 log를 stderr에 출력합니다.

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
| `./build.sh prepared_complex.pdb` | `Boresch restraint references from build/complex.rst7:` 아래에 여섯 reference 값을 출력하고 `FEP systems and windows: work`로 끝납니다. |
| `./run.sh --dry-run` | `Dry run: ABFE: 65 alchemical states, 10000000 production steps per window` |
| `./run.sh` | `ABFE production completed: work/restraint, work/charge, work/vdw`. `--preparation-only`는 `ABFE preparation completed: work`로 끝납니다. |
| `python3 anal.py` | `ABFE free-energy results: work/free_energy.tsv`. 모든 window의 production이 끝나야 실행됩니다. |

`free_energy.tsv`의 행 의미와 cycle 부호는
[ABFE tutorial README](../../../1_Simulation/5_FEP/5.2_ABFE/README.md#analysis와-output)와 같습니다.
Overlap 기준은 [FEP tutorial README](../../../1_Simulation/5_FEP/README.md#결과-해석)를
따릅니다. Overlap이 낮은 stage는 해당 `*_lambdas` 구간에 값을 추가하고 새
`WORK_DIR`에서 다시 build합니다.

### Config 선택값

| Option | 현재 지원값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `ligand_force_field` | `GAFF2`만 지원 | `GAFF2` | Ligand parameter 형식을 결정합니다. |
| `charge_method` | precharged `RESP` MOL2만 지원 | `RESP` | MOL2의 RESP charge를 그대로 사용합니다. |
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

`[alchemical]`의 soft-core 다섯 값은 vdW stage의 heating, equilibration,
production input에만 들어갑니다. Charge stage는 `ifsc=0`이라 쓰지 않습니다. 세
`gti_*`가 모두 0이면 `pmemd.cuda` 기본값과 같아 mdin에 쓰지 않고, 하나라도 1이면
셋을 모두 씁니다. `gti_lam_sch=1`이면 `pmemd.cuda`의 기본값이 `gti_ele_sc=1`,
`gti_vdw_sc=1`, `scalpha=0.2`, `scbeta=50.0`으로 바뀝니다(Amber26 §27.1.7.1,
p.559–560). Template은 config 값을 그대로 쓰므로 네 값을 함께 정합니다. Window
directory에 `lambda.sch`가 없으면 `pmemd.cuda` 기본 `smooth_step2` schedule을
사용합니다. 기본값이 아닌 조합은 `pmemd.cuda`로 실행하지 않았습니다(미검증). Build가
사용한 값은 `work/resolved_config.toml`의 `[alchemical]`에 기록됩니다.

`restraint_lambdas`, `charge_lambdas`, `vdw_lambdas`는 0.0과 1.0을 포함하는
중복 없는 오름차순 list를 직접 지정합니다. Auto/file mode는 없습니다.
`production_segments`는 `1`만 지원합니다.

### 숫자 option

| Key | 기본값 | Unit | Stage | 효과 |
| --- | --- | --- | --- | --- |
| `ligand_net_charge` | `0` | e | Build, run, analysis | 0만 허용합니다. MOL2 charge 합과 0.01 e 이내로 맞아야 합니다. |
| `complex_box_distance` | `14.0` | Å | Build | Complex leg의 solute와 box edge 사이 `solvatebox` buffer |
| `solvent_box_distance` | `20.0` | Å | Build | Solvent leg의 `solvatebox` buffer |
| `salt_concentration` | `150.0` | mM | Build | 중화 ion 뒤 leg마다 `water 수 × M / 55.5`(반올림)개의 NaCl pair를 더합니다. |
| `temperature` | `300.0` | K | MD stage, `anal.py` | `temp0`, `edgembar --temp`와 Boresch correction의 온도 |
| `pressure` | `1.0` | bar | NPT stage | `pres0` |
| `timestep` | `2.0` | fs | MD stage | `dt`. 2 fs보다 크면 build가 거부합니다. |
| `minimization_steps` | `5000` | cycles | Minimization | `maxcyc` |
| `minimization_steepest_steps` | `2500` | cycles | Minimization | `ncyc`. 이후는 conjugate gradient입니다. |
| `heating_initial_temperature` | `0.0` | K | Heating | `tempi` |
| `heating_steps` | `250000` | steps | Heating | NVT 500 ps |
| `equilibration_steps` | `500000` | steps | Equilibration | 1 ns |
| `production_steps_per_window` | `10000000` | steps | Production | Window당 20 ns |
| `trajectory_interval_steps` | `5000` | steps | MD stage | `ntwx`. Production은 window당 2,000 frames입니다. |
| `energy_interval_steps` | `5000` | steps | MD stage | mdout 기록 간격 `ntpr` |
| `restart_interval_steps` | `5000` | steps | MD stage | `ntwr` |
| `mbar_interval_steps` | `5000` | steps | Production | Charge·vdW의 `bar_intervall`과 restraint window의 DUMPAVE 기록 간격 |
| `standard_state_concentration` | `1.0` | mol/L | Analysis | Boresch correction의 standard volume `1660.539 / C` Å³ |
| `distance_force` | `5.0` | kcal/mol/Å² | Complex window | Distance restraint의 AMBER `rk`. Correction은 `K=2×rk`를 씁니다. |
| `angle_force` | `100.0` | kcal/mol/rad² | Complex window | 두 angle restraint의 `rk` |
| `torsion_force` | `100.0` | kcal/mol/rad² | Complex window | 세 dihedral restraint의 `rk` |

### Engine 선택

`AMBER_ENGINE`이 설정되어 있으면 이를 사용하며, 없으면 build가 기록한
`work/resolved_config.toml`의 `run.engine`을 읽습니다. 허용하는 executable 이름은
`pmemd.cuda`이며 설치 경로를 지정할 수 있습니다. 빈 override, 누락된 engine 설정과
지원하지 않는 executable은 기본값으로 대체하지 않고 error로 중단합니다. Runner가
`helpers/config_utils.py`를 자동 호출해 이 설정을 읽습니다.

### Window 재실행과 병렬 실행

Run은 선택한 environment/leg/window에만 write scope를 등록하므로 서로 독립적인
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
| `minimization` | `minimize.in` |
| `heating` | `heat.in.template` |
| `equilibration` | `equilibrate.in.template` |
| `production` | `production.in.template` |

모든 environment, stage leg와 lambda window에 같은 값을 씁니다. Window별 값은 지정할 수 없습니다.

### 문제 해결

| Message | 원인과 조치 |
| --- | --- |
| `[restraints] protein_anchor_1, ... must be set` | Protein anchor가 비어 있습니다. 위 anchor 선택 기준으로 mask를 지정합니다. |
| `Anchor mask must select exactly one atom` | Anchor mask가 atom 하나를 고르지 않습니다. `:102@CA`처럼 residue와 atom 이름을 함께 씁니다. |
| `Boresch angle_a is ... deg ..., outside 30-150 deg` | Anchor가 직선에 가깝습니다. 다른 anchor를 고르고 새 `WORK_DIR`에서 다시 build합니다. |
| `Ligand residue ... was not found in ...` | Complex PDB의 ligand residue 이름이 `ligand_residue_name`과 다릅니다. |
| `ABFE restraint windows exist only for the complex system` | `--system solvent --stage restraint` 조합은 없습니다. Restraint stage는 complex만 선택합니다. |
| `Completed equilibration output is required` | `--production-only` 전에 `--preparation-only`가 해당 window를 끝내지 않았습니다. |

## English

This template creates double-decoupling ABFE windows for ligand restraint
removal and charge and vdW decoupling in complex and solvent environments.
`anal.py` combines the restraint correction and each alchemical contribution.

Restraint and charge use an 11-state schedule and vdW a 16-state schedule, for
65 windows in total (11 restraint, 22 charge, 32 vdW). Each window runs
10,000,000 production steps and records MBAR energies with
`bar_intervall=5000`.

### Required inputs

- A reviewed complex PDB with the ligand, passed to `build.sh`
- A precharged MOL2 and frcmod whose residue and atom names match the complex
  (set in `config.toml`)
- Three protein anchors and three ligand anchors, each selecting exactly one
  atom. Protein anchors have no default.

Before window generation, the three ligand anchors must belong to `ligand_mask`
and the three protein anchors must lie outside it. Each mask must select one of
six distinct atoms.

Only neutral ligands are supported. `build.ligand_net_charge` must be integer
zero, and the MOL2 charge sum must match within 0.01 e. Build and dry-run check
this with ParmEd before copying or generating outputs. Legacy charged configs
are also rejected by input generation, run and analysis.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it. Required
programs and the default computation (65 windows, 1,300 ns of total production)
are listed in the [FEP template README](../README.md#required-programs).

### Choosing Boresch anchors

Build and dry-run stop before tleap while `protein_anchor_1`–`3` are empty.

- Pick rigid backbone atoms near the binding pocket for the protein anchors, such
  as helix or sheet `CA` atoms. Avoid flexible loops and side-chain tips. The
  three atoms must not lie on one line.
- Pick ligand anchors among heavy atoms of a rigid part, such as a ring.
- From the starting structure the build computes the distance r (P1–L1), the
  angles θA (P2–P1–L1) and θB (P1–L1–L2), and three dihedrals (P3–P2–P1–L1,
  P2–P1–L1–L2, P1–L1–L2–L3). P and L numbers are `protein_anchor_N` and
  `ligand_anchor_N`.
- The build stops without writing windows if θA or θB is outside 30°–150°.
  Near-collinear anchors make the restraint unstable, and the analytical
  standard-state correction divides by sin θA·sin θB. The same range applies to
  the P3–P2–P1 and L1–L2–L3 angles that define the dihedrals.
- The build prints the six reference values and the path of
  `work/restraints.tsv`. Check that they match the intended anchor layout before
  running.

The angle check runs after the tleap build. If it stops there, fix the anchors,
then remove `work/` or set a new `WORK_DIR` and build again.

### Run

```bash
./build.sh prepared_complex.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

| File | Role |
| --- | --- |
| `download.sh` | `download.sh PDB_ID` downloads an optional source complex |
| `config.toml` | Force fields, ligand files, masks, anchors, MD lengths and lambda schedules |
| `build.sh` | Creates the double-decoupling systems and 65 windows |
| `run.sh` | Runs the windows of each stage |
| `anal.py` | Combines the restraint correction and alchemical contributions with FE-ToolKit `edgembar-amber2dats.py` and `edgembar` |

`helpers/` contains leaf-local internal code called automatically by
`build.sh`, `run.sh`, or `anal.py`; `helpers/result_generation.py` also supports
a separate integrity check before an external consumer reads results.

### Stages and restraints

The build computes one distance, two angle and three torsion references from the
initial structure. Default force constants are 5 kcal/mol/Å² for the distance
and 100 kcal/mol/rad² for angles and torsions; the standard state is 1 M and
300 K. The build reads mask numbers from the topology.

| Stage | Topology | Key settings |
| --- | --- | --- |
| Restraint | `complex.parm7` | No TI; `DISANG` force constants scaled by `(1-λ)`; restraint values written to `production.restraint.dat` |
| Charge | `{complex,solvent}_charge.parm7` (two ligand copies) | `timask1`=first copy, `timask2`=`crgmask`=second copy, `ifsc=0` |
| vdW | `{complex,solvent}_uncharged.parm7` | `timask1=scmask1=ligand_mask`, `timask2=''`, `ifsc=1`, `aces26=1` |

The charge stage is linear-scaling TI (Amber manual 27.1.8.1). `build.sh` uses
LEaP to append an identical ligand copy after the solute in `complex_charge` and
`solvent_charge`, with the same salt counts. Original solute atom indices, and
therefore the restraint anchors, are unchanged. `helpers/generate_inputs.py`
checks names, charges, coordinates, and restraint atoms of both copies, then
writes residue-number masks. Because pmemd applies `crgmask` to both endpoints,
the same ligand in both `timask1` and `timask2` would give a zero charge leg.

The restraint stage is ordinary MD. ACES26 always scales SC/CC `ele,vdw` with
lambda (manual 27.1.7.4), so soft-core TI cannot change only the restraint.
`anal.py` recomputes the full-strength restraint energy `U` from DUMPAVE and
uses `(1-λj)U` for state j in MBAR. This restraint energy matched AmberTools 26
sander within 0.02 kcal/mol; `pmemd.cuda` runs are unverified. In a short run,
first check that the restraint on the first copy does not enter `DV/DL` in the
two-copy charge stage and that the λ=1 restraint window (`rk=0`) still writes
DUMPAVE.

### Outputs

`build.sh` turns each lambda value into one window of the corresponding leg and
records it in `work/states.tsv`. `anal.py` uses production outputs with a
completion record and writes `mbar/`, `free_energy.tsv`, `mbar_diagnostics.tsv`,
and `overlap_matrix.tsv`. The summary records zero and
`not_applicable_neutral_ligand` for `leading_pme_net_charge_correction`; this is
not a calculated charged correction. A failed analysis keeps the previous
results and prints recent log lines of the failed command to stderr.

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
| `./build.sh prepared_complex.pdb` | Prints six reference values under `Boresch restraint references from build/complex.rst7:` and ends with `FEP systems and windows: work`. |
| `./run.sh --dry-run` | `Dry run: ABFE: 65 alchemical states, 10000000 production steps per window` |
| `./run.sh` | `ABFE production completed: work/restraint, work/charge, work/vdw`; `--preparation-only` ends with `ABFE preparation completed: work`. |
| `python3 anal.py` | `ABFE free-energy results: work/free_energy.tsv`; it requires finished production in every window. |

The `free_energy.tsv` rows and cycle signs are the same as in the
[ABFE tutorial README](../../../1_Simulation/5_FEP/5.2_ABFE/README.md#analysis-and-outputs).
See the [FEP tutorial README](../../../1_Simulation/5_FEP/README.md#interpreting-the-results)
for the overlap guideline. For a stage with low overlap, add values in that
region of its `*_lambdas` list and rebuild in a new `WORK_DIR`.

### Config choices

| Option | Current support | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `ligand_force_field` | `GAFF2` only | `GAFF2` | Selects the ligand parameter format. |
| `charge_method` | Precharged `RESP` MOL2 only | `RESP` | Uses the RESP charges already present in the MOL2 file. |
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

The five soft-core values in `[alchemical]` go only into the vdW-stage heating,
equilibration and production inputs; the charge stage uses `ifsc=0` and omits
them. While all three `gti_*` are 0 they equal the `pmemd.cuda` defaults and are
not written; if any is 1, all three are written. With `gti_lam_sch=1`,
`pmemd.cuda` changes its defaults to `gti_ele_sc=1`, `gti_vdw_sc=1`,
`scalpha=0.2` and `scbeta=50.0` (Amber26 §27.1.7.1, p.559–560). The template
always writes the config values, so set all four together. Without `lambda.sch`
in the window directory, `pmemd.cuda` uses its default `smooth_step2` schedule.
Non-default combinations have not been run with `pmemd.cuda` (unverified). The
values used by the build are recorded under `[alchemical]` in
`work/resolved_config.toml`.

`restraint_lambdas`, `charge_lambdas`, and `vdw_lambdas` are explicit, unique,
increasing lists spanning 0.0 to 1.0. They have no auto/file mode.
`production_segments` supports only `1`.

### Numeric options

| Key | Default | Unit | Stage | Effect |
| --- | --- | --- | --- | --- |
| `ligand_net_charge` | `0` | e | Build, run, analysis | Only 0 is accepted; must match the MOL2 charge sum within 0.01 e. |
| `complex_box_distance` | `14.0` | Å | Build | `solvatebox` solute-to-edge buffer of the complex leg |
| `solvent_box_distance` | `20.0` | Å | Build | `solvatebox` buffer of the solvent leg |
| `salt_concentration` | `150.0` | mM | Build | After neutralization, adds `waters × M / 55.5` (rounded) NaCl pairs to each leg. |
| `temperature` | `300.0` | K | MD stages, `anal.py` | `temp0`, `edgembar --temp` and the Boresch-correction temperature |
| `pressure` | `1.0` | bar | NPT stages | `pres0` |
| `timestep` | `2.0` | fs | MD stages | `dt`; values above 2 fs are rejected by the build. |
| `minimization_steps` | `5000` | cycles | Minimization | `maxcyc` |
| `minimization_steepest_steps` | `2500` | cycles | Minimization | `ncyc`; conjugate gradient follows. |
| `heating_initial_temperature` | `0.0` | K | Heating | `tempi` |
| `heating_steps` | `250000` | steps | Heating | 500 ps NVT |
| `equilibration_steps` | `500000` | steps | Equilibration | 1 ns |
| `production_steps_per_window` | `10000000` | steps | Production | 20 ns per window |
| `trajectory_interval_steps` | `5000` | steps | MD stages | `ntwx`; 2,000 production frames per window |
| `energy_interval_steps` | `5000` | steps | MD stages | mdout interval `ntpr` |
| `restart_interval_steps` | `5000` | steps | MD stages | `ntwr` |
| `mbar_interval_steps` | `5000` | steps | Production | `bar_intervall` for charge/vdW and the DUMPAVE interval of restraint windows |
| `standard_state_concentration` | `1.0` | mol/L | Analysis | Standard volume `1660.539 / C` Å³ in the Boresch correction |
| `distance_force` | `5.0` | kcal/mol/Å² | Complex windows | AMBER `rk` of the distance restraint; the correction uses `K=2×rk`. |
| `angle_force` | `100.0` | kcal/mol/rad² | Complex windows | `rk` of the two angle restraints |
| `torsion_force` | `100.0` | kcal/mol/rad² | Complex windows | `rk` of the three dihedral restraints |

### Engine selection

`AMBER_ENGINE` overrides `run.engine` in the build-generated
`work/resolved_config.toml`. Accepted executable names are `pmemd.cuda`;
installation paths are accepted. Empty overrides, missing engine settings and
unsupported executables fail instead of falling back to a default. The runner
invokes `helpers/config_utils.py` automatically to read this setting.

### Rerunning and parallel windows

Run registers write scopes only for the selected environment/leg/window paths,
so independent windows can run concurrently. Stages with a completion record are
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
| `minimization` | `minimize.in` |
| `heating` | `heat.in.template` |
| `equilibration` | `equilibrate.in.template` |
| `production` | `production.in.template` |

Every environment, leg and lambda window gets the same values; per-window values are not supported.

### Troubleshooting

| Message | Cause and fix |
| --- | --- |
| `[restraints] protein_anchor_1, ... must be set` | Protein anchors are empty. Set masks using the anchor guidance above. |
| `Anchor mask must select exactly one atom` | An anchor mask does not select one atom. Give residue and atom name, such as `:102@CA`. |
| `Boresch angle_a is ... deg ..., outside 30-150 deg` | The anchors are nearly collinear. Choose other anchors and rebuild in a new `WORK_DIR`. |
| `Ligand residue ... was not found in ...` | The ligand residue name in the complex PDB differs from `ligand_residue_name`. |
| `ABFE restraint windows exist only for the complex system` | `--system solvent --stage restraint` does not exist; select the restraint stage only for complex. |
| `Completed equilibration output is required` | `--preparation-only` has not finished that window before `--production-only`. |
