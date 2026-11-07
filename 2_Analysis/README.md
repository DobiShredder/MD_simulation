# Analysis tutorials / 분석 튜토리얼

## 한국어

Trajectory 처리와 기본 구조 계산에는 cpptraj를 사용합니다. 통계 처리와
plotting, dimension reduction 및 clustering에는 Python을 사용합니다.
모든 category에 실행 가능한 예제가 있습니다.

1. [Preprocessing](1_Preprocessing/): imaging, alignment, conversion
2. [Basic analysis](2_Basic/): RMSD, RMSF, Rg, distance, angle, dihedral
3. [Interactions](3_Interactions/): H-bond, contacts, SASA, secondary structure
4. [Dimensionality reduction](4_Dimension_Reduction/): PCA, t-SNE, UMAP
5. [Clustering](5_Clustering/): K-means, DBSCAN, HDBSCAN, GMM
6. [Binding energy](6_Binding_Energy/): MM/GBSA and MM/PBSA
7. [Enhanced-sampling analysis](7_Enhanced_Sampling/): US, GaMD and GaREUS reweighting

먼저 대응하는 simulation을 실행합니다.

| Category | 필요한 simulation output |
| --- | --- |
| 1–5 | [Chignolin conventional MD](../1_Simulation/1_MD/1.1_Soluble_Protein/README.md)의 `work/system.parm7`, `work/production.nc` |
| 6 | [T4 lysozyme–JZ4 conventional MD](../1_Simulation/1_MD/1.2_Protein_Ligand/README.md)의 `work/system.parm7`, `work/production.nc` |
| 7 | 각 README에 적힌 US, GaMD 또는 GaREUS simulation output |

### 준비

AmberTools 26이 설치된 environment를 활성화하고 Python package를 설치합니다.
아래 예시는 [루트 README](../README.md)의 설치 절차로 만든 `ambertools26`
environment를 사용합니다.

```bash
conda activate ambertools26
conda install -c conda-forge \
    numpy \
    matplotlib \
    "scikit-learn>=1.5,<2" \
    "umap-learn>=0.5.7,<0.6" \
    "pymbar>=4,<5"
```

| Category | Program | Python package |
| --- | --- | --- |
| 1 Preprocessing | cpptraj | numpy, matplotlib(Conversion은 cpptraj만 사용) |
| 2 Basic, 3 Interactions | cpptraj | numpy, matplotlib |
| 4 Dimension reduction | cpptraj | numpy, matplotlib, scikit-learn(PCA, t-SNE), umap-learn(UMAP) |
| 5 Clustering | cpptraj | numpy, matplotlib, scikit-learn(K-means, DBSCAN, HDBSCAN, GMM) |
| 6 Binding energy | ante-MMPBSA.py, MMPBSA.py | numpy, matplotlib |
| 7 Enhanced sampling | cpptraj(GaMD) | numpy, matplotlib(US, GaREUS), pymbar(GaREUS) |

HDBSCAN은 scikit-learn의 `sklearn.cluster.HDBSCAN`을 사용하므로 별도
`hdbscan` package가 필요하지 않습니다.

### 실행

각 leaf는 다른 analysis 결과에 의존하지 않습니다. Command는 실행할 tutorial
directory로 이동한 뒤 입력합니다.

```bash
./run.sh
python3 anal.py
```

위 순서는 1–6번의 기본 형식입니다. Conversion tutorial은 `./run.sh`만
실행하고, 7번의 command와 입력 경로는 각 README를 따릅니다. `anal.py`는
figure를 화면에 표시하고 image file을 자동 저장하지 않습니다. PNG가 필요하면
`python3 anal.py --save-figure DIR`로 `output/` 밖의 DIR에 저장합니다. 결과
TSV는 figure 창을 열기 전에 기록되고, `anal.py`는 읽은 frame 수를 출력합니다.
Frame 수에 맞지 않는 parameter(t-SNE perplexity, UMAP `n_neighbors`, cluster 수
등)는 계산 전에 멈춥니다. 4–5번 기본값은 100-frame 예제 기준이므로 긴
trajectory에서는 조정합니다. MM/GBSA·MM/PBSA는 모든 frame을 계산하며, 범위는
각 `inputs/mmpbsa.in`에서 제한합니다.

### 다른 system 분석

다른 system을 분석할 때는 수정 위치가 나뉘어 있습니다.

- Simulation 경로: `run.sh` 상단의 `simulation_dir`, `topology`, `trajectory`
- Atom mask, cutoff와 cpptraj option: `inputs/cpptraj.in`
- MM/GBSA·MM/PBSA: `inputs/mmpbsa.in`과 `run.sh`의 `ligand_mask`
- Dimension reduction과 clustering parameter: `anal.py` 상단의 상수

### Segment로 나뉜 trajectory

1–6번 `run.sh`는 cpptraj `-y`로 trajectory 하나만 읽습니다. `3_Templates`처럼
production이 `work/001/production.nc`, `work/002/production.nc`로 나뉘어 있으면
먼저 하나로 합칩니다. 아래 command는 template leaf directory에서 실행합니다.

```bash
cpptraj -p work/system.parm7 <<'EOF'
trajin work/001/production.nc
trajin work/002/production.nc
trajout work/production_joined.nc netcdf
run
EOF
```

`trajin`은 segment 순서대로 나열합니다. 첫 segment가 root의
`work/production.nc`이면 그 file을 맨 앞에 둡니다. 그다음 analysis `run.sh`의
`simulation_dir`을 template leaf 경로로, `trajectory`를
`"$simulation_dir/work/production_joined.nc"`로 바꿉니다. Output의 frame 번호는
합친 trajectory 기준입니다. 7번의 input 형식은 각 README를 따릅니다.

결과 게시, 실패 log(`output.failed/`), 동시 실행 보호는
[GUIDE.md 부록](../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

cpptraj handles trajectory processing and core structural observables. Python
is used for dimensionality reduction, clustering, statistics, and plots.
All categories contain runnable examples.

Run the matching simulation first.

| Category | Required simulation output |
| --- | --- |
| 1–5 | `work/system.parm7` and `work/production.nc` from [Chignolin conventional MD](../1_Simulation/1_MD/1.1_Soluble_Protein/README.md) |
| 6 | `work/system.parm7` and `work/production.nc` from [T4 lysozyme–JZ4 conventional MD](../1_Simulation/1_MD/1.2_Protein_Ligand/README.md) |
| 7 | The US, GaMD, or GaREUS output named in each README |

### Preparation

Activate an environment with AmberTools 26 and install the Python packages.
The example uses the `ambertools26` environment from the
[root README](../README.md) installation steps.

```bash
conda activate ambertools26
conda install -c conda-forge \
    numpy \
    matplotlib \
    "scikit-learn>=1.5,<2" \
    "umap-learn>=0.5.7,<0.6" \
    "pymbar>=4,<5"
```

| Category | Program | Python packages |
| --- | --- | --- |
| 1 Preprocessing | cpptraj | numpy, matplotlib (Conversion uses cpptraj only) |
| 2 Basic, 3 Interactions | cpptraj | numpy, matplotlib |
| 4 Dimensionality reduction | cpptraj | numpy, matplotlib, scikit-learn (PCA, t-SNE), umap-learn (UMAP) |
| 5 Clustering | cpptraj | numpy, matplotlib, scikit-learn (K-means, DBSCAN, HDBSCAN, GMM) |
| 6 Binding energy | ante-MMPBSA.py, MMPBSA.py | numpy, matplotlib |
| 7 Enhanced sampling | cpptraj (GaMD) | numpy, matplotlib (US, GaREUS), pymbar (GaREUS) |

HDBSCAN uses scikit-learn's `sklearn.cluster.HDBSCAN`; the separate `hdbscan`
package is not needed.

### Running

Every leaf runs independently of other analyses. Run `./run.sh` and then
`python3 anal.py` from the tutorial directory. This two-command pattern applies
to categories 1–6 except Conversion, which only runs `./run.sh`; category 7
documents its own command and input path. Plotting scripts display figures with
`plt.show()` and do not save image files automatically; add
`--save-figure DIR` to also write PNG files to a directory outside `output/`.
Result TSV files are written before the figure window opens, and `anal.py`
prints the number of frames read.
Parameters that do not fit the frame count (t-SNE perplexity, UMAP
`n_neighbors`, cluster counts, ...) stop the script before fitting. The
category 4–5 defaults assume the 100-frame example; adjust them for longer
trajectories. MM/GBSA and MM/PBSA analyse every frame; restrict the range in
each `inputs/mmpbsa.in`.

### Another system

To analyze another system, edit:

- Simulation paths: `simulation_dir`, `topology`, and `trajectory` at the top
  of `run.sh`
- Atom masks, cutoffs, and cpptraj options: `inputs/cpptraj.in`
- MM/GBSA and MM/PBSA: `inputs/mmpbsa.in` and `ligand_mask` in `run.sh`
- Dimensionality-reduction and clustering parameters: constants at the top of
  `anal.py`

### Segmented trajectories

The category 1–6 `run.sh` scripts read a single trajectory with cpptraj `-y`.
When production is split into segments such as `work/001/production.nc` and
`work/002/production.nc` (as in `3_Templates`), join them first. Run this from
the template leaf directory:

```bash
cpptraj -p work/system.parm7 <<'EOF'
trajin work/001/production.nc
trajin work/002/production.nc
trajout work/production_joined.nc netcdf
run
EOF
```

List `trajin` lines in segment order; if the first segment is the root
`work/production.nc`, put it first. Then set `simulation_dir` in the analysis
`run.sh` to the template leaf and `trajectory` to
`"$simulation_dir/work/production_joined.nc"`. Frame numbers in the outputs
refer to the joined trajectory. Category 7 inputs follow each README.

Result publication, failure logs (`output.failed/`) and concurrent-run
protection are described in [GUIDE.md appendix](../GUIDE.md#4-appendix-run-state-and-recovery).
