# Analysis tutorials / 분석 튜토리얼

## 한국어

Trajectory 처리와 기본 구조 계산에는 cpptraj를 사용합니다. 통계 처리와
plotting, dimension reduction 및 clustering에는 Python을 사용합니다.
1–3번과 7번은 실행 가능한 예제이며 나머지는 아직 문서 skeleton입니다.

1. [Preprocessing](1_Preprocessing/): imaging, alignment, conversion
2. [Basic analysis](2_Basic/): RMSD, RMSF, Rg, distance, angle, dihedral
3. [Interactions](3_Interactions/): H-bond, contacts, SASA, secondary structure
4. [Dimensionality reduction](4_Dimension_Reduction/): PCA and t-SNE
5. [Clustering](5_Clustering/): K-means and DBSCAN
6. [Binding energy](6_Binding_Energy/): MM/GBSA and MM/PBSA
7. [Enhanced-sampling analysis](7_Enhanced_Sampling/): US PMF and GaMD reweighting

1–3번 tutorial은 Chignolin conventional MD의 topology와 trajectory를
기본 input으로 사용합니다. 각 leaf는 다른 analysis 결과에 의존하지 않습니다.

```bash
./run.sh [--dry-run] TOPOLOGY TRAJECTORY [TRAJECTORY ...]
python3 anal.py [--output OUTPUT_DIR]
```

`OUTPUT_DIR`, `START_FRAME`, `STOP_FRAME`, `STRIDE`, `FRAME_INTERVAL_PS`와
`CPPTRAJ`을 environment variable로 바꿀 수 있습니다. `FRAME_INTERVAL_PS`는
원본 trajectory의 frame 간격이며 기본값은 10 ps입니다. `anal.py`는 figure를
화면에 표시하고 image file을 자동 저장하지 않습니다.

## English

cpptraj handles trajectory processing and core structural observables. Python
is used for dimensionality reduction, clustering, statistics, and plots.
Categories 1–3 and 7 contain runnable examples. The remaining categories are
currently documentation skeletons. Examples in categories 1–3 use the
Chignolin conventional-MD topology and trajectory by default, and each leaf
runs independently.

The common interface accepts one topology and one or more trajectories.
`OUTPUT_DIR`, frame limits, stride, source frame interval, and the cpptraj
executable can be overridden with environment variables. Plotting scripts
display figures with `plt.show()` and do not save image files automatically.
