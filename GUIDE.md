# MD simulation tutorials: integrated guide

저장소의 학습 순서와 method 선택 기준을 정리한 문서입니다. 실행 command와
input 설명은 각 폴더의 `README.md`에 있습니다.

모든 input은 학습용 template입니다. Production 길이는 method마다 다르며 각
README에 적혀 있습니다. 어느 기본값도 수렴을 판정하기 위한 길이가 아닙니다.

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

## 0. 학습 전 준비

### 필요한 배경

- Linux shell과 파일·디렉터리의 기본 사용법
- AMBER, GROMACS, PLUMED 또는 WESTPA 중 사용할 프로그램의 기본 실행법
- force field, potential energy, ensemble, periodic boundary condition,
  thermostat와 barostat의 기본 개념
- Python 환경과 package 설치·분리 방법
- RMSD, clustering, dimension reduction 등 분석 방법의 목적

설치, 라이선스, GPU/cluster 환경과 scheduler 설정은 저장소의 범위 밖입니다.
튜토리얼은 개인 경로, queue, module 명령을 포함하지 않습니다.

### 먼저 질문을 정의하기

Method를 고르기 전에 아래 항목을 정합니다.

1. 관찰하려는 구조 변화나 열역학·속도론적 양은 무엇인가?
2. 일반 MD 시간 척도에서 관찰 가능한가?
3. 적절한 reaction coordinate 또는 collective variable을 정의할 수 있는가?
4. equilibrium ensemble이 필요한가, transition pathway와 rate가 필요한가?
5. force field, protonation, 막 조성, ligand 상태가 질문과 일치하는가?
6. 수렴과 불확실성을 어떤 독립적인 지표로 판단할 것인가?

질문과 관측량이 달라지면 simulation·analysis method도 달라집니다.

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

## 1. 시뮬레이션

| 번호 | 방법 | 주된 목적 | 주요 사전 조건 |
| --- | --- | --- | --- |
| 1 | 일반 MD | 자연스러운 국소 dynamics와 기준 trajectory | 관심 과정이 접근 가능한 시간 척도에 존재 |
| 2 | US | 선택한 좌표를 따른 PMF | 적절한 reaction coordinate와 window overlap |
| 3 | REMD 계열 | replica 교환을 통한 sampling 향상 | 교환 변수와 replica 분포 설계 |
| 4 | GaMD 계열 | reaction-coordinate-free barrier 완화 | boost 통계와 reweighting 검증 |
| 5 | FEP | 두 alchemical state의 자유에너지 차이 | 안정적인 mapping과 lambda overlap |
| 6 | WE | 희귀 사건의 pathway, flux와 rate | progress coordinate와 상태 정의 |
| 7 | MetaD/OPES | CV 공간의 barrier 완화와 자유에너지 탐색 | 물리적으로 유효한 CV와 bias 설정 |

### 공통 계산 흐름

공통 workflow는 아래 순서를 따릅니다.

1. 원본 구조와 출처 기록
2. residue, ligand, ion, protonation과 결손 원자 검토
3. force field와 solvent model 선택
4. topology와 초기 좌표 생성
5. 단계별 minimization과 equilibration
6. 초기 실행과 continuation/restart 구분
7. 짧은 교육용 production
8. 출력·restart·trajectory의 일관성 확인

Syntax check와 정상 종료는 물리적 검증이나 수렴 판단을 대신하지 않습니다.

### 현재 검증 범위

AmberTools 26의 topology build, 짧은 `sander`/cpptraj 계산, WESTPA 연결과
Python fixture는 확인했습니다. 다음 실제 engine 조합은 아직 다른 PC에서
검증해야 합니다.

- Amber 26 `pmemd.cuda` production과 GPU 전용 GaMD·FEP 기능
- `pmemd.cuda.MPI` T-REMD, REUS와 GaREUS replica exchange
- GROMACS/PLUMED REST2·REST3 HREX
- PLUMED가 연결된 AMBER의 ratchet MD, WT-MetaD와 OPES

따라서 local README에 opt-in gate나 호환성 경고가 있는 method는 해당 표시를
유지합니다. 짧은 actual run, restart와 output 검사를 통과하기 전에는 검증
완료로 간주하지 않습니다.

### 1.1 conventional MD

일반 MD는 별도의 bias 없이 선택한 Hamiltonian과 ensemble에서 시간에 따른
구조 변화를 계산합니다. Enhanced-sampling 결과를 비교하기 위한 기준
trajectory이며 대부분의 후속 분석을 배우는 출발점입니다.

세 시스템이 서로 다른 학습 목표를 담당합니다.

| 시스템 | 시작 구조 | 학습 목표 | 기본 AMBER model |
| --- | --- | --- | --- |
| Chignolin | PDB 1UAO | 수용성 단백질 build와 기본 구조·ensemble 분석 | ff19SB + TIP3P |
| T4 lysozyme–JZ4 | PDB 3HTB | ligand parameterization, interaction, ABFE와 end-state energy | ff19SB + GAFF2 + TIP3P |
| KcsA | PDB 1K4C | 막 단백질 좌표·topology build와 membrane analysis | ff19SB + Lipid21 + OPC |

ff19SB 개발 논문에서는 TIP3P와 OPC를 모두 평가했고, OPC에서 더 나은
성능을 보고했습니다. 이 저장소는 비막 system의 교육용 기본값을 TIP3P로
통일합니다. Water model을 바꾸면 결과가 동일하다고 가정하지 않습니다.

- [일반 MD 전체 안내](1_Simulation/1_MD/README.md)
- [Chignolin](1_Simulation/1_MD/1.1_Soluble_Protein/README.md)
- [T4 lysozyme–JZ4](1_Simulation/1_MD/1.2_Protein_Ligand/README.md)
- [KcsA](1_Simulation/1_MD/1.3_Membrane_Protein/README.md)

KcsA는 공개된 평형화 Lipid21 POPC bilayer를 2×2로 복제한 뒤 protein과
겹치는 lipid를 제거해 POPC 90%, POPE 5%, cholesterol 5% membrane을
만듭니다. tleap build는 별도 단계입니다. Detergent와 bulk 결정수는
제거하고 selectivity filter K+ 7개와 filter·cavity water 16개를
유지합니다. Neutral-pH baseline은 E71=`GLH`, D80=`ASP`, H25=`HIE`,
E118/E120=`GLU`입니다. Side chain 좌표가 불완전한 terminal H124는
제외합니다.

CHARMM lipid force field와 CHARMM-GUI는 membrane simulation에서 오래
사용된 조합입니다. AMBER Lipid21은 AMBER protein·ligand force field와 함께
사용하기 편합니다. 선택 기준은 lipid 조성, water/ion model과 비교할 실험
자료입니다.

입문용 GROMACS 일반 MD는 이 저장소에서 중복 구현하지 않습니다. 아래의
Lemkul 튜토리얼의 Lysozyme in Water와 KALP15 in DPPC 과정을
선행 자료로 사용합니다.

### 1.2 Umbrella sampling

Umbrella sampling은 선택한 reaction coordinate를 여러 window로 나누고
각 window에 harmonic restraint를 적용하여 일반 MD에서 충분히 방문하기
어려운 영역을 sampling합니다. 분석 단계에서는 window overlap을 확인한 뒤
WHAM 또는 MBAR로 unbiased PMF를 복원합니다.

이 저장소의 예제는 먼저 PLUMED ABMD ratchet MD로 ordered seed pathway를
만듭니다. Ratchet MD는 target-directed simulation이지만 constant-velocity
pulling은 아닙니다. 목표 방향의 thermal fluctuation은 허용하고 반대 방향
fluctuation을 억제합니다. Ratchet trajectory와 모든 umbrella window는
동일한 topology를 사용합니다.

핵심 검토 항목은 다음과 같습니다.

- reaction coordinate가 관심 transition을 구분하는가?
- seed structure가 전체 좌표 범위를 물리적으로 연결하는가?
- 인접 window의 분포가 충분히 겹치는가?
- restraint force constant의 단위와 프로그램 간 변환이 맞는가?
- equilibration 제거와 통계적 상관을 고려했는가?

- [Umbrella-sampling 튜토리얼](1_Simulation/2_US/README.md)
- [US PMF와 overlap 분석](2_Analysis/7_Enhanced_Sampling/7.1_Umbrella_Sampling/README.md)

### 1.3 Replica exchange

Replica exchange는 temperature 또는 Hamiltonian이 다른 replica 사이에서
상태를 교환합니다. Analysis에는 exchange acceptance, round trip,
ensemble별 sampling과 관심 observable을 사용합니다.

- T-REMD: replica마다 서로 다른 temperature 사용
- REST2: solute interaction을 scaling하여 전체 solvent 가열 비용 완화
- REST3: REST2에 solute–solvent interaction의 κ scaling 추가
- REUS: umbrella window를 Hamiltonian replica로 교환
- GaREUS: GaMD와 REUS를 결합한 확장 예제

- [Replica-exchange 튜토리얼](1_Simulation/3_REMD/README.md)
- [GaREUS reweighting](2_Analysis/7_Enhanced_Sampling/7.3_GaREUS_Reweighting/README.md)

### 1.4 Gaussian accelerated MD

GaMD는 potential-energy surface에 smooth boost를 추가합니다. 하나의
reaction coordinate를 고정하지 않는 대신 boost distribution과 reweighting
quality를 함께 봅니다.

- GaMD: 일반적인 potential boost
- LiGaMD3: ligand, remaining nonbonded와 bonded potential의 triple boost
- Pep-GaMD: SH3–peptide binding을 위한 selective dual boost

- [GaMD 계열 튜토리얼](1_Simulation/4_GaMD/README.md)
- [GaMD reweighting](2_Analysis/7_Enhanced_Sampling/7.2_GaMD_Reweighting/README.md)

### 1.5 Free-energy perturbation

FEP는 직접적인 물리적 transition 대신 alchemical intermediate를 정의해
두 state의 자유에너지 차이를 계산합니다.

- RBFE: 유사한 두 ligand 또는 mutation 사이의 상대 자유에너지
- ABFE: restraint와 decoupling을 이용한 절대 결합 자유에너지

FEP input에는 lambda schedule, atom mapping, charge change, soft-core 설정과
window별 equilibration이 들어갑니다. ABFE는 ligand position/orientation
restraint와 standard-state correction도 포함합니다. RBFE는 T4 lysozyme L99A의
benzene→toluene transformation, ABFE는 3HTB T4 lysozyme–JZ4를 사용합니다.
두 예제는 AMBER가 기록한 cross-state energy matrix를 FE-ToolKit MBAR로 분석하며
production은 2 ns/window입니다. State overlap과 bootstrap uncertainty를 함께
확인합니다.

- [FEP 튜토리얼](1_Simulation/5_FEP/README.md)

### 1.6 Weighted ensemble

Weighted ensemble은 여러 weighted trajectory segment를 전파하고 WESTPA가
binning과 resampling을 수행하는 path-sampling 방법입니다. 물리적 dynamics를
변경하는 bias potential을 추가하지 않지만, progress coordinate와 초기·최종
상태 정의가 효율과 해석을 좌우합니다.

현재 Na⁺/Cl⁻ 예제는 total weight, restart, random seed, bin occupancy와 target
도달을 점검합니다. Flux와 rate estimator는 포함하지 않습니다. Resampling과
weight는 WESTPA가 관리합니다.

- [WESTPA + AMBER WE 튜토리얼](1_Simulation/6_WE/README.md)

### 1.7 Metadynamics와 OPES

Metadynamics는 선택한 collective variable 공간에 history-dependent bias를
누적하여 이미 방문한 영역에서 벗어나도록 합니다. Well-tempered MetaD는
bias 증가를 완화하고, OPES는 목표 distribution에 접근하도록 bias를
구성합니다. Funnel MetaD는 trypsin–benzamidine binding 경로를 cone과
cylinder 안으로 제한하고 ligand의 axis projection을 bias합니다.

Input에는 CV, Gaussian width·height, bias factor, pace, wall, grid와 단위를
기록합니다. Restart할 때는 AMBER restart와 method별 `HILLS` 또는 OPES state를
함께 이어갑니다.

- [MetaD와 OPES 튜토리얼](1_Simulation/7_MetaD/README.md)

## 2. Trajectory 분석

Analysis는 simulation method와 분리합니다. 공통 preprocessing과 feature를
재사용하고 topology, trajectory, mask, stride, 단위와 output column을
기록합니다.

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

Cpptraj로 imaging, alignment와 기본 feature를 계산합니다. PCA, t-SNE, UMAP과
clustering은 표 형태의 feature를 Python으로 전달합니다. Dimension-reduction
plot과 cluster 결과는 representative structure, 시간 순서와 parameter
sensitivity를 함께 봅니다.

t-SNE와 HDBSCAN은 scikit-learn, UMAP은 umap-learn을 사용합니다.

```bash
conda activate ambertools26
conda install -c conda-forge \
    "scikit-learn>=1.5,<2" \
    "umap-learn>=0.5.7,<0.6"
```

1–5번 analysis는 Chignolin conventional-MD output을 사용합니다.
MM/GBSA·MM/PBSA는 T4 lysozyme–JZ4 output을 사용합니다. KcsA의
membrane-aware preprocessing과 채널 구조 분석은 이후 범위입니다.

## 3. 참고 자료

- [AMBER](https://ambermd.org/)
- [GROMACS documentation](https://manual.gromacs.org/)
- [Lemkul GROMACS tutorials](http://www.mdtutorials.com/gmx/)
- [PLUMED 2.10 user documentation](https://www.plumed.org/doc-v2.10/user-doc/html/index.html)
- [WESTPA documentation](https://westpa.readthedocs.io/)
- [REMD temperature generator](https://virtualchemistry.org/remd-temperature-generator/)
- [GaMD analysis resources](https://www.med.unc.edu/pharm/miaolab/resources/gamd/analysis/)
- [LiGaMD3](https://doi.org/10.1021/acs.jctc.4c00502)
- [Pep-GaMD](https://doi.org/10.1063/5.0021399)
- [Boresch restraint formulation](https://doi.org/10.1021/jp0217839)
- [Lipid21](https://doi.org/10.1021/acs.jctc.1c01217)
- [ff19SB](https://doi.org/10.1021/acs.jctc.9b00591)
