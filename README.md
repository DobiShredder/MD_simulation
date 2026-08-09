# Molecular Dynamics Tutorials and Templates

[![AMBER](https://img.shields.io/badge/AMBER-26+-orange?style=flat)](https://ambermd.org/)
[![GROMACS](https://img.shields.io/badge/GROMACS-2026+-blue?style=flat&logo=gromacs)](https://manual.gromacs.org/)
[![PLUMED](https://img.shields.io/badge/PLUMED-2.10+-green?style=flat)](https://www.plumed.org/doc-v2.10/user-doc/html/index.html)
[![WESTPA](https://img.shields.io/badge/WESTPA-2+-blueviolet?style=flat)](https://westpa.github.io/westpa/)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow?style=flat&logo=python)](https://www.python.org/)


### A comprehensive collection of Molecular Dynamics (MD) simulation tutorials using **AMBER** and **GROMACS**.
### This repository covers enhanced sampling techniques ranging from conventional MD to free energy calculations.



> [!IMPORTANT]
> 이 코드들은 범용 production protocol이 아닌 시작 템플릿입니다.
> 실제 system에 맞는 force field, protonation, 원자 선택, equilibration, sampling 및 수렴성을
> 사용자가 반드시 직접 디자인하고 검증해야합니다.
> 학습용 production은 10–20 ns로 제한합니다.
>
> These are starting templates, not universal production protocols. Users must
> design and validate the force field, protonation states, atom selections,
> equilibration, sampling strategy, and convergence criteria for their own
> systems. Training production runs are limited to 10–20 ns.



## Quick start / 빠른 시작

1. Read the [integrated tutorial guide / 통합 튜토리얼 가이드](GUIDE.md).
2. Choose a [simulation tutorial / 시뮬레이션 튜토리얼](1_Simulation/README.md).
3. Process its trajectory with an [analysis tutorial / 분석 튜토리얼](2_Analysis/README.md).



## Repository structure / 저장소 구조

```text
MD_simulation/
├── GUIDE.md                 # Integrated curriculum and method selection
├── 1_Simulation/
│   ├── 1_MD/
│   │   ├── 1.1_Soluble_Protein/    # Chignolin, PDB 1UAO
│   │   ├── 1.2_Protein_Ligand/     # Trypsin–benzamidine, PDB 3PTB
│   │   └── 1.3_Membrane_Protein/   # KcsA, PDB 1K4C
│   ├── 2_US/                # Umbrella sampling
│   ├── 3_REMD/              # REMD, REST2, REST3, REUS, GaREUS
│   ├── 4_GaMD/              # GaMD variants
│   ├── 5_FEP/               # RBFE and ABFE
│   ├── 6_WE/                # WESTPA + AMBER weighted ensemble
│   └── 7_MetaD/             # MetaD and OPES variants
└── 2_Analysis/
    ├── 1_Preprocessing/
    ├── 2_Basic/
    ├── 3_Interactions/
    ├── 4_Dimension_Reduction/
    ├── 5_Clustering/
    ├── 6_Binding_Energy/
    └── 7_Enhanced_Sampling/
```

## Simulation tutorials / 시뮬레이션 튜토리얼

| No. | Method | Included templates | Guide |
| --- | --- | --- | --- |
| 1 | Conventional MD | Chignolin, trypsin–benzamidine, KcsA with AMBER | [Open](1_Simulation/1_MD/README.md) |
| 2 | Ratchet MD / Umbrella Sampling | PLUMED ABMD pathway and restrained windows | [Open](1_Simulation/2_US/README.md) |
| 3 | Replica Exchange | REMD, REST2, REST3, REUS, GaREUS | [Open](1_Simulation/3_REMD/README.md) |
| 4 | Gaussian accelerated MD | Chignolin GaMD, trypsin–benzamidine LiGaMD3, SH3–peptide Pep-GaMD | [Open](1_Simulation/4_GaMD/README.md) |
| 5 | Free Energy Perturbation | T4L benzene→toluene RBFE and trypsin–benzamidine ABFE | [Open](1_Simulation/5_FEP/README.md) |
| 6 | Weighted Ensemble | Na⁺/Cl⁻ distance sampling with WESTPA and AMBER | [Open](1_Simulation/6_WE/README.md) |
| 7 | Metadynamics | WT-MetaD, funnel MetaD, OPES, OPES Expanded | [Open](1_Simulation/7_MetaD/README.md) |

## Analysis areas / 분석 영역

분석 파트는 preprocessing, 기본 구조 지표, interaction, dimension reduction,
clustering 및 MM/GB(PB)SA로 구성됩니다. Preprocessing, 기본 구조 지표와
interaction tutorial은 Chignolin trajectory를 사용하는 실행 예제입니다.
Trajectory 처리는 cpptraj을 중심으로 하고 t-SNE, clustering, 통계와 plotting은
Python으로 진행합니다.


The analysis section covers preprocessing, basic structural metrics,
interactions, dimensionality reduction, clustering, and MM/GB(PB)SA. Runnable
preprocessing, basic, and interaction examples use the Chignolin trajectory.
Trajectory processing primarily uses cpptraj, while t-SNE, clustering,
statistics, and plotting use Python.



| Area | Contents | Guide |
| --- | --- | --- |
| Preprocessing | Imaging, alignment, conversion and sampling | [Open](2_Analysis/1_Preprocessing/README.md) |
| Basic | RMSD, RMSF, Rg, distance, angle and dihedral | [Open](2_Analysis/2_Basic/README.md) |
| Interactions | Hydrogen bonds, contacts, SASA and secondary structure | [Open](2_Analysis/3_Interactions/README.md) |
| Dimensionality reduction | PCA and t-SNE | [Open](2_Analysis/4_Dimension_Reduction/README.md) |
| Clustering | K-means and DBSCAN | [Open](2_Analysis/5_Clustering/README.md) |
| Binding energy | MM/GBSA and MM/PBSA | [Open](2_Analysis/6_Binding_Energy/README.md) |
| Enhanced sampling | Umbrella-sampling PMF, overlap and GaMD reweighting | [Open](2_Analysis/7_Enhanced_Sampling/README.md) |

## Example systems / 예제 시스템

| System | Role | Source and important choices |
| --- | --- | --- |
| Chignolin | Soluble-protein MD and structural/ensemble analysis | PDB 1UAO; first NMR model; ff19SB/TIP3P |
| Trypsin–benzamidine | Protein–ligand interactions and MM/GB(PB)SA | PDB 3PTB; BEN, structural Ca2+, six disulfides; ff19SB/GAFF2/TIP3P |
| KcsA | Membrane build and membrane-protein analysis | PDB 1K4C; ff19SB/Lipid21/OPC; POPC:POPE:cholesterol 90:5:5 |
| C-crk SH3–SOS peptide | Pep-GaMD selective peptide boost | PDB 1CKB; resolved PPPVPPRR peptide; ff19SB/TIP3P |

Source structures are downloaded at runtime and checksums are recorded. Large
or generated coordinates, trajectories, restarts, topologies, and logs are not
distributed through Git.

## Method references

| Method | Journal | Year | Citation |
| --- | --- | ---: | --- |
| US | *J. Comput. Phys.* | 1977 | [23, 187–199](https://doi.org/10.1016/0021-9991(77)90121-8) |
| REMD | *Chem. Phys. Lett.* | 1999 | [314, 141–151](https://doi.org/10.1016/S0009-2614(99)01123-9) |
| REST | *PNAS* | 2005 | [102, 13749–13754](https://doi.org/10.1073/pnas.0506346102) |
| REST3 | *J. Chem. Theory Comput.* | 2023 | [19, 1346–1356](https://doi.org/10.1021/acs.jctc.2c01139) |
| REUS | *J. Chem. Phys.* | 2000 | [113, 6042–6051](https://doi.org/10.1063/1.1308516) |
| GaMD | *J. Chem. Theory Comput.* | 2015 | [11, 3584–3595](https://doi.org/10.1021/acs.jctc.5b00436) |
| LiGaMD3 | *J. Chem. Theory Comput.* | 2024 | [Triple-boost LiGaMD](https://doi.org/10.1021/acs.jctc.4c00502) |
| Pep-GaMD | *J. Chem. Phys.* | 2020 | [153, 154109](https://doi.org/10.1063/5.0021399) |
| WE | *J. Chem. Phys.* | 1996 | [105, 1604–1610](https://doi.org/10.1063/1.472061) |
| MetaD | *PNAS* | 2002 | [99, 12562–12566](https://doi.org/10.1073/pnas.202427399) |
| WT-MetaD | *Phys. Rev. Lett.* | 2008 | [100, 020603](https://doi.org/10.1103/PhysRevLett.100.020603) |
| OPES | *J. Phys. Chem. Lett.* | 2020 | [11, 2731–2736](https://doi.org/10.1021/acs.jpclett.0c00497) |



## 🛠️ Prerequisites & Tools

The tutorials utilize the following software packages. Please ensure they are installed and properly configured in your environment.

| Software | Description | Official Site |
| :--- | :--- | :--- |
| ![AMBER](https://img.shields.io/badge/AMBER-26+-orange) | MD simulation package | [ambermd.org](http://ambermd.org/) |
| ![GROMACS](https://img.shields.io/badge/GROMACS-2026+-blue) | MD simulation package | [gromacs.org](https://manual.gromacs.org/)
| ![PLUMED](https://img.shields.io/badge/PLUMED-2.10+-lightgrey) | Plugin for enhanced sampling algorithms | [plumed.org](https://www.plumed.org/) |
| ![Python](https://img.shields.io/badge/Python-3.10%2B-yellow?logo=python&logoColor=white) | Analysis & plotting | [python.org](https://www.python.org/) |

### AmberTools 26 installation / 설치

AmberTools 26은 conda-forge에서 Linux와 macOS용 binary package로 제공됩니다.
별도 environment를 만든 뒤 Amber environment script를 불러옵니다.
Weighted Ensemble (WE) 계산을 위한 WESTPA도 같은 environment에 install하는 것을 추천드립니다.

```bash
conda create -n ambertools26 -c conda-forge python=3.12 ambertools=26
conda activate ambertools26
source "$CONDA_PREFIX/amber.sh"
conda install westpa -c conda-forge
```

설치 결과는 다음 command로 확인합니다.

```bash
conda list ambertools
command -v tleap
command -v sander
command -v cpptraj
command -v antechamber
python3 -c "import parmed; print(parmed.__version__)"
```

Conda-forge package는 topology build, `sander` CPU test와 cpptraj analysis에
사용할 수 있습니다. CPU parallel 및 CUDA support는 포함하지 않습니다.
Tutorial의 기본 production engine인 `pmemd.cuda`는 별도의 Amber 26 설치와
지원되는 GPU가 필요합니다. AmberTools만 설치한 환경에서 짧은 test를 실행할
때는 `AMBER_ENGINE=sander`를 지정합니다.

```bash
AMBER_ENGINE=sander ./run.sh --dry-run
```

[AmberTools 26 공식 설치 안내](https://ambermd.org/GetAmber.php)와
[Amber 2026 Reference Manual](https://ambermd.org/doc12/Amber26.pdf)에서
platform별 차이와 설치 후 test 방법을 확인할 수 있습니다.

### 🐍 Python Dependencies
To run the analysis scripts, you need the following Python libraries. You can install them via `pip` or `conda`.

I recommend to manage your Python packages through virtual environment (ex: [Anaconda](https://www.anaconda.com/download))
```bash
numpy
pandas
matplotlib
pymbar
alchemlyb
MDAnalysis
```




*If you need any help, please contact me.*




*Created and maintained by DobiShredder*
