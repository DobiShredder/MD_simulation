# T4 lysozyme RBFE / T4 lysozyme RBFE

![RBFE common core와 soft-core atom / RBFE common core and soft-core atoms](../../../assets/simulation/rbfe_alchemical_atoms.svg)

*Ring carbon 6개와 ring hydrogen 5개는 common core로 linear mixing되고, BNZ의 H1과 MBN의 methyl group(C1, H1–H3)만 soft-core입니다. / The ring carbons and five ring hydrogens form a linearly mixed common core; only BNZ H1 and the MBN methyl group (C1, H1–H3) are soft-core.*


## 한국어

T4 lysozyme L99A에서 benzene을 toluene으로 바꿉니다. 같은 transformation을
protein complex와 물에서 각각 계산하고 두 값의 차이로 `ΔΔG_bind`를 구합니다.
두 ligand는 중성이므로 이 예제에는 net-charge correction이 없습니다.

### Script 역할

| 파일 | 역할 | 주요 output |
| --- | --- | --- |
| `download.sh` | 4W53 PDB/mmCIF와 ligand SDF download | `structure/` |
| `prepare.py` | Protein과 bound BNZ/MBN heavy atom 분리, ligand atom name을 SDF template 이름으로 변경 | `protein.pdb`, `bound_*.pdb` |
| `build.sh` | Ideal SDF에서 GAFF2/AM1-BCC parameter 생성, complex 및 solvent topology 생성 | `work/build/`, `states.tsv` |
| `generate_inputs.py` | `inputs/atom_mapping.tsv`로 common core 확인, core 좌표 동기화, 22개 window input 생성; `build.sh`가 호출 | `work/build/*_core.rst7`, `work/complex/`, `work/solvent/` |
| `run.sh` | Minimization, heating, equilibration, production 실행 | Window별 restart, trajectory, log |
| `anal.py` | Cross-state energy 추출, FE-ToolKit MBAR/BAR 실행과 두 environment 조합 | `free_energy.tsv`, `overlap_matrix.tsv` |

```bash
./download.sh
python3 prepare.py structure/4W53.raw.pdb structure/protein.pdb
./build.sh structure/protein.pdb
./run.sh
python3 anal.py
```

필요한 program과 계산량(22 windows, `pmemd.cuda` 88회, production 합계 22 ns)은
[FEP README](../README.md#필요한-program)에 있습니다.

### Ligand 준비

4W53의 MBN에는 hydrogen이 없습니다. `build.sh`는 `structure/BNZ_ideal.sdf`와
`structure/MBN_ideal.sdf`(RCSB ideal coordinate, hydrogen 포함)에
`antechamber -at gaff2 -c bcc -nc 0`을 실행해 `bnz.mol2`와 `mbn.mol2`를 만듭니다.
`prepare.py`는 crystal MBN heavy atom 7개를 `bound_mbn.pdb`로, methyl carbon을
뺀 ring 6개를 `bound_bnz.pdb`로 저장하고 atom name을 mol2 template 이름
(`C1`–`C7`, `C1`–`C6`)으로 바꿉니다. tleap의 `loadpdb`는 crystal pose의 heavy
atom 위치를 사용하고 빠진 hydrogen은 mol2 template의 internal coordinate로
만듭니다. `build.sh`는 생성된 `complex.pdb`와 `solvent.pdb`에서 BNZ 12개,
MBN 15개 atom을 확인하고 다르면 중단합니다.

### Common core

`inputs/atom_mapping.tsv`는 BNZ ring C1–C6, H2–H6을 MBN의 C2–C7, H4–H8에
대응시킵니다. 대응된 11개 atom은 common core로 두 end state의 parameter를
lambda에 따라 linear mixing합니다. 대응되지 않은 BNZ H1과 MBN methyl
C1/H1/H2/H3만 soft-core가 되며, `generate_inputs.py`가 이 차이로
`scmask1=':BNZ@H1'`, `scmask2=':MBN@C1,H1,H2,H3'`를 만듭니다.

Amber manual은 common atom이 두 state에서 같은 순서와 같은 시작 좌표를 갖도록
요구하고(Amber26 §27.1.6, p.555, sander 기준), pmemd용 준비 예시도 대응 atom의
좌표를 같게 두도록 합니다(§27.1.8.1, p.568). pmemd가 common atom을 대응시키는
방식은 실제 실행으로 확인하지 않았습니다. `generate_inputs.py`는 mapping 순서를
검사하고, MBN core 좌표를 BNZ 대응 atom에 복사해
`work/build/{complex,solvent}_core.rst7`을 만듭니다. Window는 이 restart에서
시작합니다. Ring carbon은 같은 crystal 좌표에서 오고 tleap이 만든 ring H는 약
0.01 Å 이내로 일치하므로, 차이가 0.1 Å를 넘으면 mapping 또는 preparation 오류로
보고 중단합니다. BNZ H1은 tleap이 ring C1에서 methyl 방향(차이 약 0.6°)으로
놓습니다.

Common core가 끝까지 결합 상태를 유지하므로 ligand 전체가 동시에 약하게
결합되는 구간이 없습니다. 그래서 binding site에서 ligand를 붙잡는 별도
restraint를 두지 않습니다.

### Analysis와 output

`anal.py`는 AmberTools 26의 `edgembar-amber2dats.py`로 각 window의
`production.out`에서 matrix를 추출한 뒤 full matrix가 있으면 MBAR를 사용합니다.
먼 lambda state의 energy가 수치 범위를 벗어나 mdout에 `********`로 기록되면
extractor는 해당 window의 현재 state와 인접 state energy만 저장합니다. 이 경우
모든 인접 pair가 있으면 BAR로 전환하며 임의의 energy로 `********`를 대체하지
않습니다. Complex와 solvent는 각각 사용 가능한 estimator를 선택하고
`free_energy.tsv`에 이를 기록합니다. FE-ToolKit의 automatic equilibration,
correlated-sample stride와 20회 bootstrap을 사용합니다.

| Output | 내용 |
| --- | --- |
| `work/free_energy.tsv` | Complex, solvent와 `ΔΔG_bind`; MBAR/BAR estimator와 uncertainty 포함 |
| `work/mbar_diagnostics.tsv` | State별 sample 수, 제거한 equilibration과 stride |
| `work/overlap_matrix.tsv` | Lambda state 사이의 overlap |
| `work/mbar/rbfe_report.html` | FE-ToolKit convergence report |

`complex_delta_g`와 `solvent_delta_g`는 같은 방향의 transformation입니다.
`relative_binding_delta_delta_g`는 `complex_delta_g - solvent_delta_g`입니다. 부호,
overlap 기준과 equilibration 판정은 [FEP README](../README.md#결과-해석)를 따릅니다.

### 성공 확인

| Command | 정상 종료 |
| --- | --- |
| `./build.sh structure/protein.pdb` | 두 environment마다 `11 common-core atoms`, `scmask1=':BNZ@H1'`, `scmask2=':MBN@C1,H1,H2,H3'`를 출력하고 `Created 22 RBFE windows: work/complex, work/solvent`로 끝납니다. |
| `./run.sh` | `RBFE production completed: work/complex, work/solvent`로 끝납니다. |
| `python3 anal.py` | `RBFE free-energy results: work/free_energy.tsv`로 끝나고 `free_energy.tsv`에 세 행이 있습니다. |

`full MBAR matrix is unavailable; using adjacent-state BAR.`가 출력되면 그
environment는 BAR로 계산됩니다. 이때는 estimator column에 `BAR`가 기록됩니다.

Analysis가 실패하면 기존 결과를 유지하고 실패한 command의 최근 log를 stderr에
출력합니다. 외부 script에서 결과를 읽기 전에는 다음 검사를 사용합니다.

```bash
python3 helpers/result_generation.py work
```

완료 기록은 `work/.analysis-generation.json`입니다. `work/.analysis.pending`이
남으면 게시가 중간에 멈춘 것이므로 GUIDE.md 부록의 `.output.pending`과 같은
방식으로 처리합니다.

### 주요 option

Complex와 solvent environment는 각각 lambda 0.0–1.0의 11개 window를 사용합니다.
`timask1=':BNZ'`/`timask2=':MBN'`는 두 end state를, `scmask1`/`scmask2`는 위
common core에서 빠진 soft-core atom을 지정합니다. 각 window는 200 ps heating,
100 ps NPT equilibration과 1 ns production을 실행합니다.

Solvent environment는 `solvatebox system OPCBOX 20.0`을 사용합니다. 가장 짧은
box dimension도 `cut=10 Å`의 GPU neighbor list에 필요한 공간을 갖도록 ligand와
box edge 사이에 20 Å buffer를 둡니다. Complex environment는 protein 때문에
box가 충분히 크므로 12 Å buffer를 유지합니다.

Soft-core interaction은 Amber 26의 `aces26=1` 형식을 사용합니다.
`gti_sc_cc_energy_terms='ele,vdw,ele14,vdw14'`는 soft-core와 common region
사이의 nonbonded term을 lambda에 따라 바꿉니다. 이 형식은 `pmemd.cuda`에서
실행하며 `run.sh`는 다른 engine override를 거부합니다. Minimization의
`ntmin=2`는 `ifsc=1`에서 요구되는 steepest-descent algorithm을 사용합니다.

BNZ C1–H1은 common atom과 soft-core atom을 잇는 SHAKE bond입니다(`ntc=2`).
`pmemd.cuda`는 `tishake=0`(기본)에서 이런 bond가 있으면 `gti_syn_mass=3`을
기본으로 사용해 SHAKE bond 길이를 두 end state의 linear combination으로
맞춥니다(Amber26 §27.1.7.5, p.567). 그래서 `tishake`와 `gti_syn_mass`를
따로 지정하지 않고 2 fs timestep을 유지합니다. Common-core input의 실제
`pmemd.cuda` parsing, DV/DL과 MBAR block은 미검증입니다.

Production의 `ifmbar=1`과 `mbar_lambda`는 각 saved configuration의 potential
energy를 11개 state에서 평가합니다. 이 계산은 현재 window의 dynamics를
바꾸지 않고 cross-state energy를 mdout에 추가합니다. 더 긴 계산과 system별
설정은 `3_Templates/5_FEP/5.1_RBFE`에서 구성합니다.

### Window 재실행

완료 기록이 있는 stage는 production을 포함해 다시 실행하지 않습니다. 따라서
중단된 `./run.sh`를 다시 실행하면 남은 window부터 계산합니다. Partial output이
남은 window의 처리와 동시 실행 보호는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을
참고합니다.

### 문제 해결

| Message | 원인과 조치 |
| --- | --- |
| `ACES26 soft-core inputs must run with pmemd.cuda` 또는 `AMBER engine not found` | `AMBER_ENGINE`이 `pmemd.cuda`가 아니거나 Amber 26이 `PATH`에 없습니다. `pmemd.cuda` 경로를 지정합니다. |
| `Mapped core atoms differ by ... A (limit 0.1 A)` | `inputs/atom_mapping.tsv`가 다른 atom을 짝지었거나 `prepare.py` 결과가 바뀌었습니다. 원래 mapping을 복원합니다. |
| `Mapped MBN atoms are not in the same order as their BNZ partners` | Mapping 행이 BNZ atom 순서와 맞지 않습니다. 행을 BNZ 순서로 정렬합니다. |
| `ligand atom counts are BNZ=..., MBN=... (expected 12 and 15)` | `bound_*.pdb`의 atom 이름이 mol2 template와 다릅니다. `prepare.py`를 다시 실행하고 `tleap_*.log`를 봅니다. |
| `Build output already exists and was retained` | 이전 build가 남아 있습니다. `mv work work.old`로 옮긴 뒤 `./build.sh`를 다시 실행합니다. |
| `energy matrix cannot support adjacent-state BAR` | 인접 state energy가 없습니다. 해당 window `production.out`에 `MBAR Energy analysis` block이 있는지와 `work/mbar/extract.log`를 확인합니다. |

## English

This example transforms benzene into toluene in the T4 lysozyme L99A cavity and
repeats the same transformation in water. Their difference gives `ΔΔG_bind`.
Both ligands are neutral, so no net-charge correction is needed.

### Script roles

| File | Role | Main output |
| --- | --- | --- |
| `download.sh` | Downloads 4W53 PDB/mmCIF and ligand SDFs | `structure/` |
| `prepare.py` | Separates the protein and bound BNZ/MBN heavy atoms and renames ligand atoms to the SDF template names | `protein.pdb`, `bound_*.pdb` |
| `build.sh` | Creates GAFF2/AM1-BCC parameters from the ideal SDFs and the complex and solvent topologies | `work/build/`, `states.tsv` |
| `generate_inputs.py` | Checks the common core with `inputs/atom_mapping.tsv`, synchronizes core coordinates and writes 22 window inputs; called by `build.sh` | `work/build/*_core.rst7`, `work/complex/`, `work/solvent/` |
| `run.sh` | Runs minimization, heating, equilibration and production | Per-window restarts, trajectories and logs |
| `anal.py` | Extracts cross-state energies, runs FE-ToolKit MBAR/BAR and combines both environments | `free_energy.tsv`, `overlap_matrix.tsv` |

```bash
./download.sh
python3 prepare.py structure/4W53.raw.pdb structure/protein.pdb
./build.sh structure/protein.pdb
./run.sh
python3 anal.py
```

Required programs and the expected computation (22 windows, 88 `pmemd.cuda`
runs, 22 ns of total production) are listed in the
[FEP README](../README.md#required-programs).

### Ligand preparation

The 4W53 MBN ligand has no hydrogens. `build.sh` runs
`antechamber -at gaff2 -c bcc -nc 0` on `structure/BNZ_ideal.sdf` and
`structure/MBN_ideal.sdf` (RCSB ideal coordinates with hydrogens) to create
`bnz.mol2` and `mbn.mol2`. `prepare.py` writes the seven crystal MBN heavy atoms
to `bound_mbn.pdb` and the six ring atoms to `bound_bnz.pdb`, renaming them to
the mol2 template names (`C1`–`C7` and `C1`–`C6`). tleap `loadpdb` keeps the
crystal heavy-atom pose and builds the missing hydrogens from the template
internal coordinates. `build.sh` stops unless `complex.pdb` and `solvent.pdb`
contain 12 BNZ and 15 MBN atoms.

### Common core

`inputs/atom_mapping.tsv` maps BNZ ring C1–C6 and H2–H6 onto MBN C2–C7 and
H4–H8. These 11 atoms form the common core, whose parameters are mixed linearly
with lambda. Only the unmapped BNZ H1 and the MBN methyl C1/H1/H2/H3 are
soft-core, so `generate_inputs.py` writes `scmask1=':BNZ@H1'` and
`scmask2=':MBN@C1,H1,H2,H3'`.

The Amber manual requires common atoms to appear in the same order with
identical starting coordinates in both states (Amber26 §27.1.6, p.555, stated
for sander), and its pmemd preparation example also asks for identical
coordinates of corresponding atoms (§27.1.8.1, p.568). How pmemd pairs common
atoms has not been checked in an actual run. `generate_inputs.py` checks the
mapping order and copies the MBN core coordinates onto the mapped BNZ atoms in
`work/build/{complex,solvent}_core.rst7`, which every window starts from. The
ring carbons come from the same crystal atoms and the tleap-built ring hydrogens
agree within about 0.01 Å, so a gap above 0.1 Å is treated as a mapping or
preparation error. tleap places BNZ H1 along the ring C1 → methyl direction
(about 0.6° off).

Because the common core stays coupled at every lambda, the ligand is never
weakly bound as a whole, and no extra restraint is needed to keep it in the
binding site.

### Analysis and outputs

`anal.py` extracts the cross-state energy matrix from each window's
`production.out` with AmberTools 26 `edgembar-amber2dats.py` and uses MBAR for a
complete matrix. If an energy at a distant lambda state overflows to `********`,
the extractor retains current- and adjacent-state energies. The analysis then
uses BAR when every adjacent pair is available; it does not replace undefined
energies with arbitrary values. The complex and solvent estimators are selected
independently and recorded in `free_energy.tsv`. FE-ToolKit automatic
equilibration, correlated-sample stride and 20 bootstrap samples are used.

| Output | Content |
| --- | --- |
| `work/free_energy.tsv` | Complex, solvent and `ΔΔG_bind`, with MBAR/BAR estimator and uncertainty |
| `work/mbar_diagnostics.tsv` | Per-state sample counts, removed equilibration and stride |
| `work/overlap_matrix.tsv` | Overlap between lambda states |
| `work/mbar/rbfe_report.html` | FE-ToolKit convergence report |

`complex_delta_g` and `solvent_delta_g` describe the same transformation
direction. `relative_binding_delta_delta_g` is
`complex_delta_g - solvent_delta_g`. See the
[FEP README](../README.md#interpreting-the-results) for the sign, the overlap
guideline and the equilibration check.

### Success check

| Command | Normal finish |
| --- | --- |
| `./build.sh structure/protein.pdb` | Prints `11 common-core atoms`, `scmask1=':BNZ@H1'` and `scmask2=':MBN@C1,H1,H2,H3'` for each environment and ends with `Created 22 RBFE windows: work/complex, work/solvent`. |
| `./run.sh` | Ends with `RBFE production completed: work/complex, work/solvent`. |
| `python3 anal.py` | Ends with `RBFE free-energy results: work/free_energy.tsv`; `free_energy.tsv` has three rows. |

If `full MBAR matrix is unavailable; using adjacent-state BAR.` is printed, that
environment is estimated with BAR and its estimator column reads `BAR`.

A failed analysis keeps the previous results and prints recent log lines of the
failed command to stderr. Before reading results in an external script, run the
check below.

```bash
python3 helpers/result_generation.py work
```

Completion is recorded in `work/.analysis-generation.json`. A leftover
`work/.analysis.pending` means publication stopped midway; handle it like
`.output.pending` in the GUIDE.md appendix.

### Key options

The complex and solvent environments each use eleven lambda windows from 0.0 to
1.0. `timask1=':BNZ'` and `timask2=':MBN'` define the end states, and
`scmask1`/`scmask2` list the soft-core atoms outside the common core. Every
window runs 200 ps of heating, 100 ps of NPT equilibration, and one 1 ns
production run.

The solvent environment uses `solvatebox system OPCBOX 20.0`. The 20 Å
solute-to-box-edge buffer keeps its shortest dimension large enough for the GPU
neighbor list with the 10 Å cutoff. The protein complex retains its 12 Å buffer
because that box is already larger.

Soft-core interactions use the Amber 26 `aces26=1` format.
`gti_sc_cc_energy_terms='ele,vdw,ele14,vdw14'` scales the nonbonded terms between
soft-core and common regions with lambda. This format runs in `pmemd.cuda`, and
`run.sh` rejects other engine overrides. Minimization uses `ntmin=2` because
`ifsc=1` requires the steepest-descent algorithm.

BNZ C1–H1 is a SHAKE bond between a common and a soft-core atom (`ntc=2`). With
the default `tishake=0`, `pmemd.cuda` then defaults to `gti_syn_mass=3`, which
sets such bond lengths to the linear combination of the two end states
(Amber26 §27.1.7.5, p.567). The inputs therefore keep the 2 fs timestep
without setting `tishake` or `gti_syn_mass`. Parsing of the common-core inputs,
DV/DL, and MBAR blocks in an actual `pmemd.cuda` run remain unverified.

Production `ifmbar=1` and `mbar_lambda` evaluate every saved configuration at
all eleven lambda states. This adds cross-state energies to mdout without
changing the window's dynamics. Use `3_Templates/5_FEP/5.1_RBFE` for longer or
system-specific calculations.

### Rerunning windows

Stages with a completion record, production included, are not rerun, so
rerunning an interrupted `./run.sh` continues with the remaining windows. See
[GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for handling windows with partial output and
for concurrent-run protection.

### Troubleshooting

| Message | Cause and fix |
| --- | --- |
| `ACES26 soft-core inputs must run with pmemd.cuda` or `AMBER engine not found` | `AMBER_ENGINE` is not `pmemd.cuda`, or Amber 26 is not on `PATH`. Point it to `pmemd.cuda`. |
| `Mapped core atoms differ by ... A (limit 0.1 A)` | `inputs/atom_mapping.tsv` pairs different atoms, or the `prepare.py` output changed. Restore the original mapping. |
| `Mapped MBN atoms are not in the same order as their BNZ partners` | The mapping rows do not follow BNZ atom order. Sort them in BNZ order. |
| `ligand atom counts are BNZ=..., MBN=... (expected 12 and 15)` | Atom names in `bound_*.pdb` differ from the mol2 templates. Rerun `prepare.py` and read `tleap_*.log`. |
| `Build output already exists and was retained` | A previous build remains. Move it with `mv work work.old` and rerun `./build.sh`. |
| `energy matrix cannot support adjacent-state BAR` | Neighboring-state energies are missing. Check the window's `production.out` for `MBAR Energy analysis` blocks and read `work/mbar/extract.log`. |

## References / 참고 자료

- [RCSB PDB 4W53](https://www.rcsb.org/structure/4W53)
