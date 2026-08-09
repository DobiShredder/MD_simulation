# PCA / 주성분 분석

## 한국어

Chignolin residue 2–9의 φ/ψ를 sine/cosine feature로 바꾼 뒤 표준화하고 PCA를
적용합니다. PCA는 원래 feature의 분산을 가장 많이 설명하는 직교 축을 찾는
선형 방법입니다.

이 directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`run.sh`는 cpptraj으로 `output/phi_psi.dat`을 만듭니다. `anal.py`는
`features.tsv`, `projection.tsv`와 `explained_variance.tsv`를 기록하고 scree
plot 및 PC1–PC2 projection을 표시합니다.

다른 system은 `run.sh` 상단의 topology와 trajectory, cpptraj의 residue 범위를
함께 수정합니다. Feature scaling 여부와 atom/residue selection이 바뀌면 서로
다른 PCA basis가 되므로 projection을 직접 비교하지 않습니다.

## English

Cpptraj calculates residue 2–9 φ/ψ angles. Python converts them to standardized
sine/cosine features and performs PCA. Numeric outputs contain the scaled
features, projections, and individual/cumulative explained variance. PCA bases
from different feature definitions are not directly comparable.
