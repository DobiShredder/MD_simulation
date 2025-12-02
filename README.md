# 🧬 Molecular Dynamics Simulation Tutorials

[![AMBER](https://img.shields.io/badge/AMBER-20+-orange?style=flat)](https://ambermd.org/)
[![GROMACS](https://img.shields.io/badge/GROMACS-2020+-blue?style=flat&logo=gromacs)](https://manual.gromacs.org/)
[![PLUMED](https://img.shields.io/badge/PLUMED-2.7+-lightgrey?style=flat)](https://www.plumed.org/)
[![Python](https://img.shields.io/badge/Python-3.8+-yellow?style=flat&logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

A comprehensive collection of Molecular Dynamics (MD) simulation tutorials using **AMBER** and **GROMACS**.

This repository covers enhanced sampling techniques ranging from conventional MD to free energy calculations.

**Youtube videos and presentation files for description will be updated soon**



**presentation slides for description (updating):** [**here**](https://docs.google.com/presentation/d/1rGrlHCfM9lWvhG1cafMP6cIJ3lagn0hf/edit?usp=drive_link&ouid=111574709419600577762&rtpof=true&sd=true)

---

## 📚 Table of Contents

### 1. 💧 Conventional MD Simulation
Basic setup and production runs for conventional molecular dynamics.

### 2. ☂️ US (Umbrella Sampling)
Free energy calculations along a reaction coordinate using the umbrella sampling method.

### 3. 🌡️ REMD (Replica Exchange Molecular Dynamics)
Enhanced sampling techniques to overcome energy barriers.
- **3.1 REMD**: Standard T-REMD (Temperature-Replica Exchange).
- **3.2 REST**: Replica Exchange with Solute Tempering (using **GROMACS**).
- **3.3 REUS**: Replica Exchange Umbrella Sampling (combining REMD + US).
- **3.4 GaREUS**: Gaussian accelerated Replica Exchange Umbrella Sampling.

### 4. 🚀 Gaussian Accelerated MD (GaMD)
Unconstrained enhanced sampling method that works by adding a boost potential.
- **4.1 GaMD**: Gaussian accelerated MD.
- **4.2 LiGaMD**: Ligand GaMD for protein-ligand interaction.
- **4.3 Pep-GaMD**: Peptide GaMD for protein-peptide interaction.
- **4.4 PPi-GaMD**: Protein-Protein interaction GaMD.

### 5. ⚡ Free Energy Perturbation (FEP)
Alchemical free energy calculations
- **5.1 RBFE**: Relative Binding Free Energy (using **GROMACS**).
- **5.2 ABFE**: Absolute Binding Free Energy (using **AMBER**).

### 6. 🏔️ Metadynamics (MetaD)
Bias potential methods based on collective variables.
- **6.1 Funnel-MetaD**: Funnel-restrained Metadynamics for binding free energy.
- **6.2 OPES**: On-the-fly Probability Enhanced Sampling (Next-gen Metadynamics).

---

## 📂 Directory Structure

```bash
MD-Simulation-Tutorials/
├── 1_MD/
│   ├── AMBER/               # Conventional MD with AMBER
│   └── GMX/                 # Conventional MD with GROMACS
├── 2_US/                    # Umbrella Sampling
├── 3_REMD/
│   ├── 3.1_REMD/            # Standard REMD
│   ├── 3.2_REST/            # Solute Tempering (GROMACS)
│   ├── 3.3_REUS/            # Replica Exchange US
│   └── 3.4_GaREUS/          # Gaussian accelerated REUS
├── 4_GaMD/
│   ├── 4.1_GaMD/            # Standard GaMD
│   ├── 4.2_LiGaMD/          # Ligand-GaMD
│   ├── 4.3_Pep-GaMD/        # Peptide-GaMD
│   └── 4.4_PPi-GaMD/        # Protein-Protein interaction GaMD
├── 5_FEP/
│   ├── 5.1_RBFE/            # Relative Binding Free Energy
│   └── 5.2_ABFE/            # Absolute Binding Free Energy
└── 6_MetaD/
	├── 6.1_WT-MetaD/        # Well-Tempered Metadynamics
    ├── 6.2_funnel-MetaD/    # funnel-restrainted Metadynamics
    └── 6.3_OPES/            # OPES Method
```


| Method | Journal | Year | Citation
| :--- | :--- | :---: | :--- |
| **REMD** | *Chem. Phys. Lett.* | 1999 | [314(1-2), 141-151](https://doi.org/10.1016/S0009-2614(99)01123-9)
| **GaMD** | *J. Chem. Theory Comput.* | 2015 | [11(8), 3584-3595](https://dx.doi.org/10.1021/acs.jctc.5b00436)
| **FEP** | *PNAS* | 2005 | [102(19), 6825-6830](https://doi.org/10.1073/pnas.0409005102)
| **MetaD** | *PNAS* | 2002 | [99(20), 12562-12566](https://doi.org/10.1073/pnas.202427399)
| **WT-MetaD** | *Phys. Rev. Lett.* | 2008 | [100, 020603](https://doi.org/10.1103/PhysRevLett.100.020603)
| **OPES** | *J. Phys. Chem. Lett.* | 2020 | [11, 2731-2736](http://dx.doi.org/10.1021/acs.jpclett.0c00497)


## 🛠️ Prerequisites & Tools

The tutorials utilize the following software packages. Please ensure they are installed and properly configured in your environment.

| Software | Description | Official Site |
| :--- | :--- | :--- |
| ![AMBER](https://img.shields.io/badge/AMBER-20+-orange) | MD simulation package | [ambermd.org](http://ambermd.org/) |
| ![GROMACS](https://img.shields.io/badge/GROMACS-2020+-blue) | MD simulation package | [gromacs.org](https://manual.gromacs.org/)
| ![PLUMED](https://img.shields.io/badge/PLUMED-2.7+-lightgrey) | Plugin for enhanced sampling algorithms | [plumed.org](https://www.plumed.org/) |
| ![Python](https://img.shields.io/badge/Python-3.8%2B-yellow?logo=python&logoColor=white) | Analysis & plotting | [python.org](https://www.python.org/) |

### 🐍 Python Dependencies
To run the analysis scripts, you need the following Python libraries. You can install them via `pip` or `conda`.

I recommend to manage your Python packages through virtual environment (ex: [Anaconda](https://www.anaconda.com/download))
```bash
numpy
pandas
matplotlib
pymbar
alchemlyb
pymol-open-source
```

*If you need any help, please contact me.*




*Created and maintained by DobiShredder*



