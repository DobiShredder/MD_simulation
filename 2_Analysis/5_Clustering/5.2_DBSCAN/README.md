# DBSCAN clustering

## 한국어

DBSCAN은 `eps` 안에 `min_samples` 이상의 이웃이 있는 영역을 연결하고 희박한
frame을 noise로 분류합니다. Cluster 수를 미리 정하지 않지만 하나의 density
threshold를 사용합니다.

```bash
./run.sh
python3 anal.py
```

기본값은 `eps=1.2`, `min_samples=10`이며 noise label은 `-1`입니다.
`k_distance.tsv`와 plot으로 cutoff sensitivity를 확인합니다. Cluster가 없는
경우도 parameter 또는 sampling에 대한 결과이므로 label과 noise fraction을
그대로 기록합니다.

## English

DBSCAN connects dense regions using `eps=1.2` and `min_samples=10`; sparse
frames retain the noise label `-1`. The sorted k-neighbor distance is written
for sensitivity checks. A no-cluster result is preserved rather than hidden.
