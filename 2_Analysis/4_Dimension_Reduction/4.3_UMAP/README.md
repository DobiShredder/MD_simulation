# UMAP

## 한국어

UMAP은 이웃 graph를 만든 뒤 저차원에서 그 연결 관계를 보존하는 nonlinear
embedding입니다. 입력은 표준화한 Chignolin backbone dihedral feature입니다.

```bash
./run.sh
python3 anal.py
```

기본값은 `n_neighbors=15`, `min_dist=0.1`, `metric="euclidean"`,
`random_state=20260809`입니다. `embedding.tsv`와 `metadata.tsv`를 생성합니다.
UMAP은 Numba cache를 system temporary directory에 만들며 repository에는 cache를
남기지 않습니다.

`n_neighbors`는 local/global structure의 균형에, `min_dist`는 저차원에서
point가 모일 수 있는 정도에 영향을 줍니다. Parameter가 다른 embedding의
거리와 밀도를 정량 비교하지 않습니다.

## English

UMAP builds a neighbor graph from standardized periodic dihedral features and
embeds it in two dimensions. The tutorial records UMAP parameters and version.
Its Numba cache is placed under the system temporary directory, not the
repository. Embedding geometry is not a thermodynamic observable.
