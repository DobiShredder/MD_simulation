# Ratchet MD and umbrella sampling template

## 한국어

Ratchet MD(rMD)로 reaction coordinate가 목표 방향으로 증가하는 pathway를
만들고, ordered first-crossing frame을 umbrella window seed로 사용합니다.
rMD trajectory는 seed 생성에만 사용하며 PMF는 US production에서 계산합니다.

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다. 필요한 program은
[상위 README](../README.md#준비-사항)에 있습니다. 사용자가 직접 실행하는 파일은
이 directory와 `rmd/`, `us/`에 있습니다. `helpers/`는 `build.sh`, `run.sh` 또는
`anal.py`가 자동 호출하는 내부 code이며 직접 실행하지 않습니다.

### 실행

`download.sh PDB_ID`는 RCSB source PDB를 수정하지 않고 `structure/`에 받습니다.
Protonation, missing atom과 불필요한 chain은 build 전에 사용자가 정리합니다.

```bash
./build.sh prepared.pdb

cd rmd
./run.sh
python3 anal.py

cd ../us
./build.sh
./run.sh
```

| Script | 역할 |
| --- | --- |
| `build.sh` | rMD와 모든 umbrella window가 공유하는 topology와 restart를 만듭니다. |
| `rmd/run.sh` | Tutorial과 같은 minimization, heating, equilibration, PLUMED ABMD 순서로 pathway를 생성합니다. |
| `rmd/anal.py` | Seed restart를 추출합니다. |
| `us/build.sh` | `windows.tsv`의 `CENTER_A FORCE_KCAL_MOL_A2` row를 window directory로 변환합니다. |
| `us/run.sh` | 선택한 window를 실행합니다. |

자세한 option은 [`rmd/README.md`](rmd/README.md)와 [`us/README.md`](us/README.md)에
있습니다.

`AMBER_ENGINE`이 설정되어 있으면 이를 사용하며, 없으면 `work/resolved_config.toml`의
`run.engine`을 읽습니다. 허용하는 executable 이름은 `pmemd.cuda`이며 설치 경로를 지정할
수 있습니다. `rmd/`와 `us/` runner는 상위의 공통 `../work/resolved_config.toml`을
읽습니다.

실행 상태, 실패 후 재실행, 동시 실행 보호와 build 임시 directory는
[GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다. 선택한 US window는 서로 독립적으로
실행할 수 있지만, 전체 window를 만드는 `us/build.sh`와는 함께 실행할 수 없습니다.

### Config 선택값

`[umbrella] atom_mask_1`과 `atom_mask_2`는 각각 한 atom 또는 atom group을
선택합니다. 두 mask가 같은 atom을 포함하면 거부합니다. Group 쪽은 center of
mass를 사용합니다. rMD는 PLUMED `COM ATOMS=... NOPBC`와 `DISTANCE`를 쓰고, US
window는 AMBER restraint의 `iat=-1`, `igr1`/`igr2`, `ir6=0`을 씁니다. `rmd/anal.py`의
cpptraj `distance`도 기본값인 center of mass로 seed를 고르므로 세 단계가 같은
distance를 사용합니다. `NOPBC`는 `WHOLEMOLECULES`가 먼저 molecule을 이어 붙인다는
가정에 기대므로 group atom은 `[ratchet_md] whole_molecule_mask` 안에 있어야 합니다.
두 mask가 모두 한 atom이면 이전과 같은 input을 만듭니다. Window `distance.dat`는
group을 써도 time과 distance 두 column입니다. AmberTools 26 `sander`로 group
restraint의 DUMPAVE 값이 cpptraj center-of-mass distance와 같은 것을 확인했습니다.
`pmemd.cuda` 실행과 PLUMED `COM` parsing은 미검증입니다.

`[ratchet_md] target_distance`는 Å로 입력하고 PLUMED `ABMD TO`의 nm로
변환합니다. `kappa`는 PLUMED ABMD의 ρ 정의를 따르며 일반
harmonic distance force constant와 같은 양이 아닙니다.

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 일치하는 ion parameter를 선택합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `equilibration_ensemble` | `NVT`, `NPT` | `NPT` | Seed와 window equilibration의 `ntb`와 `ntp`를 설정합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Window production의 `ntb`와 `ntp`를 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 SHAKE를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | rMD와 모든 window의 heating `ig`입니다. `"random"`은 `ig=-1`입니다. 이후 equilibration, ratchet MD와 production은 `ig=-1`로 실행할 때마다 새 seed를 사용합니다. |

`windows_file`은 항상 명시적인 window center 목록을 읽습니다. Blank line과 `#`로
시작하는 comment line을 제외한 각 행은 whitespace로 구분한 `CENTER_A FORCE` 두 값이어야
합니다. 두 값은 양수이고 center는 중복 없이 오름차순이어야 합니다.
`production_segments`는 `1`만 지원합니다.

### 숫자 option

`target_distance`와 `kappa`는 위에서, density 범위는 [`rmd/README.md`](rmd/README.md)에서
설명합니다.

| Key | 기본값 | Unit | 적용 stage | 값을 바꾸면 |
| --- | ---: | --- | --- | --- |
| `solute_box_distance` | 14.0 | Å | Build | Solute와 box 경계 사이 water 두께입니다. 늘어난 distance에서도 solute가 box 안에 있도록 정합니다. |
| `salt_concentration` | 150.0 | mM | Build | Salt formula unit 수 = round(water 수 × 농도(M) / 55.5)입니다. |
| `temperature` | 300.0 | K | rMD와 모든 window | `temp0`를 바꿉니다. PMF analysis 온도도 같게 맞춥니다. |
| `pressure` | 1.0 | bar | NPT stage | `pres0`를 바꿉니다. |
| `timestep` | 2.0 | fs | 모든 dynamics | AMBER `dt`(ps)로 기록합니다. 2 fs보다 크면 build가 중단됩니다. |
| `minimization_steps` | 5000 | cycle | rMD minimization 2회, window minimization | `maxcyc`를 바꿉니다. |
| `minimization_steepest_steps` | 2500 | cycle | 같은 minimization | `ncyc`입니다. 이 수만큼 steepest descent 뒤 conjugate gradient로 바꿉니다. |
| `heating_initial_temperature` | 20.0 | K | rMD와 window heating | `tempi`와 `TEMP0` ramp 시작값입니다. |
| `heating_steps` | 250000 | step | rMD와 window heating | Ramp 길이입니다(500 ps). |
| `equilibration_steps` | 500000 | step | rMD와 window equilibration | 1 ns입니다. Window equilibration은 distance restraint만 사용합니다. |
| `production_steps` | 10000000 | step | Window production | Window당 20 ns입니다. |
| `trajectory_interval_steps` | 5000 | step | Ratchet MD를 뺀 모든 dynamics | `ntwx`입니다. 기본값에서 window `production.nc`는 2,000 frame입니다. |
| `energy_interval_steps` | 5000 | step | 모든 dynamics | `ntpr`입니다. |
| `restart_interval_steps` | 5000 | step | 모든 dynamics | `ntwr`입니다. |
| `seed_max_error` | 0.75 | Å | `rmd/anal.py` | Window center와 seed frame distance의 허용 차이입니다. 키우면 seed가 center에서 더 멀어질 수 있습니다. |
| `distance_output_interval_steps` | 500 | step | Window production | `DUMPFREQ`입니다. 기본값은 1 ps마다 기록해 window당 약 20,000 row입니다. |
| `path_generation_steps` | 500000 | step | Ratchet MD | `ratchet.in`의 `nstlim`입니다(1 ns). Target에 도달하지 못하면 늘립니다. |
| `output_interval_steps` | 500 | step | Ratchet MD | PLUMED `PRINT STRIDE`와 ratchet `ntwx`입니다. `work/ratchet.dat`와 `work/ratchet.nc`를 1 ps마다 기록해 seed 후보 frame이 1,000개입니다. 줄이면 후보가 늘어납니다. |

Config에 없는 고정값은 positional restraint 10(rMD solvent minimization), 2(rMD와
window heating), 1(rMD equilibration) kcal·mol⁻¹·Å⁻², `cut=10.0` Å, `gamma_ln=1.0` ps⁻¹,
`taup=2.0` ps입니다.

### Window table과 seed generation

`rmd/anal.py`와 `us/build.sh`는 `resolved_config.toml`의 `umbrella.windows_file`을 같은
leaf 기준으로 읽습니다. 기본값은 `us/windows.tsv`입니다. Seed 추출은 table 사본을
`rmd/work/seeds/windows.tsv`에 저장합니다. Builder는 이 사본과 실제 table이 같은지,
`seeds.tsv`의 개수·순서·center가 같은지 검사한 뒤 window를 만듭니다.

같은 seed로 window를 다시 만들 때는 `us/build.sh`와 `us/run.sh`에 같은 새
`WORK_DIR`(기본 `work`)을 지정합니다. `windows.tsv`의 center나 force를 바꾸면
`us/build.sh`가 seed 사본과 다르다고 거부하므로 seed generation부터 다시 합니다.
Parent build, rMD와 seed 추출은 `work/`, `rmd/work/` 고정 경로를 쓰므로 leaf를 별도
directory에 복사해 새 계산을 시작합니다.

### 계산량과 결과 판단

기본 `windows.tsv`는 4–22 Å의 19개 window입니다. rMD는 engine 5회(minimization 2,
heating, equilibration, ratchet MD)로 0.5 + 1 + 1 = 2.5 ns를 계산합니다. Window는
19개 × 4회 = 76회, window당 0.5 + 1 + 20 = 21.5 ns, 합계 408.5 ns(production 380 ns)입니다.
각 실행은 `pmemd.cuda` process 하나가 GPU 하나를 사용합니다. `us/run.sh`는 선택한
window를 차례로 실행하므로, GPU가 여러 개이면 `--windows START-END`를 나눠 별도
process로 실행하고 GPU는 scheduler나 `CUDA_VISIBLE_DEVICES`로 정합니다. 실행 시간은
GPU와 atom 수에 따라 달라집니다.

결과 판단 기준은 tutorial [US README](../../../1_Simulation/2_US/README.md#결과-판단)와
같습니다. PMF는 [US PMF analysis](../../../2_Analysis/7_Enhanced_Sampling/7.1_Umbrella_Sampling/README.md)의
`WINDOWS_DIR`, `PRODUCTION_TIMESTEP_PS`, `TEMPERATURE_KELVIN`과 PMF grid를 이 template
값에 맞춘 뒤 계산합니다.

### 자주 생기는 문제

남은 파일 처리는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 따릅니다.

| Message | 조치 |
| --- | --- |
| `Run ../build.sh first: ../work/resolved_config.toml` | Leaf root에서 `build.sh`를 먼저 실행합니다. |
| `rMD input generation failed; see the Config error above.` | Atom mask가 atom을 고르지 못했거나 두 mask가 겹칩니다. Message의 순서대로 `../work`를 옮기고 다시 build합니다. |
| `Equilibration density is outside ...` | `rmd/work/equil.out`의 `Density` 추세와 box 크기를 확인합니다. |
| `No ordered frame is within 0.750 Å of ...` | `rmd/work/ratchet.dat`에서 distance가 그 center에 도달했는지 봅니다. 도달했다면 `[ratchet_md] output_interval_steps`를 줄여 새 copy에서 다시 계산합니다. |
| `Window table changed since seed extraction` | Seed를 만든 뒤 `windows.tsv`를 고쳤습니다. 새 copy에서 seed generation부터 다시 합니다. |
| `Partial ... output is retained` | Message의 `mv` command로 남은 파일을 옮긴 뒤 같은 command를 다시 실행합니다. |

## English

Ratchet MD (rMD) generates a target-directed pathway along the configured
distance. Ordered first-crossing frames seed the umbrella windows; only the
umbrella production trajectories are used for the PMF.

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it. Required
programs are listed in the [parent README](../README.md#prerequisites).
User-facing entry points are in this directory and in `rmd/` and `us/`. `helpers/` contains
internal code called automatically by `build.sh`, `run.sh`, or `anal.py`; do not
run it directly.

### Running

`download.sh PDB_ID` retrieves an unmodified RCSB PDB into `structure/`;
protonation, missing atoms, and unwanted chains remain user preparation steps.

```bash
./build.sh prepared.pdb

cd rmd
./run.sh
python3 anal.py

cd ../us
./build.sh
./run.sh
```

| Script | Role |
| --- | --- |
| `build.sh` | Creates one topology and restart shared by rMD and every window. |
| `rmd/run.sh` | Generates the pathway with the tutorial minimization, heating, equilibration, and PLUMED ABMD sequence. |
| `rmd/anal.py` | Extracts seed restarts. |
| `us/build.sh` | Converts the `CENTER_A FORCE_KCAL_MOL_A2` rows of `windows.tsv` into window directories. |
| `us/run.sh` | Runs the selected windows. |

See [`rmd/README.md`](rmd/README.md) and [`us/README.md`](us/README.md) for their
options.

`AMBER_ENGINE` overrides `run.engine` in `work/resolved_config.toml`. The only
accepted executable name is `pmemd.cuda`; installation paths are accepted. The
`rmd/` and `us/` runners read the shared `../work/resolved_config.toml`.

See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state, reruns after failure,
concurrent-run protection, and the temporary build directory. Selected US windows
can run independently, but not together with a whole-window `us/build.sh`.

### Config choices

`[umbrella] atom_mask_1` and `atom_mask_2` each select one atom or an atom
group; masks that share atoms are rejected. A group side uses its center of
mass: rMD writes PLUMED `COM ATOMS=... NOPBC` plus `DISTANCE`, and the US
windows write an AMBER restraint with `iat=-1`, `igr1`/`igr2`, and `ir6=0`. The
cpptraj `distance` in `rmd/anal.py` selects seeds with its default
center-of-mass distance, so all three stages measure the same quantity.
`NOPBC` relies on `WHOLEMOLECULES` rebuilding the molecule first, so group atoms
must lie inside `[ratchet_md] whole_molecule_mask`. Two single-atom masks
produce the same inputs as before. Window `distance.dat` keeps the two columns,
time and distance, with groups. A short AmberTools 26 `sander` run confirmed
that the group-restraint DUMPAVE value matches the cpptraj center-of-mass
distance; `pmemd.cuda` runs and PLUMED `COM` parsing are unverified.

`[ratchet_md] target_distance` is entered in Å and converted to the PLUMED `ABMD TO` value in nm. `kappa`
follows the PLUMED ABMD ρ definition and is not an ordinary harmonic-distance
force constant.

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects matching LEaP water and ion parameters. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `equilibration_ensemble` | `NVT`, `NPT` | `NPT` | Sets `ntb` and `ntp` for seed and window equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Sets window-production `ntb` and `ntp`. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies SHAKE to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | Sets the heating `ig` for rMD and every window; `"random"` maps to `ig=-1`. Later equilibration, ratchet MD, and production use `ig=-1` and receive a new seed per invocation. |

`windows_file` always supplies an explicit list of window centers. After blank
lines and full-line `#` comments are skipped, each row must contain two
whitespace-separated values, `CENTER_A FORCE`. Both values must be positive, and
centers must be unique and in increasing order. `production_segments` supports
only `1`.

### Numeric options

`target_distance` and `kappa` are described above, and the density range in
[`rmd/README.md`](rmd/README.md).

| Key | Default | Unit | Stage | Effect of changing it |
| --- | ---: | --- | --- | --- |
| `solute_box_distance` | 14.0 | Å | Build | Water thickness between the solute and box edge; choose it so the solute stays inside the box at the largest distance. |
| `salt_concentration` | 150.0 | mM | Build | Salt formula units = round(water count × concentration (M) / 55.5). |
| `temperature` | 300.0 | K | rMD and every window | Sets `temp0`; use the same temperature in the PMF analysis. |
| `pressure` | 1.0 | bar | NPT stages | Sets `pres0`. |
| `timestep` | 2.0 | fs | All dynamics | Written as AMBER `dt` in ps; values above 2 fs stop the build. |
| `minimization_steps` | 5000 | cycles | Two rMD minimizations and the window minimization | Sets `maxcyc`. |
| `minimization_steepest_steps` | 2500 | cycles | Same minimizations | Sets `ncyc`: steepest descent for this many cycles, then conjugate gradient. |
| `heating_initial_temperature` | 20.0 | K | rMD and window heating | `tempi` and the start of the `TEMP0` ramp. |
| `heating_steps` | 250000 | steps | rMD and window heating | Ramp length (500 ps). |
| `equilibration_steps` | 500000 | steps | rMD and window equilibration | 1 ns; window equilibration uses only the distance restraint. |
| `production_steps` | 10000000 | steps | Window production | 20 ns per window. |
| `trajectory_interval_steps` | 5000 | steps | All dynamics except ratchet MD | Sets `ntwx`: 2,000 frames in each window `production.nc` by default. |
| `energy_interval_steps` | 5000 | steps | All dynamics | Sets `ntpr`. |
| `restart_interval_steps` | 5000 | steps | All dynamics | Sets `ntwr`. |
| `seed_max_error` | 0.75 | Å | `rmd/anal.py` | Allowed difference between a window center and the seed-frame distance; larger values allow seeds farther from the center. |
| `distance_output_interval_steps` | 500 | steps | Window production | Sets `DUMPFREQ`; the default writes every 1 ps, about 20,000 rows per window. |
| `path_generation_steps` | 500000 | steps | Ratchet MD | `nstlim` in `ratchet.in` (1 ns); increase it if the target is not reached. |
| `output_interval_steps` | 500 | steps | Ratchet MD | PLUMED `PRINT STRIDE` and the ratchet `ntwx`: `work/ratchet.dat` and `work/ratchet.nc` are written every 1 ps, giving 1,000 seed-candidate frames. Smaller values give more candidates. |

Fixed values outside the config are positional restraints of 10 (rMD solvent
minimization), 2 (rMD and window heating), and 1 (rMD equilibration)
kcal·mol⁻¹·Å⁻², `cut=10.0` Å, `gamma_ln=1.0` ps⁻¹, and `taup=2.0` ps.

### Window tables and seed generations

Both `rmd/anal.py` and `us/build.sh` read `umbrella.windows_file` from
`resolved_config.toml`, relative to the leaf directory; the default is
`us/windows.tsv`. Seed extraction saves a copy at `rmd/work/seeds/windows.tsv`.
Before creating windows, the builder checks this copy against the current table
and verifies the count, order, and centers in `seeds.tsv`.

To rebuild windows from the same seeds, set the same fresh `WORK_DIR` (default
`work`) for `us/build.sh` and `us/run.sh`. Changing a center or force in
`windows.tsv` makes `us/build.sh` reject the table as different from the seed
copy, so start again from seed generation. The parent build, rMD, and seed
extraction use the fixed `work/` and `rmd/work/` paths; start those changes from
a separate copy of the leaf.

### Computational cost and judging the result

The default `windows.tsv` has 19 windows from 4 to 22 Å. rMD runs the engine 5
times (two minimizations, heating, equilibration, ratchet MD) for
0.5 + 1 + 1 = 2.5 ns. The windows need 19 × 4 = 76 runs, 0.5 + 1 + 20 = 21.5 ns
per window, and 408.5 ns in total (380 ns production). Each run is one
`pmemd.cuda` process on one GPU. `us/run.sh` runs the selected windows in
order; with several GPUs, split `--windows START-END` across separate processes
and assign GPUs through the scheduler or `CUDA_VISIBLE_DEVICES`. Run time depends
on the GPU and the atom count.

Judge the results with the same criteria as the tutorial
[US README](../../../1_Simulation/2_US/README.md#judging-the-result). Before
computing the PMF with the
[US PMF analysis](../../../2_Analysis/7_Enhanced_Sampling/7.1_Umbrella_Sampling/README.md),
set its `WINDOWS_DIR`, `PRODUCTION_TIMESTEP_PS`, `TEMPERATURE_KELVIN`, and PMF
grid to match this template.

### Common problems

Handle retained files as described in the
[GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery).

| Message | Action |
| --- | --- |
| `Run ../build.sh first: ../work/resolved_config.toml` | Run `build.sh` in the leaf root first. |
| `rMD input generation failed; see the Config error above.` | An atom mask selected no atoms or the two masks overlap. Move `../work` aside and rebuild as the message describes. |
| `Equilibration density is outside ...` | Check the `Density` trend in `rmd/work/equil.out` and the box size. |
| `No ordered frame is within 0.750 Å of ...` | Check in `rmd/work/ratchet.dat` whether the distance reached that center. If it did, lower `[ratchet_md] output_interval_steps` and rerun in a fresh copy. |
| `Window table changed since seed extraction` | `windows.tsv` was edited after seed extraction. Start again from seed generation in a fresh copy. |
| `Partial ... output is retained` | Move the retained files with the `mv` command in the message and rerun the same command. |
