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

1–5번은 Chignolin, 6번은 trypsin–benzamidine conventional MD output을
사용합니다. 7번은 대응하는 enhanced-sampling simulation output을 읽습니다.
각 leaf는 다른 analysis 결과에 의존하지 않습니다. Command는 실행할 tutorial
directory로 이동한 뒤 입력합니다.

```bash
./run.sh
python3 anal.py
```

위 순서는 1–6번의 기본 형식입니다. Conversion tutorial은 `./run.sh`만
실행하고, 7번의 command와 입력 경로는 각 README를 따릅니다.

먼저 대응하는 conventional MD를 실행합니다. 1–6번의 각 `run.sh`는 해당
simulation의 `work/system.parm7`과 `work/production.nc`를 직접 읽습니다. 다른
system을 사용할 때는 `run.sh` 상단의 `topology`와 `trajectory`를 수정합니다.
`anal.py`는 figure를 화면에 표시하고 image file을 자동 저장하지 않습니다.

## English

cpptraj handles trajectory processing and core structural observables. Python
is used for dimensionality reduction, clustering, statistics, and plots.
All categories contain runnable examples. Categories 1–5 use Chignolin,
category 6 uses trypsin–benzamidine conventional-MD output, and category 7
reads the matching enhanced-sampling simulation. Each leaf runs independently.

Run the Chignolin conventional-MD tutorial first. Each `run.sh` reads its
`work/system.parm7` and `work/production.nc` directly. To analyze another
system, edit the `topology` and `trajectory` variables at the top of that
script. This two-command pattern applies to categories 1–6 except Conversion,
which only runs `./run.sh`; category 7 documents its own command and input
path. Every leaf is self-contained. Plotting scripts display figures with
`plt.show()` and do not save image files automatically.
