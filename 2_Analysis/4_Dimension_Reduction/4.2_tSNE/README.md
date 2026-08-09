# t-SNE

## 한국어

t-SNE는 고차원에서 가까운 frame이 2차원에서도 이웃이 되도록 확률 분포를
맞추는 nonlinear embedding입니다. Chignolin backbone dihedral feature를
표준화해 사용합니다.

```bash
./run.sh
python3 anal.py
```

기본값은 `perplexity=30`, `learning_rate="auto"`, `init="pca"`,
`max_iter=1000`, `random_state=20260809`입니다. `embedding.tsv`와
`metadata.tsv`를 만들고 frame 순서로 색칠한 plot을 표시합니다.

Perplexity는 유효 이웃 수와 관련된 parameter이며 frame 수보다 작아야 합니다.
Script는 frame이 부족해도 값을 자동으로 낮추지 않습니다. Seed와 perplexity가
다른 embedding의 회전, 모양과 cluster 간 거리를 정량 비교하지 않습니다.

## English

Scikit-learn t-SNE embeds standardized periodic backbone-dihedral features.
The fixed perplexity is 30 with PCA initialization and a recorded random seed.
The script refuses undersized data rather than silently changing perplexity.
Embedding distance and density are not free energies or populations.
