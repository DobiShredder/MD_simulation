# REST3 template

## 한국어

사용자가 준비한 protein PDB로 GROMACS/PLUMED REST3 HREX를 구성합니다. REST3는
REST2 scaling에 protein–water vdW를 조절하는 κ schedule을 추가합니다. 기본
schedule은 357 K까지 κ=1.0을 유지하고 450 K에서 1.020이 되도록 선형
보간합니다. 이 값은 universal default가 아니며 IDP와 force-field/water 조합별
pilot simulation에서 compactness와 exchange를 확인해야 합니다. κ 효과는
temperature predictor에 포함되지 않습니다.

기본 `temperature_mode = "list"`는 `config.toml`의 `temperatures`에 적힌 12개 effective
temperature(300–450 K, geometric 간격)를 사용하므로 system 크기와 관계없이
12 replica를 만듭니다. 1UBQ(tempered solute 1231 atom)에서 offline predictor가
예측한 이웃 exchange 확률은 κ 효과를 빼고 약 0.27–0.30입니다. Solute가 더 크면
첫 production segment의 exchange 통계를 확인하고 replica 수를 늘립니다.

### 파일 역할

| 파일 | 역할 |
| --- | --- |
| `download.sh` | RCSB PDB ID로 source PDB를 받고, 검증된 `repex-topology-parser` 0.2.2 source를 함께 내려받습니다. |
| `build.sh` | Solvated system, REST3 state table, parser 기반 replica topology와 MDP input을 만들고 검사합니다. |
| `run.sh` | Replica별 pre-production과 PLUMED `-hrex` production segment를 실행합니다. |
| `config.toml` | Force field, box, salt, stage 길이, temperature/κ schedule과 resource 설정입니다. |
| `helpers/` | `build.sh` 또는 `run.sh`가 자동 호출하는 leaf-local 내부 code입니다. Scale-one energy 검사 input(`energy_check.mdp`, `energy_selection.txt`)도 여기에 있으며 직접 실행하거나 수정하지 않습니다. |

이 directory의 runtime code는 별도로 복사해 사용할 수 있습니다. Python
dependency는 복사한 directory의 `requirements.txt`를 사용해 설치합니다.

### 실행

준비 사항: [family README의 준비 사항](../README.md#준비-사항)에 있는
PLUMED-patched `GROMACS 2024.3`(`gmx`, `gmx_mpi`)과 MPI launcher, AMBER
`tleap`, PLUMED CLI `plumed`(build), `requirements.txt`의 numpy·ParmEd(Python
3.10 이하는 tomli)와 `download.sh`가 받는 parser source가 필요합니다.
`build.sh`는 `TLEAP`, `PLUMED`를 executable override로 읽습니다.

```bash
./download.sh 1UBQ
./build.sh structure/1UBQ.pdb
replicas=$(awk 'NR > 1 {count++} END {print count + 0}' work/states.tsv)
./run.sh --cpus "$replicas" --gpus 1
```

각 replica의 preproduction은 tutorial과 같은 minimization과 NPT equilibration
순서이며 별도 heating stage는 사용하지 않습니다. `config.toml`의
`minimization_steepest_steps`와 `heating_initial_temperature`는 모든 template가
공유하는 config 검사 helper가 요구해 남겨 두지만 REST GROMACS input에는
적용되지 않습니다.

`GROMACS`와 `GROMACS_MPI`가 설정되어 있으면 각각 사용하며, 없으면
`work/resolved_config.toml`의 `run.equilibration_engine`과
`run.production_engine`을 읽습니다. Executable 이름은 각각 `gmx`, `gmx_mpi`이며
설치 경로를 지정할 수 있습니다. Build의 GROMACS command도 source config의 같은
선택과 override를 사용합니다. 빈 override, 누락된 engine 설정과 지원하지 않는
executable은 기본값으로 대체하지 않고 error로 중단합니다.

실행 상태, 실패 후 재실행, 동시 실행 보호는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을
참고합니다.

### 계산 resource와 길이

| 항목 | 기본값과 규칙 |
| --- | --- |
| Replica | 12개(`[replica_exchange] temperatures`)입니다. `temperature_mode = "auto"`이면 build가 정합니다. |
| `--cpus N` | 생략하면 replica 수 × `cpu_threads_per_replica`(1)입니다. Replica 수로 나누어져야 하며 replica마다 `N/replica 수` thread(`-ntomp`)를 씁니다. |
| `--gpus N` | 생략하면 `gpu_count`(1)입니다. 1–replica 수입니다. Minimization과 equilibration은 replica를 최대 N개씩 동시에 `gmx mdrun -ntmpi 1 -gpu_id (replica index mod N)`로 실행합니다. |
| Production | `mpirun $MPI_OPTIONS -np 12 gmx_mpi mdrun -ntomp T -gpu_id 0,…,N-1 -multidir work/000 … -deffnm production.NNN -hrex -replex 1000 -plumed plumed.dat`입니다. Replica마다 external-MPI rank 하나를 씁니다. 두 번째 segment부터 `-cpi production.(NNN-1).cpt -noappend`가 붙습니다. |
| 추가 option | `MPI_OPTIONS`는 launcher 바로 뒤에, `GROMACS_OPTIONS`는 모든 `mdrun` 끝에 공백으로 나누어 붙습니다. |
| Replica당 길이 | Minimization 최대 5,000 steps, equilibration 500,000 steps × 2 fs = 1 ns, production 50,000,000 steps × 2 fs = 100 ns(10 segments × 10 ns) |
| 전체 길이 | Equilibration 12 ns, production 1.2 μs(12 replica 합계) |
| Exchange | 1,000 steps(2 ps)마다 시도하며 segment당 약 5,000회입니다. |

`--gpus 1`로도 실행할 수 있지만 모든 replica가 GPU 하나를 공유하므로 느립니다.
Scheduler는 할당한 GPU만 `CUDA_VISIBLE_DEVICES`에 노출해야 하며 `-gpu_id`는 그
안의 logical device ID입니다. Pilot run에는 `production_steps`를 줄이거나
`--segments 1-1`을 사용합니다.

### REST3 topology와 build 검사

기본 OPC 설정에서는 `kappa_atom_names=['OW']`가 water oxygen type을 선택합니다.
`helpers/verify_rest3.py`는 O/H1/H2/EP의 type·charge·mass와 각 cation/anion 및
water의 solvent interaction이 replica 사이에서 보존되는지 검사합니다.
`water_model = "TIP3P"` compatibility option도 유지합니다.

Parser 0.2.2는 molecule 이름에 `system` 같은 section 단어가 들어 있으면 topology를
잘못 읽습니다. ParmEd는 여러 residue로 된 molecule을 `system1`, `system2`로
부르므로 `helpers/convert_topology.py`가 이 이름을 `Solute_1`, `Solute_2`로
바꿉니다. Parser는 dihedral type을 찾을 때 모든 hot molecule에 molecule 0의 atom
type을 쓰므로 `helpers/rest3_parser_adapter.py`가 molecule별 atom type을 쓰도록
고칩니다. Adapter는 parser의 molecule index를 `[ moleculetype ]` definition에
맞추며, 같은 이름이 `[ molecules ]`의 여러 row에 나타나도 row 순서와 개수를
유지하고 coordinate file을 재배열하지 않습니다.

두 peptide와 ion이 있는 작은 AmberTools system에서 두 molecule의
charge(`sqrt(λ)`), atom type과 dihedral force constant(`λ`) scaling, ion/water
보존을 확인했습니다. 여러 molecule system의 실제 `grompp`와 HREX run은
미검증입니다.

Build는 scale-one energy를 검사합니다. NaN/Inf energy, overflow한 차이 또는
음수·non-finite tolerance는 검증 실패이며 기존 비교 output을 교체하지 않습니다.
첫 `grompp` 전에는 ParmEd가 출력한 긴 CMAP 실수를 GROMACS 2024.x가 읽을 수 있는
정밀도로 정규화합니다.

Preprocessing TPR, processed topology와 energy-check raw file은
`work/.build_tmp.XXXXXX/`에 둡니다. 성공한 build에서도 남기려면
`./build.sh --keep-intermediates INPUT.pdb`를 사용합니다.

### 주요 output

- `work/states.tsv`: 최종 temperature, λ, κ와 seed
- `work/tempered_atoms.tsv`: tempered atom 목록(`system.parm7`의 1-based atom index, residue, atom name)
- `work/hot_molecules.tsv`: parser에 hot molecule로 전달한 molecule
- `work/topol.top`, `work/system.gro`: 공통 topology와 모든 replica가 직접 참조하는 coordinate file
- `work/NNN/` replica topology와 run-stage TPR, `*.grompp.log`, restart
- `work/build.log`, `work/build_summary.toml`, `work/energy_check.tsv`, `work/net_charge.tsv`
- `work/NNN/production.NNN.xtc`, `production.NNN.log`: segment별 trajectory와 exchange 기록이 들어 있는 GROMACS log

`build_summary.toml`은 `System has non-zero total charge` 문구의 값을
`total_charge_e`에 기록합니다. Log에 charge 값이 없으면
`total_charge_known=false`로 표시하고 값을 0으로 추정하지 않습니다. Log가
누락되면 summary 생성을 중단합니다.

`run.sh`는 segment마다 `Completed: rest3 production.NNN (work)`를, 마지막에
`Completed rest3 production: work`를 출력합니다. `--preparation-only`는
`Preparation output: work/<replica>/equilibrate.gro and equilibrate.cpt`로
끝납니다. 기본값에서 각 `production.NNN.xtc`는 10 ps 간격으로 segment당 약
1,000 frames입니다.

### Exchange 품질 해석

Template에는 analysis script가 없으므로 GROMACS log를 직접 확인합니다. 각
`work/NNN/production.NNN.log`에는 2 ps마다 `Repl ex` line이 기록됩니다. 이
line은 현재 replica 순서를 출력하고, 두 label 사이의 `x`가 그 state 경계의
accepted exchange입니다. Segment가 끝나면 log 끝의 `Repl average probabilities`에
neighbour pair별 평균 acceptance가 나옵니다.

- 0에 가까운 pair가 κ>1 구간에만 있으면 `maximum_kappa`나 onset 근처 state
  간격을 조정합니다. Predictor는 κ를 반영하지 않습니다.
- 모든 pair가 거의 0이면 PLUMED patch version을
  [준비 사항](../README.md#준비-사항)과 비교합니다.
- Segment별 값을 비교해 시간에 따라 acceptance가 크게 변하지 않는지 봅니다.

목표 acceptance와 round trip 기준은
[REMD tutorial family README](../../../1_Simulation/3_REMD/README.md#exchange-품질-해석)를
참고합니다. Walker의 round trip은 `Repl ex` line의 replica 순서를 따라가
계산합니다.

### Config 선택값

| Option | 허용값 | 기본값 | 적용 방식 |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Protein parameter를 선택합니다. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | LEaP water와 REST3 water atom type을 함께 결정합니다. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | 각각 `solvatebox`, `solvateoct`를 사용합니다. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Neutralization 뒤 추가할 bulk salt를 선택합니다. |
| `tempered_region` | `solute`, `mask` | `solute` | `solute`는 water와 ion을 제외한 모든 molecule(여러 protein chain, ligand 포함), `mask`는 `tempered_mask`가 덮는 molecule을 hot molecule로 parser에 전달합니다. 선택 결과는 `work/hot_molecules.tsv`에 기록합니다. 다른 값은 build 시작 전에 error로 중단합니다. |
| `tempered_mask` | AMBER mask 문자열 | `""` | `tempered_region = "mask"`일 때만 사용합니다(예: `":LIG"`). Molecule 전체를 덮어야 합니다. `solute`와 함께 값을 쓰면 error입니다. |
| `equilibration_ensemble` | `NPT`만 지원 | `NPT` | Replica equilibration에 적용합니다. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | GROMACS production pressure coupling을 설정합니다. |
| `constraint_mode` | `h-bonds`만 지원 | `h-bonds` | Hydrogen-containing bond에 LINCS를 적용합니다. |
| `random_seed` | `"random"` 또는 양의 정수 | `"random"` | State별 seed를 무작위로 만들거나 정수에서 파생합니다. |

| Mode option | Mode | 사용하는 설정 | 무시하는 설정과 결과 |
| --- | --- | --- | --- |
| `temperature_mode` | `auto` | `minimum_temperature`, `maximum_temperature`, `target_exchange_probability`, `generator_tolerance` | `temperatures`를 무시하고 tempered atom 수(`work/tempered_atoms.tsv`)로 ladder를 계산합니다. 1UBQ 기본값(300–450 K, p=0.20)은 11 state가 나와 p≈0.286, 12 state로 조정됩니다. |
| `temperature_mode` | `list` (기본값) | `temperatures` | Auto 설정을 무시하고 목록 temperature에서 `lambda_pp`와 `lambda_pw`를 계산합니다. |
| `rest3_kappa.mode` | `linear` (기본값) | `onset_temperature`, `maximum_temperature`, `maximum_kappa` | `values`를 무시하고 onset 이하 1.0, 이후 선형 κ를 계산합니다. |
| `rest3_kappa.mode` | `list` | `values` | Linear 설정을 무시하고 κ 목록을 순서대로 사용합니다. |

### 숫자 option

| Key | 기본값 | Unit | Stage | 효과 |
| --- | ---: | --- | --- | --- |
| `solute_box_distance` | 14.0 | Å | Build | `solvatebox`/`solvateoct`의 solute–box 경계 거리입니다. |
| `salt_concentration` | 150.0 | mM | Build | Neutralization 뒤 salt pair 수를 water 수 × (M/55.5)의 반올림으로 정합니다. |
| `temperature` | 300.0 | K | 모든 MD | 모든 replica의 `ref-t`와 `gen-temp`입니다. Temperature ladder의 첫 값과 같아야 합니다. |
| `pressure` | 1.0 | bar | Equilibration, NPT production | `ref-p`입니다. |
| `timestep` | 2.0 | fs | Equilibration, production | GROMACS `dt`(ps)로 변환합니다. |
| `minimization_steps` | 5000 | steps | Minimization | Steepest descent 최대 `nsteps`입니다. `emtol=1000` kJ/mol/nm는 고정입니다. |
| `equilibration_steps` | 500000 | steps | Equilibration | 기본 1 ns입니다. |
| `production_steps` | 50000000 | steps | Production | Replica당 전체 길이(기본 100 ns)입니다. `production_segments`로 나누어져야 합니다. |
| `production_segments` | 10 | segments | Production | Segment당 `production_steps / production_segments` steps(기본 10 ns)를 실행합니다. |
| `trajectory_interval_steps` | 5000 | steps | Equilibration, production | `nstxout-compressed`(기본 10 ps)입니다. |
| `energy_interval_steps` | 5000 | steps | 모든 MDP | `nstenergy`와 `nstlog`입니다. |
| `restart_interval_steps` | 5000 | steps | 없음 | 공통 config 검사용이며 GROMACS input에는 쓰지 않습니다. Stage와 segment 끝의 `.cpt`가 restart입니다. |
| `minimum_temperature`, `maximum_temperature` | 300.0, 450.0 | K | Build(`auto`) | `[replica_exchange]` predictor ladder의 양 끝입니다. |
| `target_exchange_probability` | 0.20 | 확률 | Build(`auto`) | Predictor의 목표 neighbour acceptance입니다(κ 미반영). 홀수 state가 나오면 올려서 짝수로 맞춥니다. |
| `generator_tolerance` | 0.0001 | 확률 | Build(`auto`) | 각 pair의 예측 확률을 목표값에 맞추는 허용 오차입니다. |
| `exchange_interval_steps` | 1000 | steps | Production | `mdrun -replex`(기본 2 ps)입니다. |
| `cpu_threads_per_replica` | 1 | threads | Run | `--cpus`를 생략했을 때 replica당 thread 수입니다. |
| `gpu_count` | 1 | GPUs | Run | `--gpus`를 생략했을 때 GPU 수입니다. |
| `rest3_kappa.onset_temperature` | 357.0 | K | Build(`linear`) | 이 effective temperature 이하에서는 κ=1.0입니다. |
| `rest3_kappa.maximum_temperature` | 450.0 | K | Build(`linear`) | κ가 `maximum_kappa`에 도달하는 temperature입니다. Onset보다 커야 하며 그 위에서는 `maximum_kappa`로 고정됩니다. |
| `rest3_kappa.maximum_kappa` | 1.020 | 무차원 | Build(`linear`) | κ 상한입니다. 1.0 이상이어야 합니다. |

### Tempered region 선택

`build.sh`는 LEaP 뒤 `helpers/tempered_selection.py`로 `system.parm7`에서 hot
atom을 한 번 고르고 `work/tempered_atoms.tsv`에 씁니다. `mask`는 ParmEd
`AmberMask`로 평가합니다. 선택이 비었거나 water·ion residue를 포함하면 build를
중단합니다. Auto temperature predictor는 이 table의 atom 수를 사용합니다.

Parser 0.2.2는 `[ moleculetype ]` 단위로 tempering합니다(`hot_molecules`).
`helpers/generate_rest3_topologies.py`는 선택된 atom이 속한 molecule을 hot
molecule로 정하고, molecule의 일부만 고른 mask는 해당 molecule과 atom 수를
알리고 중단합니다. GROMACS topology는 같은 molecule의 반복 copy를 definition
하나로 저장하므로 동일한 copy는 모두 고르거나 모두 제외해야 합니다. Molecule
일부만 tempering하려면 REST2 template를 사용합니다.

Parser는 hot molecule atom에만 `s` prefix type을 쓰고, κ²를 곱한 water oxygen과
cold molecule atom type 사이에는 원래 값의 `[ nonbond_params ]`를 추가합니다
(parser 0.2.2 `_generate_nonbonded_kappa_fix`). `helpers/scale_cmap.py`는 모든
CMAP을 λ로 scaling하므로
`helpers/convert_topology.py`가 cold molecule의 C-alpha CMAP type을 `XU<n>`으로
분리하고 이 map은 unscaled로 남깁니다. `helpers/verify_rest3.py`도 이 기준으로
CMAP을 검사합니다. 두 chain으로 나눈 1UBQ에서 chain A만 고른 mask build는 fake
`gmx`/`plumed` fixture로만 확인했으며, 실제 `grompp`와 HREX run은 미검증입니다.

### Replica 수와 schedule 목록

Replica 수는 2 이상의 짝수여야 합니다. Auto mode에서 predictor가 홀수 N개
state를 내면 온도 범위와 predictor 계산식은 그대로 두고 target exchange
probability를 올려 N+1개로 맞춥니다. N+1개가 되는 값 중 가장 큰 값을 쓰므로
모든 인접 pair의 예상 교환 확률이 거의 같아집니다. 실제로 쓴 값은 build 출력과
`work/system_counts.tsv`의 `used_target_exchange_probability`에 남습니다.
`build.sh --dry-run`은 auto predictor를 실행하지 않으므로 auto replica 수는 실제
build에서 정해집니다.

기본 `[replica_exchange] temperatures`는 `T_i = 300 × 1.5^(i/11)`(i = 0–11)인
12개 값(K)입니다. 다른 범위나 replica 수를 쓰려면 이 배열을 수정합니다. κ를
직접 정하려면 `[rest3_kappa]`에 `mode = "list"`와 `values`를 씁니다.
`config.toml`의 주석 예시는 기본 temperature에 대한 linear κ를 반올림한
값입니다.

```toml
[replica_exchange]
temperature_mode = "list"
temperatures = [
    300.000000, 311.264471, 322.951902, 335.078177,
    347.659771, 360.713782, 374.257948, 388.310674,
    402.891055, 418.018903, 433.714775, 450.000000,
]

[rest3_kappa]
mode = "list"
values = [
    1.000, 1.000, 1.000, 1.000, 1.000, 1.001,
    1.004, 1.007, 1.010, 1.013, 1.016, 1.020,
]
```

Temperature는 둘 이상의 finite 양수이고 중복 없이 오름차순이며 첫 값은
`run.temperature`와 같아야 합니다. κ 개수는 temperature state 수와 같아야 하고
모든 κ는 1.0 이상이어야 합니다. 두 목록은 LEaP 실행 전에 검사하며 홀수 개
temperature 목록은 자동으로 바꾸지 않고 거부합니다. `temperature_mode = "auto"`와
κ `list`를 함께 쓰면 κ 개수는 predictor가 state 수를 정한 뒤 검사합니다. `nan`,
`inf`, `-inf`는 config를 읽을 때 key 위치와 함께 거부합니다.
`run.sh --dry-run`도 `work/states.tsv`의 count를 검사합니다.

### Scaled replica의 net charge

REST는 hot molecule atom의 charge만 `sqrt(λ)`로 줄이고 water와 ion은 cold로
둡니다. Ion은 NaCl, KCl, MgCl2, CaCl2의 실제 residue 이름으로 분류합니다.
따라서 charged solute의 scaled replica에는 `Q_ref + q_hot(sqrt(λ) − 1)`의 net
charge가 생깁니다. `Q_ref`는 unscaled topology의 total charge(변환 roundoff
수준)이고 `q_hot`은 `work/hot_molecules.tsv`에 기록된 모든 hot molecule atom의
원래 charge 합입니다. PME에서 GROMACS는 균일한 neutralizing background를 더하고
Ewald net-charge warning 하나를 출력합니다. Solute만 tempering하는 방식은
[PLUMED HREX tutorial](https://www.plumed.org/doc-v2.9/user-doc/html/hrex.html)과
[REST3 parser 예제](https://github.com/koreyr/repex_topology_parser)를 따릅니다.
Background charge artifact가 큰 system(예: membrane)에서는 이 선택을 따로
검토합니다.

`maxwarn`은 public config option이 아닙니다. `build.sh`는 replica별 예상 charge를
`work/net_charge.tsv`에 기록합니다. `run.sh`의 `grompp`는 먼저 warning 우회 없이
실행합니다. 실패하면 warning이 net-charge warning 하나뿐이고 log의
`System has non-zero total charge` 값이 예상값 ±0.01 e일 때만 `-maxwarn 1`로
다시 실행합니다. Build의 preprocessing과 energy check, replica 000은 λ=1이므로
`work/topol.top`의 `Q_ref` 주변 roundoff만 허용합니다. 다른 warning이나 예상과
다른 charge는 replica, 보고된 charge, 예상 charge와 `*.grompp.log` 경로를 남기고
계산을 중단합니다. 이 gate는 실제 GROMACS로 실행하지 않았습니다(미검증).

### Production checkpoint continuation

최초 minimization은 공통 `work/system.gro`를, 이후 stage는 replica별 `.gro`와
필요한 `.cpt`를 사용합니다. 첫 production segment는 equilibration의
coordinate/velocity를 `grompp -t`로 읽고 새 production 계산을 시작합니다. 두
번째부터는 predecessor checkpoint를 `mdrun -cpi`에도 전달해 thermostat/barostat와
전체 MD state를 이어받습니다. Runner는 predecessor의 step/time/part를 검사하고,
원본 `production.mdp`에서 누적 `init-step`을 가진 `production.NNN.mdp`를
생성합니다. 기존 파생 input은 내용이 같을 때만 재사용합니다.

각 후속 segment는 `-noappend`로 독립 output을 생성합니다. Engine의
`production.NNN.partMMMM.*`는 모든 요청 step이 완료된 checkpoint를 확인한 뒤
`production.NNN.*`로 옮깁니다. `.cpt` 이름은 바꾸지 않으므로 checkpoint에 기록된
원래 part output의 이름과 checksum이 유지됩니다. Trajectory는 이 canonical
`.xtc` 경로에서 읽습니다.

Exit 0이어도 checkpoint가 요청한 마지막 step/time에 도달하지 않았으면 완료로
보지 않습니다. 이전 runner의 후속 segment가 time을 다시 시작했거나 checkpoint
part가 맞지 않으면 새 `WORK_DIR`에서 시작합니다.

실제 GROMACS 2024.3의 단일 replica CPU 계산에서 segment helper의 누적 step/time,
part output 이름과 기존 파일 보존을 확인했습니다. 공개 runner의 MPI HREX/GPU
continuation은 미검증입니다. Runner가 GPU ID를 전달하므로 CPU-only 환경에서는
실행되지 않습니다.

### Engine option 직접 지정

Config key가 없는 GROMACS mdp option은 `[gromacs.<stage>]` table로 지정합니다. Stage 우선순위, 값 형식과 거부되는 option은 [3_Templates README](../../README.md#engine-option-직접-지정)를 따릅니다.

```toml
[gromacs.production]
nstcalcenergy = 200
```

| Stage | Input |
| --- | --- |
| `minimization` | `minimize.mdp` |
| `equilibration` | `equilibrate.mdp` |
| `production` | `production.mdp` |

REST는 모든 stage를 GROMACS로 실행하므로 `[gromacs]`만 씁니다. Heating stage가 없으므로 `[gromacs.heating]`은 적용되지 않습니다. Scale-one 검사용 `helpers/energy_check.mdp`는 바꾸지 않습니다. 모든 replica에 같은 값을 씁니다. 예시의 `nstcalcenergy`(GROMACS 기본값 100)는 `nstenergy`(`energy_interval_steps`, 5000)가 그 배수가 되도록 정합니다(GROMACS 2026.3 manual).

### 문제 해결

| Message 또는 증상 | 원인 | 조치 |
| --- | --- | --- |
| `repex-topology-parser 0.2.2 module not found. Run ./download.sh before ./build.sh.` | Parser source가 없습니다. | `./download.sh PDB_ID`를 다시 실행합니다. |
| `Build did not complete: work/build.done is missing; see work/build.log.` | Build가 중간에 실패했습니다(`REST3 topology-preservation check failed`, partial-molecule mask 등). | `work/build.log`와 남은 `work/.build_tmp.XXXXXX/`를 확인하고 work를 옮긴 뒤 다시 build합니다. |
| `Config validation failed: ...` | `production_steps`가 `production_segments`로 나누어지지 않는 등 config 값이 잘못되었습니다. | 바로 위에 출력된 Python error의 key를 고칩니다. |
| `--cpus must be divisible by the replica count (N).`, `--gpus cannot exceed the replica count (N).` | Resource 값이 replica 수와 맞지 않습니다. | `work/states.tsv`의 row 수에 맞춰 지정합니다. |
| `The GROMACS MPI build does not recognize -hrex`, `The GROMACS build is not patched with PLUMED`, `... needs PLUMED 2.10.2 or later` | `gmx_mpi`가 PLUMED 2.10.2 이상의 GROMACS 2024 patch build가 아닙니다. | [준비 사항](../README.md#준비-사항)대로 다시 build하거나 `GROMACS_MPI`로 올바른 executable을 지정합니다. |
| `Previous production segment is incomplete: ...` | `--segments`가 끝나지 않은 앞 segment를 건너뛰었습니다. | 앞 segment부터 실행합니다. 실패한 segment의 partial output 정리는 [GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 따릅니다. |

## English

This template builds GROMACS/PLUMED REST3 HREX from a user-prepared protein
PDB. REST3 adds a κ schedule that adjusts protein–water vdW to REST2 scaling.
The default keeps κ at 1.0 through 357 K and linearly reaches 1.020 at 450 K.
This is not a universal value; assess compactness and exchange in a pilot run
for each IDP and force-field/water combination. The temperature predictor does
not model the κ correction.

The default `temperature_mode = "list"` uses the 12 geometric effective
temperatures (300–450 K) in `temperatures` in `config.toml`, so the build creates
12 replicas for any system. For 1UBQ (1231 tempered-solute atoms) the offline
predictor estimates neighbor exchange probabilities of about 0.27–0.30 without
the κ effect. For larger solutes, check the exchange statistics of the first
production segment and add replicas when needed.

### File roles

| File | Role |
| --- | --- |
| `download.sh` | Downloads the source PDB by RCSB PDB ID together with the verified `repex-topology-parser` 0.2.2 source. |
| `build.sh` | Builds the solvated system, REST3 state table, parser-based replica topologies and MDP inputs, and checks them. |
| `run.sh` | Runs per-replica pre-production and PLUMED `-hrex` production segments. |
| `config.toml` | Force field, box, salt, stage lengths, temperature/κ schedule and resource settings. |
| `helpers/` | Leaf-local internal code called automatically by `build.sh` or `run.sh`; not an entry point. It also holds the scale-one energy-check inputs (`energy_check.mdp`, `energy_selection.txt`), which are not user settings. |

This directory's runtime code can be copied on its own. Install the Python
dependencies from the local `requirements.txt` after copying it.

### Run

Prerequisites: the PLUMED-patched GROMACS 2024.3 (`gmx`, `gmx_mpi`) and MPI
launcher described in the [family README prerequisites](../README.md#prerequisites),
AMBER `tleap`, the PLUMED CLI `plumed` (build), numpy and ParmEd from
`requirements.txt` (plus tomli on Python 3.10 or older), and the parser source
fetched by `download.sh`. `build.sh` reads `TLEAP` and `PLUMED` as executable
overrides.

```bash
./download.sh 1UBQ
./build.sh structure/1UBQ.pdb
replicas=$(awk 'NR > 1 {count++} END {print count + 0}' work/states.tsv)
./run.sh --cpus "$replicas" --gpus 1
```

Replica preproduction uses the same minimization-to-NPT-equilibration sequence
as the tutorial, without a separate heating stage.
`minimization_steepest_steps` and `heating_initial_temperature` remain in
`config.toml` because the shared config checker requires them; REST GROMACS
inputs do not use them.

`GROMACS` and `GROMACS_MPI` override `run.equilibration_engine` and
`run.production_engine` in `work/resolved_config.toml`. Executable names must
be `gmx` and `gmx_mpi`; installation paths are accepted. GROMACS commands during
build use the same selection and override from the source config. Empty
overrides, missing engine settings and unsupported executables fail instead of
falling back to a default.

See [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery) for run state, reruns after failure and
concurrent-run protection.

### Resources and length

| Item | Default and rule |
| --- | --- |
| Replicas | 12 (`[replica_exchange] temperatures`); with `temperature_mode = "auto"` the build sets the count. |
| `--cpus N` | Defaults to replicas × `cpu_threads_per_replica` (1). Must divide by the replica count; each replica gets `N/replicas` threads (`-ntomp`). |
| `--gpus N` | Defaults to `gpu_count` (1); range 1 to the replica count. Minimization and equilibration run up to N replicas at once with `gmx mdrun -ntmpi 1 -gpu_id (replica index mod N)`. |
| Production | `mpirun $MPI_OPTIONS -np 12 gmx_mpi mdrun -ntomp T -gpu_id 0,…,N-1 -multidir work/000 … -deffnm production.NNN -hrex -replex 1000 -plumed plumed.dat`, one external-MPI rank per replica. From the second segment `-cpi production.(NNN-1).cpt -noappend` is added. |
| Extra options | `MPI_OPTIONS` is split on whitespace and placed right after the launcher; `GROMACS_OPTIONS` is appended to every `mdrun`. |
| Length per replica | Minimization up to 5,000 steps, equilibration 500,000 steps × 2 fs = 1 ns, production 50,000,000 steps × 2 fs = 100 ns (10 segments × 10 ns) |
| Total length | 12 ns equilibration and 1.2 μs production over 12 replicas |
| Exchange | Attempted every 1,000 steps (2 ps), about 5,000 attempts per segment. |

`--gpus 1` works, but every replica then shares one GPU and runs slowly. The
scheduler must expose only the allocated devices through
`CUDA_VISIBLE_DEVICES`; `-gpu_id` values are logical IDs within that set. For a
pilot run, reduce `production_steps` or use `--segments 1-1`.

### REST3 topology and build checks

With the default OPC model, `kappa_atom_names=['OW']` selects the water oxygen
type. `helpers/verify_rest3.py` checks that O/H1/H2/EP atom types, charges and
masses and the solvent interactions of water and every cation/anion are
preserved across replicas. The optional `water_model = "TIP3P"` compatibility
path remains available.

Parser 0.2.2 misreads a topology when a molecule name contains a section word
such as `system`. ParmEd names multi-residue molecules `system1`, `system2`, so
`helpers/convert_topology.py` renames them `Solute_1`, `Solute_2`. The parser
also looks up dihedral types with molecule 0's atom types for every hot
molecule; `helpers/rest3_parser_adapter.py` makes it use each molecule's own
types. The adapter maps parser molecule indices to `[ moleculetype ]`
definitions; repeated names in `[ molecules ]` keep their row order and counts,
and the coordinate file is not reordered.

A small AmberTools system with two peptides and ions confirmed charge
(`sqrt(lambda)`), atom-type and dihedral force-constant (`lambda`) scaling for
both molecules and unchanged ions and water. Real `grompp` and HREX runs of a
multi-molecule system are unverified.

The build checks the scale-one energy. Nonfinite energy, an overflowed
difference, or a negative or nonfinite tolerance fails validation without
replacing existing comparison output. Before the first `grompp`, the build
normalizes long ParmEd-formatted CMAP numbers to a precision accepted by
GROMACS 2024.x.

Preprocessing TPRs, processed topologies and raw energy-check files stay in
`work/.build_tmp.XXXXXX/`. Use `./build.sh --keep-intermediates INPUT.pdb` to
keep them after a successful build.

### Main outputs

- `work/states.tsv`: final temperatures, λ values, κ values and seeds
- `work/tempered_atoms.tsv`: tempered atoms (1-based `system.parm7` atom index, residue and atom name)
- `work/hot_molecules.tsv`: molecules passed to the parser as hot
- `work/topol.top`, `work/system.gro`: shared topology and the coordinate file referenced directly by every replica
- `work/NNN/` replica topologies and run-stage TPRs, `*.grompp.log` files and restarts
- `work/build.log`, `work/build_summary.toml`, `work/energy_check.tsv`, `work/net_charge.tsv`
- `work/NNN/production.NNN.xtc`, `production.NNN.log`: per-segment trajectory and the GROMACS log that holds the exchange records

`build_summary.toml` records the value reported by `System has non-zero total
charge` as `total_charge_e`. If the log contains no charge value, it records
`total_charge_known=false` and omits the numeric value. Missing logs stop
summary generation.

`run.sh` prints `Completed: rest3 production.NNN (work)` after each segment and
`Completed rest3 production: work` at the end. `--preparation-only` ends with
`Preparation output: work/<replica>/equilibrate.gro and equilibrate.cpt`. With
the defaults each `production.NNN.xtc` holds about 1,000 frames at 10 ps
intervals.

### Reading exchange quality

The template has no analysis script, so read the GROMACS logs directly. Each
`work/NNN/production.NNN.log` records a `Repl ex` line every 2 ps. The line
prints the current replica order, and an `x` between two labels marks an
accepted exchange across that state boundary. At the end of a segment the log
reports `Repl average probabilities` per neighbour pair.

- If near-zero pairs appear only where κ>1, adjust `maximum_kappa` or the state
  spacing around the onset. The predictor does not include κ.
- If every pair is near zero, compare the PLUMED patch version with the
  [prerequisites](../README.md#prerequisites).
- Compare segments to check that acceptance does not drift strongly over time.

See the [REMD tutorial family README](../../../1_Simulation/3_REMD/README.md#reading-exchange-quality)
for target acceptance and round-trip guidance. Walker round trips follow the
replica order printed in the `Repl ex` lines.

### Config choices

| Option | Allowed values | Default | Effect |
| --- | --- | --- | --- |
| `protein_force_field` | `ff99SB-ILDN`, `ff14SB`, `ff19SB` | `ff19SB` | Selects the protein parameters. |
| `water_model` | `TIP3P` (`ff99SB-ILDN`, `ff14SB`), `OPC` (`ff19SB`) | `OPC` | Selects both LEaP water and REST3 water atom types. |
| `box_shape` | `rectangular`, `octahedral` | `rectangular` | Uses `solvatebox` or `solvateoct`, respectively. |
| `salt_type` | `NaCl`, `KCl`, `MgCl2`, `CaCl2` | `NaCl` | Selects bulk salt added after neutralization. |
| `tempered_region` | `solute`, `mask` | `solute` | `solute` passes every non-water, non-ion molecule (including multiple protein chains and ligands) to the parser as a hot molecule; `mask` passes the molecules covered by `tempered_mask`. The selection is recorded in `work/hot_molecules.tsv`. Other values stop the build before it starts. |
| `tempered_mask` | AMBER mask string | `""` | Used only with `tempered_region = "mask"` (for example `":LIG"`). It must cover whole molecules. A value together with `solute` is an error. |
| `equilibration_ensemble` | `NPT` only | `NPT` | Applies to replica equilibration. |
| `production_ensemble` | `NVT`, `NPT` | `NPT` | Selects GROMACS production pressure coupling. |
| `constraint_mode` | `h-bonds` only | `h-bonds` | Applies LINCS to bonds involving hydrogen. |
| `random_seed` | `"random"` or a positive integer | `"random"` | Creates random state seeds or derives them from the integer. |

| Mode option | Mode | Settings used | Ignored settings and result |
| --- | --- | --- | --- |
| `temperature_mode` | `auto` | `minimum_temperature`, `maximum_temperature`, `target_exchange_probability`, `generator_tolerance` | Ignores `temperatures` and predicts a ladder from the tempered atom count (`work/tempered_atoms.tsv`). For 1UBQ the defaults (300–450 K, p=0.20) give 11 states, adjusted to 12 at p≈0.286. |
| `temperature_mode` | `list` (default) | `temperatures` | Ignores auto settings and computes `lambda_pp` and `lambda_pw` from the listed temperatures. |
| `rest3_kappa.mode` | `linear` (default) | `onset_temperature`, `maximum_temperature`, `maximum_kappa` | Ignores `values`; κ is 1.0 through onset and then increases linearly. |
| `rest3_kappa.mode` | `list` | `values` | Ignores linear settings and uses the κ list in order. |

### Numeric options

| Key | Default | Unit | Stage | Effect |
| --- | ---: | --- | --- | --- |
| `solute_box_distance` | 14.0 | Å | Build | Solute-to-box-edge distance for `solvatebox`/`solvateoct`. |
| `salt_concentration` | 150.0 | mM | Build | Salt pairs after neutralization = water count × (M/55.5), rounded. |
| `temperature` | 300.0 | K | All MD | `ref-t` and `gen-temp` of every replica; must equal the first ladder temperature. |
| `pressure` | 1.0 | bar | Equilibration, NPT production | `ref-p`. |
| `timestep` | 2.0 | fs | Equilibration, production | Converted to GROMACS `dt` in ps. |
| `minimization_steps` | 5000 | steps | Minimization | Maximum steepest-descent `nsteps`; `emtol=1000` kJ/mol/nm is fixed. |
| `equilibration_steps` | 500000 | steps | Equilibration | 1 ns by default. |
| `production_steps` | 50000000 | steps | Production | Total length per replica (100 ns by default); must divide by `production_segments`. |
| `production_segments` | 10 | segments | Production | Each segment runs `production_steps / production_segments` steps (10 ns by default). |
| `trajectory_interval_steps` | 5000 | steps | Equilibration, production | `nstxout-compressed` (10 ps by default). |
| `energy_interval_steps` | 5000 | steps | All MDP files | `nstenergy` and `nstlog`. |
| `restart_interval_steps` | 5000 | steps | None | Required by the shared config checker but not written to GROMACS inputs; the `.cpt` at the end of each stage and segment is the restart. |
| `minimum_temperature`, `maximum_temperature` | 300.0, 450.0 | K | Build (`auto`) | Ends of the `[replica_exchange]` predicted ladder. |
| `target_exchange_probability` | 0.20 | probability | Build (`auto`) | Predictor target for neighbour acceptance (κ not included); raised when needed to make the state count even. |
| `generator_tolerance` | 0.0001 | probability | Build (`auto`) | Tolerance for matching each pair's predicted probability to the target. |
| `exchange_interval_steps` | 1000 | steps | Production | `mdrun -replex` (2 ps by default). |
| `cpu_threads_per_replica` | 1 | threads | Run | Threads per replica when `--cpus` is omitted. |
| `gpu_count` | 1 | GPUs | Run | GPU count when `--gpus` is omitted. |
| `rest3_kappa.onset_temperature` | 357.0 | K | Build (`linear`) | κ=1.0 at and below this effective temperature. |
| `rest3_kappa.maximum_temperature` | 450.0 | K | Build (`linear`) | Temperature at which κ reaches `maximum_kappa`; must exceed the onset, and κ stays at `maximum_kappa` above it. |
| `rest3_kappa.maximum_kappa` | 1.020 | dimensionless | Build (`linear`) | Upper κ value; must be at least 1.0. |

### Tempered region selection

After LEaP, `build.sh` runs `helpers/tempered_selection.py` once on
`system.parm7` and writes the hot atoms to `work/tempered_atoms.tsv`. A `mask`
is evaluated with ParmEd `AmberMask`. An empty selection or one that contains
water or ion residues stops the build. The auto temperature predictor uses the
atom count of this table.

Parser 0.2.2 tempers whole `[ moleculetype ]` definitions (`hot_molecules`).
`helpers/generate_rest3_topologies.py` makes every molecule that contains
selected atoms hot and stops with the molecule name and atom counts when a mask
covers only part of a molecule. The GROMACS topology stores repeated copies of a
molecule as one definition, so identical copies must all be selected or all be
excluded. Use the REST2 template to temper part of a molecule.

The parser writes `s`-prefixed types only for hot-molecule atoms and adds
`[ nonbond_params ]` with the original values between the κ²-scaled water
oxygen and cold-molecule atom types (parser 0.2.2
`_generate_nonbonded_kappa_fix`). `helpers/scale_cmap.py` scales every CMAP by
lambda, so
`helpers/convert_topology.py` gives the C-alpha CMAP types of cold molecules
separate `XU<n>` names whose maps stay unscaled; `helpers/verify_rest3.py`
checks CMAPs on the same basis. A mask build that selects chain A of 1UBQ split
into two chains was checked only with fake `gmx`/`plumed` fixtures; real
`grompp` and HREX runs are unverified.

### Replica count and schedule lists

The replica count must be even and at least two. When the auto predictor returns
an odd count N, the temperature range and predictor algorithm are kept and the
target exchange probability is raised to give N+1 states. The largest target
that still gives N+1 is used, so every neighbor pair has nearly the same
predicted probability. The value used is printed by the build and stored as
`used_target_exchange_probability` in `work/system_counts.tsv`.
`build.sh --dry-run` does not run the auto predictor, so the auto replica count
is set by the actual build.

The default `[replica_exchange] temperatures` holds the 12 values (K) of
`T_i = 300 × 1.5^(i/11)` for i = 0–11; edit the array to change the range or
replica count. To set κ directly, use `mode = "list"` and `values` under
`[rest3_kappa]`. The commented example in `config.toml` is the linear κ for the
default temperatures, rounded.

```toml
[replica_exchange]
temperature_mode = "list"
temperatures = [
    300.000000, 311.264471, 322.951902, 335.078177,
    347.659771, 360.713782, 374.257948, 388.310674,
    402.891055, 418.018903, 433.714775, 450.000000,
]

[rest3_kappa]
mode = "list"
values = [
    1.000, 1.000, 1.000, 1.000, 1.000, 1.001,
    1.004, 1.007, 1.010, 1.013, 1.016, 1.020,
]
```

Temperatures must be at least two unique, increasing, finite positive values,
with the first equal to `run.temperature`. The κ count must equal the
temperature-state count, and every κ must be at least 1.0. Both lists are
checked before LEaP, and an odd-length temperature list is rejected, not
adjusted. With `temperature_mode = "auto"` and a κ `list`, the κ count is
checked after the predictor sets the state count. `nan`, `inf` and `-inf` are
rejected with the key location when the config is read. `run.sh --dry-run` also
checks the `work/states.tsv` count.

### Net charge of scaled replicas

REST scales only hot-molecule charges by `sqrt(lambda)`; water and ions stay
cold. Ions are classified by the actual NaCl, KCl, MgCl2 and CaCl2 residue
names. A scaled replica of a charged solute therefore carries a net charge of
`Q_ref + q_hot(sqrt(lambda) - 1)`, where `Q_ref` is the total charge of the
unscaled topology (conversion roundoff) and `q_hot` is the unscaled charge of
all hot-molecule atoms listed in `work/hot_molecules.tsv`. With PME, GROMACS
adds a uniform neutralizing background and prints one Ewald net-charge warning.
Tempering only the solute follows the
[PLUMED HREX tutorial](https://www.plumed.org/doc-v2.9/user-doc/html/hrex.html)
and the [REST3 parser examples](https://github.com/koreyr/repex_topology_parser).
Review this choice for systems where background-charge artifacts are large,
such as membranes.

`maxwarn` is not a public configuration option. `build.sh` writes each
replica's expected charge to `work/net_charge.tsv`. `run.sh` first runs
`grompp` without a warning override. It retries with `-maxwarn 1` only when the
single warning is the net-charge warning and the reported `System has non-zero
total charge` is within 0.01 e of the expected value. The build preprocessing,
energy check and replica 000 use lambda=1, so they accept only roundoff around
`Q_ref` from `work/topol.top`. Any other warning or charge stops the workflow
and reports the replica, reported charge, expected charge and `*.grompp.log`
path. This gate has not been run with real GROMACS (unverified).

### Production checkpoint continuation

Initial minimization reads the shared `work/system.gro`; later stages read each
replica's `.gro` and, where required, `.cpt`. The first production segment reads
equilibration coordinates and velocities with `grompp -t` and starts a new
production stage. From the second segment onward, `mdrun -cpi` also restores the
predecessor checkpoint's full MD state, including thermostat/barostat state. The
runner checks predecessor step/time/part and derives `production.NNN.mdp` with
cumulative `init-step` from the original `production.mdp`. An existing derived
input is reused only when its content matches.

Each continuation uses `-noappend` for separate outputs. After checking that the
checkpoint reached the requested final step/time, the runner moves
`production.NNN.partMMMM.*` to the canonical `production.NNN.*` names. The `.cpt`
name is unchanged, so checkpoint-recorded part output names and checksums remain
intact. Read trajectories from the canonical `.xtc` paths.

Exit 0 alone does not count as completion when the checkpoint ends early. Use a
new `WORK_DIR` if an older runner's continuation reset time or has an
incompatible checkpoint part.

The segment helper was checked with actual single-replica GROMACS 2024.3 CPU runs
for cumulative step/time, part output names and preservation of existing files.
Public-runner MPI HREX/GPU continuation remains unverified. The runner passes GPU
IDs and cannot run in a CPU-only environment.

### Engine option passthrough

GROMACS mdp options without a config key go into `[gromacs.<stage>]` tables. Stage precedence, value formats and refused options are described in the [3_Templates README](../../README.md#engine-option-passthrough).

```toml
[gromacs.production]
nstcalcenergy = 200
```

| Stage | Input |
| --- | --- |
| `minimization` | `minimize.mdp` |
| `equilibration` | `equilibrate.mdp` |
| `production` | `production.mdp` |

REST runs every stage with GROMACS, so only `[gromacs]` applies. There is no heating stage, so `[gromacs.heating]` has no effect. The scale-one check input `helpers/energy_check.mdp` is left unchanged. Every replica gets the same values. Choose `nstcalcenergy` (GROMACS default 100) so that `nstenergy` (`energy_interval_steps`, 5000) is a multiple of it (GROMACS 2026.3 manual).

### Troubleshooting

| Message or symptom | Cause | Action |
| --- | --- | --- |
| `repex-topology-parser 0.2.2 module not found. Run ./download.sh before ./build.sh.` | The parser source is missing. | Rerun `./download.sh PDB_ID`. |
| `Build did not complete: work/build.done is missing; see work/build.log.` | The build failed partway (`REST3 topology-preservation check failed`, a partial-molecule mask, and so on). | Read `work/build.log` and the retained `work/.build_tmp.XXXXXX/`, move work aside and rebuild. |
| `Config validation failed: ...` | A config value is invalid, for example `production_steps` not divisible by `production_segments`. | Fix the key named in the Python error printed just above. |
| `--cpus must be divisible by the replica count (N).`, `--gpus cannot exceed the replica count (N).` | Resource values do not match the replica count. | Match them to the row count of `work/states.tsv`. |
| `The GROMACS MPI build does not recognize -hrex`, `The GROMACS build is not patched with PLUMED`, `... needs PLUMED 2.10.2 or later` | `gmx_mpi` is not a GROMACS 2024 build patched with PLUMED 2.10.2 or later. | Rebuild as in the [prerequisites](../README.md#prerequisites) or point `GROMACS_MPI` to the right executable. |
| `Previous production segment is incomplete: ...` | `--segments` skipped an unfinished earlier segment. | Run from the earlier segment. Clean up a failed segment's partial output as in the [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery). |
