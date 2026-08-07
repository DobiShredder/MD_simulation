# Analysis tutorials / 분석 튜토리얼

## 한국어

Trajectory 처리와 기본 구조 계산에는 cpptraj를 사용합니다. 차원 축소,
clustering, 통계와 시각화는 Python으로 진행합니다. 1–6번은 아직 문서
skeleton이며, 7번에는 실행 가능한 US PMF 예제가 있습니다.

1. [Preprocessing](1_Preprocessing/): imaging, alignment, conversion
2. [Basic analysis](2_Basic/): RMSD, RMSF, Rg, distance, angle, dihedral
3. [Interactions](3_Interactions/): H-bond, contacts, SASA, secondary structure
4. [Dimensionality reduction](4_DimReduction/): PCA and t-SNE
5. [Clustering](5_Clustering/): K-means and DBSCAN
6. [Binding energy](6_Binding_Energy/): MM/GBSA and MM/PBSA
7. [Enhanced-sampling analysis](7_Enhanced_Sampling/): US PMF and overlap

각 analysis의 topology, trajectory, mask, frame 범위, stride, 단위와 output
column을 README에 기록합니다. Clustering에는 원래 feature 또는 PCA
projection을 사용합니다. t-SNE는 시각화 용도로만 사용합니다.

## English

cpptraj handles trajectory processing and core structural observables. Python
is used for dimensionality reduction, clustering, statistics, and plots.
Categories 1–6 are documentation skeletons; the US PMF example in category 7
is runnable.

Each README records topology, trajectory, masks, frame range, stride, units,
and output columns. Clustering uses original features or PCA projections;
t-SNE is reserved for visualization.
