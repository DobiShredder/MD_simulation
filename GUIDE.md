# MD simulation tutorials: integrated guide

한국어 · [English](#english)

저장소의 학습 순서와 method 선택 기준을 정리한 문서입니다.
실행 command와 input 설명은 각 폴더의 `README.md`에 있습니다.

모든 input은 학습용 template입니다. Production 길이는 method마다 다르며 각 README에 적혀 있습니다.
이 튜토리얼에서 제공하는 기본 값들은 수렴을 판정하기 위한 simulation 조건이 아닙니다.

## 목차

0. [학습 전 준비](#0-학습-전-준비)
1. [시뮬레이션](#1-시뮬레이션)
   - [conventional MD](#11-conventional-md)
   - [Umbrella sampling](#12-umbrella-sampling)
   - [Replica exchange](#13-replica-exchange)
   - [Gaussian accelerated MD](#14-gaussian-accelerated-md)
   - [Free-energy perturbation](#15-free-energy-perturbation)
   - [Weighted ensemble](#16-weighted-ensemble)
   - [Metadynamics와 OPES](#17-metadynamics와-opes)
2. [Trajectory 분석](#2-trajectory-분석)
3. [참고 자료](#3-참고-자료)
4. [부록: 실행 상태와 복구](#4-부록-실행-상태와-복구)

## 0. 학습 전 준비

### 필요한 배경

아래 내용은 학습자가 이 튜토리얼을 진행하기 전에 습득할 필요가 있는 지식들입니다.
이 튜토리얼에서는 아래 내용들을 다루지 않습니다.

- programming에 대한 기초 수준의 이해
- Linux shell과 파일·디렉터리의 기본 사용법
- Python과 package 설치 및 가상 환경 관리 방법
- force field 등 MD simulation을 구성하는 기본적인 물리학에 대한 이해
- 단백질 구조에 대한 이해
- AMBER, GROMACS, PLUMED 의 기본 실행 방법
- RMSD, clustering, dimension reduction 등 분석 방법의 목적



### 먼저 질문을 정의하기

분자동력학 계산을 수행하기 전에 아래 내용을 충분히 고민하고 결정해야 합니다.

1. 관찰하려는 구조 변화나 thermodynamic/kinetic 지표는 무엇인가?
2. 일반적인 MD simulation 수준의 time scale에서 관찰 가능한가?
3. 적절한 reaction coordinate 또는 collective variable을 정의할 수 있는가?
4. equilibrium ensemble이 필요한가, transition pathway와 rate가 필요한가?
5. force field, protonation, 막 조성, ligand 상태가 질문과 일치하는가?
6. 수렴과 불확실성을 어떤 독립적인 지표로 판단할 것인가?

질문과 관측하려는 지표가 달라지면 simulation·analysis method도 달라집니다.



### 저장소의 두 부분

```text
structure and scientific choices
              ↓
1_Simulation: system build → minimization → equilibration → trajectory
              ↓
2_Analysis: preprocessing → features → statistics → interpretation
```

- [시뮬레이션 튜토리얼](1_Simulation/README.md)
- [분석 튜토리얼](2_Analysis/README.md)
- [사용자 structure용 config template](3_Templates/README.md)
- [실행 상태와 실패 후 재실행 규칙](#4-부록-실행-상태와-복구)

`1_Simulation/`에서 method와 engine input을 익힌 뒤 같은 계산을 자신의 structure에
적용할 때 `3_Templates/`를 사용합니다. Template는 build-ready PDB와
`config.toml`을 받으며 system별 protonation, missing atom과 selection은 자동으로
결정하지 않습니다.



## 1. 시뮬레이션

| 번호 | 방법 | 주된 목적 | 주요 사전 조건 |
| --- | --- | --- | --- |
| 1 | 일반 MD | 시간에 따른 dynamics | 관심있는 pathway가 conventional MD로 접근 가능한 시간 scale에 존재 |
| 2 | US | 선택한 좌표를 따르는 PMF | 적절한 reaction coordinate와 window overlap |
| 3 | REMD 계열 | replica exchange를 통한 sampling 향상 | 교환 변수와 replica 분포 설계 |
| 4 | GaMD 계열 | reaction-coordinate-free barrier 완화 | boost 통계와 reweighting 검증 |
| 5 | FEP | 두 alchemical state의 free energy 차이 | 안정적인 mapping과 lambda overlap |
| 6 | WE | 희귀 사건의 pathway, flux와 rate | progress coordinate와 상태 정의 |
| 7 | MetaD/OPES | CV 공간의 barrier 완화와 자유에너지 탐색 | 물리적으로 유효한 CV와 bias 설정 |



### 공통 계산 흐름

공통 workflow는 아래 순서를 따릅니다.

1. 원본 구조와 출처 기록
2. residue, ligand, ion, protonation 및 missing atoms 검토
3. force field와 solvent model 선택
4. topology와 초기 좌표 생성
5. 단계별 minimization과 equilibration
6. 초기 실행과 continuation/restart 구분
7. 짧은 교육용 production
8. 출력·restart·trajectory의 일관성 확인



### 1.1 conventional MD

일반 MD는 별도의 bias 없이 선택한 Hamiltonian과 ensemble에서 시간에 따른 구조 변화를 계산합니다.
Enhanced-sampling 결과를 비교하기 위한 기준 trajectory이며 대부분의 후속 분석을 배우는 출발점입니다.

세 시스템이 서로 다른 학습 목표를 담당합니다.

| 시스템 | 시작 구조 | 학습 목표 | 기본 AMBER model |
| --- | --- | --- | --- |
| Chignolin | PDB 1UAO | protein의 build와 기본 구조·ensemble 분석 | ff19SB + OPC |
| T4 lysozyme–JZ4 | PDB 3HTB | ligand parameterization, interaction, ABFE와 end-state energy | ff19SB + GAFF2 + OPC |
| KcsA | PDB 1K4C | 막 단백질 좌표·topology build와 membrane analysis | ff19SB + Lipid21 + OPC |

ff19SB 기반 tutorial은 Amber 26 manual의 권장 조합인 OPC를 사용합니다.
OPC는 O, H1, H2와 massless extra point(EP)로 구성된 4-site water model이며,
`leaprc.water.opc`가 OPC용 water와 Li/Merz 12-6 ion parameter를 함께 불러옵니다.
Water model을 바꾸면 density와 solvation thermodynamics를 비롯한 결과가 달라질 수 있습니다.

- [일반 MD 전체 안내](1_Simulation/1_MD/README.md)
- [Chignolin](1_Simulation/1_MD/1.1_Soluble_Protein/README.md)
- [T4 lysozyme–JZ4](1_Simulation/1_MD/1.2_Protein_Ligand/README.md)
- [KcsA](1_Simulation/1_MD/1.3_Membrane_Protein/README.md)

KcsA는 공개된 Lipid21 POPC bilayer를 2×2로 복제한 뒤 protein과 겹치는 lipid를 제거해
POPC 90%, POPE 5%, cholesterol 5% membrane을 만듭니다.
tleap build는 별도 단계입니다.
Detergent와 bulk water는 제거하고 selectivity filter K+ 7개와 filter·cavity water 16개를 유지합니다.
Neutral-pH baseline은 E71=`GLH`, D80=`ASP`, H25=`HIE`, E118/E120=`GLU`입니다.
Side chain 좌표가 불완전한 terminal H124는 제외합니다.

* CHARMM lipid force field와 CHARMM-GUI는 membrane simulation에서 오랫동안 사용된 조합입니다.
유명하고 많이 사용되었기 때문에 충분히 많은 검증이 이루어졌다는 것이 장점입니다.
* AMBER Lipid21은 AMBER protein·ligand force field와 함께 사용하기 편합니다.
* 이 튜토리얼에서는 CHARMM-GUI를 사용하지 않고 local에서 자체적으로 membrane protein system을 계산하는 방법을 다룹니다.


> GROMACS의 기본 사용법 및 GROMACS를 사용한 conventional MD simulation은 이 튜토리얼에서 다루지 않습니다. 참고 자료에 안내되어 있는 Lemkul's MD tutorials의 Lysozyme in Water와 KALP15 in DPPC 과정을 참조하시기 바랍니다.



### 1.2 Umbrella sampling

Umbrella sampling은 선택한 reaction coordinate를 여러 window로 나누고
각 window에 harmonic restraint를 적용하여 일반 MD에서 충분히 방문하기 어려운 영역을 sampling합니다.
분석 단계에서는 window overlap을 확인한 뒤
WHAM 또는 MBAR로 unbiased PMF를 복원합니다.

이 저장소의 예제는 먼저 PLUMED ratchet MD(ABMD)로 ordered seed pathway를 만듭니다.
Ratchet MD는 target-directed simulation이지만 constant-velocity pulling은 아닙니다.
목표 방향의 thermal fluctuation은 허용하고 반대 방향 fluctuation을 억제합니다.
Ratchet MD trajectory와 모든 umbrella window는 동일한 topology를 사용합니다.

핵심 검토 항목은 다음과 같습니다.

- reaction coordinate가 관심 transition을 구분하는가?
- seed structure가 전체 좌표 범위를 물리적으로 연결하는가?
- 인접 window의 분포가 충분히 겹치는가?
- restraint force constant의 단위와 프로그램 간 변환이 맞는가?
- equilibration 제거와 통계적 상관을 고려했는가?

- [Umbrella-sampling 튜토리얼](1_Simulation/2_US/README.md)
- [US PMF와 overlap 분석](2_Analysis/7_Enhanced_Sampling/7.1_Umbrella_Sampling/README.md)



### 1.3 Replica exchange

Replica exchange는 temperature 또는 Hamiltonian이 다른 replica 사이에서 상태를 교환합니다.
Analysis에는 exchange acceptance, round trip, ensemble별 sampling과 관심 observable을 사용합니다.

- T-REMD: replica마다 서로 다른 temperature 사용
- REST2: solute interaction을 scaling하여 전체 solvent 가열 비용 완화
- REST3: REST2에 solute–solvent interaction의 κ scaling 추가
- REUS: umbrella window를 Hamiltonian replica로 교환
- GaREUS: GaMD와 REUS를 결합한 확장 예제

- [Replica-exchange 튜토리얼](1_Simulation/3_REMD/README.md)
- [GaREUS reweighting](2_Analysis/7_Enhanced_Sampling/7.3_GaREUS_Reweighting/README.md)



### 1.4 Gaussian accelerated MD

GaMD는 potential-energy surface에 smooth boost를 추가합니다.
reaction coordinate를 고정하지 않는 대신 boost distribution과 reweighting quality를 함께 봅니다.

- GaMD: 일반적인 potential boost
- LiGaMD3: ligand, remaining nonbonded와 bonded potential의 triple boost
- Pep-GaMD: SH3–peptide binding을 위한 selective dual boost

- [GaMD 계열 튜토리얼](1_Simulation/4_GaMD/README.md)
- [GaMD reweighting](2_Analysis/7_Enhanced_Sampling/7.2_GaMD_Reweighting/README.md)



### 1.5 Free-energy perturbation

FEP는 직접적인 물리적 transition 대신 alchemical intermediate를 정의해 두 state의 자유에너지 차이를 계산합니다.

- RBFE: 유사한 두 ligand 또는 mutation 사이의 상대 자유에너지
- ABFE: restraint와 decoupling을 이용한 절대 결합 자유에너지

FEP input에는 lambda schedule, atom mapping, charge change, soft-core 설정과 window별 equilibration이 들어갑니다.
ABFE는 ligand position/orientation restraint와 standard-state correction도 포함합니다.
RBFE는 T4 lysozyme L99A의 benzene→toluene transformation, ABFE는 3HTB T4 lysozyme–JZ4를 사용합니다.
두 예제는 AMBER가 기록한 cross-state energy matrix를 FE-ToolKit MBAR로 분석하며 production은 1 ns/window입니다.
State overlap과 bootstrap uncertainty를 함께 확인합니다.

- [FEP 튜토리얼](1_Simulation/5_FEP/README.md)



### 1.6 Weighted ensemble

Weighted ensemble은 여러 weighted trajectory segment를 전파하고 WESTPA가 binning과 resampling을 수행하는 path-sampling 방법입니다.
물리적 dynamics를 변경하는 bias potential을 추가하지 않지만, progress coordinate와 초기·최종 상태 정의가 효율과 해석을 좌우합니다.

Chignolin 예제는 residue 2–9 Cα RMSD를 progress coordinate로 사용하여
total weight, restart, random seed, bin occupancy와 partially unfolded target 도달을 점검합니다.
Flux와 rate estimator는 포함하지 않습니다. Resampling과 weight는 WESTPA가 관리합니다.

- [WESTPA + AMBER WE 튜토리얼](1_Simulation/6_WE/README.md)



### 1.7 Metadynamics와 OPES

Metadynamics는 선택한 collective variable 공간에 history-dependent bias를 누적하여 이미 방문한 영역에서 벗어나도록 합니다.
Well-Tempered MetaD는 bias 증가를 완화하고, OPES는 목표 distribution에 접근하도록 bias를 구성합니다.
Funnel MetaD는 trypsin–benzamidine binding 경로를 cone과 cylinder 안으로 제한하고 ligand의 axis projection을 bias합니다.

Input에는 CV, Gaussian width·height, bias factor, pace, wall, grid와 단위를 기록합니다.
Restart할 때는 AMBER restart와 method별 `HILLS` 또는 OPES state를 함께 이어갑니다.

- [MetaD와 OPES 튜토리얼](1_Simulation/7_MetaD/README.md)



## 2. Trajectory 분석

이 section에서는 MD simulation 계산 후의 데이터 분석 방법에 대해 학습합니다.
data의 분석은 simulation 수행만큼이나 (혹은 그 이상으로) 중요한 과정입니다.
본 section을 학습하기 전에 `1_MD/1.1_Soluble_Protein`에서 기본 튜토리얼을 진행해서
학습에 필요한 예제 trajectory를 확보하시길 바랍니다.


권장 학습 순서는 다음과 같습니다.



1. [Trajectory preprocessing](2_Analysis/1_Preprocessing/README.md): imaging,
   alignment, stripping, 변환과 sampling
2. [Basic structural analysis](2_Analysis/2_Basic/README.md): RMSD, RMSF, Rg,
   distance, angle과 dihedral
3. [Interactions and structure](2_Analysis/3_Interactions/README.md): hydrogen
   bond, contact, SASA와 secondary structure
4. [Dimensionality reduction](2_Analysis/4_Dimension_Reduction/README.md): PCA, t-SNE와 UMAP
5. [Clustering](2_Analysis/5_Clustering/README.md): K-means, DBSCAN, HDBSCAN과 GMM
6. [Binding energy](2_Analysis/6_Binding_Energy/README.md): MM/GBSA와 MM/PBSA
7. [Enhanced-sampling analysis](2_Analysis/7_Enhanced_Sampling/README.md):
   umbrella-sampling PMF, histogram overlap, GaMD와 GaREUS reweighting


Cpptraj로 imaging, alignment와 기본 feature를 계산합니다.
Dimension reduction, clustering 방법은 Python을 사용해서 계산합니다.
시각화는 matplotlib의 pyplot 사용을 권장합니다.
t-SNE와 HDBSCAN은 scikit-learn, UMAP은 umap-learn을 사용합니다.

```bash
conda activate ambertools26
conda install -c conda-forge \
    "scikit-learn>=1.5,<2" \
    "umap-learn>=0.5.7,<0.6"
```

1–5번 analysis는 `1_MD/1.1_Soluble_Protein`에서 생성 된 Chignolin의 trajectory를 사용합니다.
MM/GBSA·MM/PBSA는 `1_MD/1.2_Protein_Ligand`에서 생성 된 T4 Lysozyme-JZ4 시스템의 trajectory를 사용합니다.



## 3. 참고 자료

- [AMBER](https://ambermd.org/)
- [GROMACS documentation](https://manual.gromacs.org/)
- [GROMACS tutorials](http://www.mdtutorials.com/gmx/)
- [PLUMED 2.10 user documentation](https://www.plumed.org/doc-v2.10/user-doc/html/index.html)
- [WESTPA documentation](https://westpa.readthedocs.io/)
- [REMD temperature generator](https://virtualchemistry.org/remd-temperature-generator/)
- [GaMD analysis resources](https://www.med.unc.edu/pharm/miaolab/resources/gamd/analysis/)
- [LiGaMD3](https://doi.org/10.1021/acs.jctc.4c00502)
- [Pep-GaMD](https://doi.org/10.1063/5.0021399)
- [Boresch restraint formulation](https://doi.org/10.1021/jp0217839)
- [Lipid21](https://doi.org/10.1021/acs.jctc.1c01217)
- [ff19SB](https://doi.org/10.1021/acs.jctc.9b00591)



## 4. 부록: 실행 상태와 복구

`1_Simulation`, `3_Templates`, `2_Analysis`의 `build.sh`, `run.sh`, `anal.py`가
공통으로 따르는 결과 보존, 실패 후 재실행, 동시 실행 보호 규칙입니다. 각
README는 method별 내용만 설명하고 이 부록을 가리킵니다.

#### 결과 보존

- Script는 기존 결과를 자동으로 지우거나 덮어쓰거나 다시 계산하지 않습니다.
- 완료된 stage, window와 segment는 다시 실행할 때 재사용하거나 건너뜁니다.
  Production까지 끝난 tutorial을 다시 실행하면 건너뛰고 다음 command를 안내한 뒤
  정상 종료합니다.
- 완료 판정에는 engine 성공 종료, 필수 output, 그 뒤에 기록한 완료 표시
  (`.<stage>.complete` 또는 `.<stage>.success.json`)가 모두 필요합니다.
- Output은 있는데 완료 표시가 없으면 partial로 보고 중단합니다.

#### 실패한 뒤 다시 실행

Partial output이 남으면 error가 stage, replica/window, 남은 파일과 실행할
command를 출력합니다. 보통 남은 파일을 `work` 밖으로 옮긴 뒤 같은 command를
다시 실행합니다.

```bash
mkdir -p work.failed
mv work/heat.out work/heat.rst7 work/heat.info work.failed/
./run.sh
```

- Replica와 window는 `000/production.out`처럼 파일 이름이 같습니다. Error가
  출력하는 command는 하위 directory를 유지하며 옮기므로 그대로 실행합니다.
- `work` 안의 다른 위치로 옮기면 기록이 없는 결과로 보고 거부합니다.
- Tutorial은 `work` 경로가 고정입니다. 처음부터 다시 하려면
  `mv work work.old` 후 `build.sh`부터 실행합니다. Template은 새 `WORK_DIR`을
  지정할 수도 있습니다.
- PLUMED bias를 이어받는 MetaD/OPES template은 segment마다
  `bias_start/`에 시작 시점 bias file을 남깁니다. 복원 절차는
  [3_Templates/7_MetaD/README.md](3_Templates/7_MetaD/README.md)에 있습니다.

#### Build

- Topology나 restart가 이미 있는 work에는 다시 build하지 않습니다.
- Template build는 `work/.build_tmp.XXXXXX/`에서 준비합니다. 성공하면 지우고,
  실패하면 진단용으로 남기고 경로를 출력합니다. `--keep-intermediates`는 성공한
  build에서도 남깁니다.
- REST2/REST3 tutorial·template과 REUS/GaREUS template은 모든 검사를 통과한 뒤
  마지막에 `work/build.done`을 씁니다. 이 파일이 없으면 `run.sh`가 시작하지
  않습니다.
- Template build는 `config.toml`에 template이 모르는 key가 있으면 경고합니다.
  대부분 오타이며, 그 key는 무시됩니다.

#### Input 변경

- 첫 실행 때 각 stage가 사용한 input의 SHA256을 `.*.identity.json`에 기록합니다.
- Topology, coordinate file, engine input이나 predecessor restart가 바뀌면 실행
  전에 거부합니다. 기록이 없는 과거 결과도 보존하고 거부합니다.
- Template은 build가 만든 `work/resolved_config.toml`을 읽습니다. Build 뒤에
  `config.toml`을 고쳐도 반영되지 않으므로 새 work에서 다시 build합니다.
- 기록에 절대 경로가 들어가므로 진행 중인 work를 옮기거나 복사해서 이어서
  실행하지 않습니다.

#### 동시 실행

- 같은 output이나 state를 쓰는 작업은 동시에 실행할 수 없습니다.
  `writer_guard.py`가 lock directory(보통 `work.writers/`)에 기록하고 거부합니다.
  서로 다른 `WORK_DIR`은 함께 실행할 수 있습니다.
- `--help`와 `--dry-run`은 lock과 identity를 만들지 않습니다.
- 정상 종료, 실패, Ctrl-C(INT/TERM) 뒤에는 자식 process 종료를 확인하고 자기
  lock만 해제합니다.
- SIGKILL이나 node 장애로 남은 lock은 자동으로 지우지 않습니다. Error에 나온
  `owner.json`의 host, PID, command를 확인하고, 해당 host와 scheduler에서 모든
  writer가 끝났는지 확인한 뒤 그 lock directory만 지웁니다.
  `work.writers/.gate/`도 같습니다.
- Network filesystem, remote MPI와 다른 node의 process 종료는 미검증입니다.

#### 실패했을 때 볼 파일

Engine이 실패하면 script가 아래 파일의 경로와 마지막 20줄을 출력합니다.

| 상황 | 파일 |
|---|---|
| AMBER stage | `<stage>.out`(예: `work/heat.out`), engine stdout/stderr `engine.<stage>.log` |
| tleap | `leap.log`, `tleap.stdout.log` |
| REST template build | `work/build.log` |
| AMBER REMD production | `work/mpirun.production.log` 또는 `mpirun.production.NNN.log`, 각 replica의 `production*.out` |
| GROMACS REST 준비 단계 | 각 replica의 `<stage>.grompp.log`, `<stage>.mdrun.log` |
| GROMACS REST production | 각 replica의 `production*.log` |
| PLUMED input 검사 | `work/plumed.parse.log` |
| WESTPA | `work/west.log` 또는 `west.NNN.log`, `work/seg_logs/`, `traj_segs/<iter>/<seg>/segment.out`, `west.init.log` |
| Analysis `run.sh` | `output.failed/*.log` |

#### Analysis output

- `run.sh`는 빈 임시 directory에서 계산하고, 필수 output을 확인한 뒤 output
  directory를 교체합니다. 실패하면 이전 결과를 그대로 두고 log를
  `<output>.failed/`에 복사합니다. 기본 output directory는 `output/`이고,
  `7.2_GaMD_Reweighting`은 `output/PROFILE/`, FEP와 MetaD `anal.py`는
  `work/analysis/`를 씁니다.
- 완료 파일의 hash는 `result_generation.py`(7.1, 7.3 analysis는 `prepare.py`)가
  generation 기록 file에 남기고, `anal.py`가 확인합니다. 기록이 없는 과거 결과는
  `run.sh`로 다시 만듭니다.
- `.<output>.pending` marker(예: `.output.pending`, `work/.analysis.pending`)가
  남았으면 게시가 중간에 멈춘 것입니다. Process가 끝났는지 확인한 뒤 marker에
  적힌 이전/새 directory를 함께 검사합니다. Marker만 지우고 다시 실행하지
  않습니다.

#### Download

- Tutorial `download.sh`는 파일과 `SHA256SUMS`를 staging에서 검사한 뒤
  게시합니다. 실패해도 기존 파일은 그대로 둡니다. `structure/.download.pending`이
  남으면 다음 download와 읽기를 거부하므로, 남은 staging과 marker를 함께
  확인합니다.
- Template `download.sh`는 임시 file에서 PDB atom record를 검사한 뒤
  저장합니다.



## English

This guide covers the learning order and how to choose a method. Commands and
input details live in each folder's `README.md`.

Every input is a teaching template. Production lengths differ by method and are
listed in each README. The default values are not simulation conditions for
judging convergence.

### Contents

0. [Before you start](#0-before-you-start)
1. [Simulation](#1-simulation)
   - [Conventional MD](#11-conventional-md-1)
   - [Umbrella sampling](#12-umbrella-sampling-1)
   - [Replica exchange](#13-replica-exchange-1)
   - [Gaussian accelerated MD](#14-gaussian-accelerated-md-1)
   - [Free-energy perturbation](#15-free-energy-perturbation-1)
   - [Weighted ensemble](#16-weighted-ensemble-1)
   - [Metadynamics and OPES](#17-metadynamics-and-opes)
2. [Trajectory analysis](#2-trajectory-analysis)
3. [References](#3-references)
4. [Appendix: Run state and recovery](#4-appendix-run-state-and-recovery)

### 0. Before you start

#### Background you need

The tutorials assume the following background and do not teach it:

- basic programming
- the Linux shell and working with files and directories
- installing Python packages and managing virtual environments
- the basic physics of MD, such as force fields
- protein structure
- running AMBER, GROMACS, and PLUMED
- what analyses such as RMSD, clustering, and dimensionality reduction are for

#### Define the question first

Decide the following before running any MD:

1. Which structural change or thermodynamic/kinetic quantity do you want to observe?
2. Is it reachable on the time scale of ordinary MD?
3. Can you define a suitable reaction coordinate or collective variable?
4. Do you need an equilibrium ensemble, or a transition pathway and rate?
5. Do the force field, protonation, membrane composition, and ligand state match the question?
6. Which independent measures will you use to judge convergence and uncertainty?

A different question or observable usually calls for a different simulation and
analysis method.

#### The two parts of the repository

```text
structure and scientific choices
              ↓
1_Simulation: system build → minimization → equilibration → trajectory
              ↓
2_Analysis: preprocessing → features → statistics → interpretation
```

- [Simulation tutorials](1_Simulation/README.md)
- [Analysis tutorials](2_Analysis/README.md)
- [Config templates for your own structure](3_Templates/README.md)
- [Run state and reruns after a failure](#4-appendix-run-state-and-recovery)

Learn the method and engine inputs in `1_Simulation/`, then use `3_Templates/`
to apply the same calculation to your own structure. A template takes a
build-ready PDB and a `config.toml`. It does not decide protonation, missing
atoms, or atom selections for your system.

### 1. Simulation

| No. | Method | Main purpose | Key prerequisite |
| --- | --- | --- | --- |
| 1 | Conventional MD | Dynamics over time | The pathway of interest is reachable on a conventional-MD time scale |
| 2 | US | PMF along a chosen coordinate | A suitable reaction coordinate and window overlap |
| 3 | REMD family | Better sampling through replica exchange | Design of the exchange variable and replica spacing |
| 4 | GaMD family | Barrier lowering without a reaction coordinate | Boost statistics and validated reweighting |
| 5 | FEP | Free-energy difference between two alchemical states | A stable mapping and lambda overlap |
| 6 | WE | Pathways, flux, and rates of rare events | Progress coordinate and state definitions |
| 7 | MetaD/OPES | Barrier lowering and free-energy exploration in CV space | Physically meaningful CVs and bias settings |

#### Common workflow

1. Record the source structure and where it came from
2. Review residues, ligands, ions, protonation, and missing atoms
3. Choose the force field and solvent model
4. Build the topology and initial coordinates
5. Minimize and equilibrate in stages
6. Keep the initial run separate from continuation/restart
7. Run a short teaching production
8. Check that outputs, restarts, and trajectories are consistent

#### 1.1 Conventional MD

Conventional MD follows structural change over time under the chosen
Hamiltonian and ensemble, with no added bias. It is the reference trajectory
for enhanced-sampling results and the starting point for most later analyses.

Each of the three systems has its own learning goal.

| System | Starting structure | Learning goal | Default AMBER model |
| --- | --- | --- | --- |
| Chignolin | PDB 1UAO | Protein build and basic structure/ensemble analysis | ff19SB + OPC |
| T4 lysozyme–JZ4 | PDB 3HTB | Ligand parameterization, interactions, ABFE, and end-state energies | ff19SB + GAFF2 + OPC |
| KcsA | PDB 1K4C | Membrane-protein coordinate/topology build and membrane analysis | ff19SB + Lipid21 + OPC |

The ff19SB tutorials use OPC, the water model the Amber 26 manual recommends
with ff19SB. OPC is a 4-site model with O, H1, H2, and a massless extra point
(EP). `leaprc.water.opc` loads the OPC water together with the matching Li/Merz
12-6 ion parameters. Changing the water model can change density, solvation
thermodynamics, and other results.

- [Conventional MD overview](1_Simulation/1_MD/README.md)
- [Chignolin](1_Simulation/1_MD/1.1_Soluble_Protein/README.md)
- [T4 lysozyme–JZ4](1_Simulation/1_MD/1.2_Protein_Ligand/README.md)
- [KcsA](1_Simulation/1_MD/1.3_Membrane_Protein/README.md)

The KcsA membrane is built by tiling a published Lipid21 POPC bilayer 2×2 and
removing lipids that overlap the protein, giving 90% POPC, 5% POPE, and 5%
cholesterol. The tleap build is a separate step. Detergent and bulk water are
removed; the seven selectivity-filter K+ ions and 16 filter and cavity waters
are kept. The neutral-pH baseline is E71=`GLH`, D80=`ASP`, H25=`HIE`, and
E118/E120=`GLU`. Terminal H124, whose side-chain coordinates are incomplete, is
excluded.

- CHARMM lipid force fields with CHARMM-GUI have long been used for membrane
  simulations, so they are widely validated.
- AMBER Lipid21 is convenient to combine with AMBER protein and ligand force
  fields.
- These tutorials build the membrane-protein system locally without CHARMM-GUI.

> Basic GROMACS usage and conventional MD with GROMACS are not covered. See
> the Lysozyme in Water and KALP15 in DPPC tutorials in Lemkul's MD tutorials
> (GROMACS tutorials under References).

#### 1.2 Umbrella sampling

Umbrella sampling splits a chosen reaction coordinate into windows and applies
a harmonic restraint in each, so regions that conventional MD rarely visits are
sampled. The analysis checks window overlap and then recovers the unbiased PMF
with WHAM or MBAR.

The example first builds an ordered seed pathway with PLUMED ratchet MD (ABMD).
Ratchet MD is target-directed but is not constant-velocity pulling: it allows
thermal fluctuations toward the target and suppresses those moving back. The
ratchet trajectory and all umbrella windows share one topology.

Check these points:

- Does the reaction coordinate separate the transition of interest?
- Do the seed structures physically connect the full coordinate range?
- Do neighboring windows overlap?
- Are the restraint force-constant units and cross-program conversions correct?
- Have you discarded equilibration and accounted for statistical correlation?

- [Umbrella-sampling tutorial](1_Simulation/2_US/README.md)
- [US PMF and overlap analysis](2_Analysis/7_Enhanced_Sampling/7.1_Umbrella_Sampling/README.md)

#### 1.3 Replica exchange

Replica exchange swaps states between replicas that differ in temperature or
Hamiltonian. The analysis uses exchange acceptance, round trips, per-ensemble
sampling, and the observables of interest.

- T-REMD: a different temperature for each replica
- REST2: scales solute interactions to avoid the cost of heating all solvent
- REST3: adds κ scaling of solute–solvent interactions to REST2
- REUS: exchanges umbrella windows as Hamiltonian replicas
- GaREUS: an extended example combining GaMD and REUS

- [Replica-exchange tutorials](1_Simulation/3_REMD/README.md)
- [GaREUS reweighting](2_Analysis/7_Enhanced_Sampling/7.3_GaREUS_Reweighting/README.md)

#### 1.4 Gaussian accelerated MD

GaMD adds a smooth boost to the potential-energy surface. It does not fix a
reaction coordinate, so the boost distribution and reweighting quality must be
checked together.

- GaMD: a general potential boost
- LiGaMD3: a triple boost of the ligand, remaining nonbonded, and bonded potentials
- Pep-GaMD: a selective dual boost for SH3–peptide binding

- [GaMD-family tutorials](1_Simulation/4_GaMD/README.md)
- [GaMD reweighting](2_Analysis/7_Enhanced_Sampling/7.2_GaMD_Reweighting/README.md)

#### 1.5 Free-energy perturbation

FEP computes the free-energy difference between two states through alchemical
intermediates instead of a physical transition.

- RBFE: relative free energy between two similar ligands or a mutation
- ABFE: absolute binding free energy using restraints and decoupling

FEP inputs contain the lambda schedule, atom mapping, charge changes, soft-core
settings, and per-window equilibration. ABFE also includes ligand
position/orientation restraints and a standard-state correction. RBFE uses the
benzene→toluene transformation in T4 lysozyme L99A, and ABFE uses 3HTB T4
lysozyme–JZ4. Both analyze the cross-state energy matrix written by AMBER with
FE-ToolKit MBAR; production is 1 ns per window. Check state overlap and the
bootstrap uncertainty together.

- [FEP tutorials](1_Simulation/5_FEP/README.md)

#### 1.6 Weighted ensemble

Weighted ensemble is a path-sampling method that propagates many weighted
trajectory segments while WESTPA handles binning and resampling. It adds no
bias potential to the physical dynamics, but efficiency and interpretation
depend on the progress coordinate and the initial and target state definitions.

The chignolin example uses the Cα RMSD of residues 2–9 as the progress
coordinate. It checks total weight, restart, random seeds, bin occupancy, and
arrival at a partially unfolded target. Flux and rate estimators are not
included. WESTPA manages resampling and weights.

- [WESTPA + AMBER WE tutorial](1_Simulation/6_WE/README.md)

#### 1.7 Metadynamics and OPES

Metadynamics builds up a history-dependent bias in a chosen collective-variable
space, pushing the system out of regions it has already visited. Well-Tempered
MetaD tempers the bias growth; OPES builds the bias toward a target
distribution. Funnel MetaD confines the trypsin–benzamidine binding path inside
a cone and cylinder and biases the ligand's projection on the funnel axis.

Record the CVs, Gaussian width and height, bias factor, pace, walls, grid, and
units in the input. On restart, continue the AMBER restart together with the
method's `HILLS` file or OPES state.

- [MetaD and OPES tutorials](1_Simulation/7_MetaD/README.md)

### 2. Trajectory analysis

This part covers analysis after the MD run. Analysis matters as much as running
the simulation, if not more. Run the basic tutorial in
`1_MD/1.1_Soluble_Protein` first to get the example trajectory.

Suggested order:

1. [Trajectory preprocessing](2_Analysis/1_Preprocessing/README.md): imaging,
   alignment, stripping, conversion, and sampling
2. [Basic structural analysis](2_Analysis/2_Basic/README.md): RMSD, RMSF, Rg,
   distances, angles, and dihedrals
3. [Interactions and structure](2_Analysis/3_Interactions/README.md): hydrogen
   bonds, contacts, SASA, and secondary structure
4. [Dimensionality reduction](2_Analysis/4_Dimension_Reduction/README.md): PCA, t-SNE, and UMAP
5. [Clustering](2_Analysis/5_Clustering/README.md): K-means, DBSCAN, HDBSCAN, and GMM
6. [Binding energy](2_Analysis/6_Binding_Energy/README.md): MM/GBSA and MM/PBSA
7. [Enhanced-sampling analysis](2_Analysis/7_Enhanced_Sampling/README.md):
   umbrella-sampling PMF, histogram overlap, and GaMD and GaREUS reweighting

Cpptraj handles imaging, alignment, and basic features. Dimensionality
reduction and clustering use Python. Matplotlib's pyplot is recommended for
plots. t-SNE and HDBSCAN use scikit-learn; UMAP uses umap-learn.

```bash
conda activate ambertools26
conda install -c conda-forge \
    "scikit-learn>=1.5,<2" \
    "umap-learn>=0.5.7,<0.6"
```

Analyses 1–5 use the chignolin trajectory from `1_MD/1.1_Soluble_Protein`.
MM/GBSA and MM/PBSA use the T4 lysozyme–JZ4 trajectory from
`1_MD/1.2_Protein_Ligand`.

### 3. References

- [AMBER](https://ambermd.org/)
- [GROMACS documentation](https://manual.gromacs.org/)
- [GROMACS tutorials](http://www.mdtutorials.com/gmx/)
- [PLUMED 2.10 user documentation](https://www.plumed.org/doc-v2.10/user-doc/html/index.html)
- [WESTPA documentation](https://westpa.readthedocs.io/)
- [REMD temperature generator](https://virtualchemistry.org/remd-temperature-generator/)
- [GaMD analysis resources](https://www.med.unc.edu/pharm/miaolab/resources/gamd/analysis/)
- [LiGaMD3](https://doi.org/10.1021/acs.jctc.4c00502)
- [Pep-GaMD](https://doi.org/10.1063/5.0021399)
- [Boresch restraint formulation](https://doi.org/10.1021/jp0217839)
- [Lipid21](https://doi.org/10.1021/acs.jctc.1c01217)
- [ff19SB](https://doi.org/10.1021/acs.jctc.9b00591)

### 4. Appendix: Run state and recovery

These rules on result preservation, reruns after failure, and concurrent-run
protection apply to `build.sh`, `run.sh` and `anal.py` in `1_Simulation`,
`3_Templates` and `2_Analysis`. Each README covers only its method and points
here.

#### Result preservation

- Scripts never delete, overwrite or recompute existing results automatically.
- Completed stages, windows and segments are reused or skipped on rerun.
  Rerunning a tutorial whose production is complete skips it, prints the next
  command and exits normally.
- Completion requires a successful engine exit, the required outputs, and a
  completion record written afterwards (`.<stage>.complete` or
  `.<stage>.success.json`).
- Outputs without a completion record are treated as partial and stop the run.

#### Rerunning after a failure

When partial output remains, the error prints the stage, replica/window, the
leftover files and the command to run. Usually you move those files out of
`work` and rerun the same command.

```bash
mkdir -p work.failed
mv work/heat.out work/heat.rst7 work/heat.info work.failed/
./run.sh
```

- Replicas and windows share file names such as `000/production.out`. The
  printed command keeps their subdirectories; run it as shown.
- Moving files elsewhere inside `work` is rejected as results without a record.
- Tutorials use a fixed `work` path. To start over, run `mv work work.old` and
  then `build.sh`. Templates can also use a new `WORK_DIR`.
- MetaD/OPES templates that continue PLUMED bias keep the bias files at the
  start of each segment in `bias_start/`. See
  [3_Templates/7_MetaD/README.md](3_Templates/7_MetaD/README.md) for the restore
  steps.

#### Build

- A work directory that already has a topology or restart is not rebuilt.
- Template builds prepare in `work/.build_tmp.XXXXXX/`. It is removed on success
  and kept for diagnosis on failure, with its path printed.
  `--keep-intermediates` keeps it after a successful build too.
- REST2/REST3 (tutorials and templates) and the REUS/GaREUS templates write
  `work/build.done` last, after every check passes. `run.sh` does not start
  without it.
- Template builds warn about keys in `config.toml` that the template does not
  know. They are usually typos and are ignored.

#### Input changes

- On the first run, each stage records the SHA256 of its inputs in
  `.*.identity.json`.
- A changed topology, coordinate file, engine input or predecessor restart is
  rejected before running. Older results without a record are preserved and
  rejected.
- Templates read `work/resolved_config.toml`, written by the build. Edits to
  `config.toml` after the build are not used; rebuild in a new work directory.
- Records contain absolute paths, so do not move or copy an active work tree to
  continue it.

#### Concurrent runs

- Jobs that write the same output or state cannot run together.
  `writer_guard.py` records locks in a lock directory (usually `work.writers/`) and rejects the second job.
  Different `WORK_DIR`s can run together.
- `--help` and `--dry-run` create no locks or identity records.
- After a normal exit, a failure or Ctrl-C (INT/TERM), a script confirms that its
  child processes stopped and releases only its own lock.
- Locks left by SIGKILL or node failure are not removed automatically. Check the
  host, PID and command in the reported `owner.json`, confirm on that host and in
  the scheduler that every writer stopped, then remove only that lock directory.
  The same applies to `work.writers/.gate/`.
- Network filesystems, remote MPI and termination of processes on other nodes
  are unverified.

#### Where to look after a failure

When an engine fails, the script prints the path and last 20 lines of these
files.

| Situation | File |
|---|---|
| AMBER stage | `<stage>.out` (e.g. `work/heat.out`), engine stdout/stderr in `engine.<stage>.log` |
| tleap | `leap.log`, `tleap.stdout.log` |
| REST template build | `work/build.log` |
| AMBER REMD production | `work/mpirun.production.log` or `mpirun.production.NNN.log`, and each replica's `production*.out` |
| GROMACS REST preparation | each replica's `<stage>.grompp.log`, `<stage>.mdrun.log` |
| GROMACS REST production | each replica's `production*.log` |
| PLUMED input check | `work/plumed.parse.log` |
| WESTPA | `work/west.log` or `west.NNN.log`, `work/seg_logs/`, `traj_segs/<iter>/<seg>/segment.out`, `west.init.log` |
| Analysis `run.sh` | `output.failed/*.log` |

#### Analysis output

- `run.sh` computes in an empty temporary directory, checks the required
  outputs and then replaces the output directory. On failure the previous
  results stay and the logs are copied to `<output>.failed/`. The default output
  directory is `output/`; `7.2_GaMD_Reweighting` uses `output/PROFILE/`, and the
  FEP and MetaD `anal.py` scripts use `work/analysis/`.
- `result_generation.py` (`prepare.py` in analysis 7.1 and 7.3) records the
  hashes of completed files in a generation record, and `anal.py` checks them.
  Regenerate older results without a record with `run.sh`.
- A leftover `.<output>.pending` marker (e.g. `.output.pending`,
  `work/.analysis.pending`) means publication stopped midway. Confirm the
  process ended, then inspect both the previous and new directories named in
  the marker. Do not remove only the marker and retry.

#### Download

- Tutorial `download.sh` scripts check the files and `SHA256SUMS` in staging
  before publishing. Existing files stay unchanged on failure. A leftover
  `structure/.download.pending` blocks further downloads and reads; inspect the
  remaining staging together with the marker.
- Template `download.sh` scripts check the PDB atom records in a temporary file
  before saving.
