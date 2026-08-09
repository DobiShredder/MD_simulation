# K-means clustering

## 한국어

K-means는 cluster 내부의 centroid distance 제곱합을 줄이도록 frame을 나눕니다.
구형이고 크기가 비슷한 cluster를 선호하며 cluster 수를 미리 정해야 합니다.

```bash
./run.sh
python3 anal.py
```

기본값은 `n_clusters=3`, `n_init=20`, `random_state=20260809`입니다. k=2–8의
silhouette score를 `silhouette.tsv`에 기록합니다. 선택한 세 cluster의 label,
population과 centroid에 가까운 representative frame은 `cluster_labels.tsv`,
`cluster_summary.tsv`, `representative_frames.tsv`에 기록합니다.

Silhouette maximum만으로 cluster 수를 확정하지 않습니다. 시간 순서와 구조를
확인하고 필요하면 `CLUSTER_COUNT`를 수정합니다.

## English

K-means partitions five-PC features using three clusters and 20 initializations.
Silhouette scores for k=2–8 are diagnostics rather than an automatic model
choice. The representative frame is nearest to each cluster center.
