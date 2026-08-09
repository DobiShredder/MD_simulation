#!/usr/bin/env python3
"""Chignolin backbone dihedral feature를 t-SNE로 투영한다."""

from __future__ import annotations

from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import numpy as np
    import sklearn
    from sklearn.manifold import TSNE
    from sklearn.preprocessing import StandardScaler
except ModuleNotFoundError as error:
    raise SystemExit(
        "필요한 Python package가 없습니다. 다음을 실행하세요: "
        "conda install -n ambertools26 -c conda-forge 'scikit-learn>=1.5,<2'"
    ) from error


PERPLEXITY = 30.0
RANDOM_STATE = 20260809


def read_features(path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = np.loadtxt(path, comments="#", ndmin=2)
    if data.shape[1] < 3:
        raise ValueError("phi_psi.dat 형식을 확인하세요.")
    angles = np.deg2rad(data[:, 1:])
    features = np.column_stack((np.sin(angles), np.cos(angles)))
    return data[:, 0], StandardScaler().fit_transform(features)


def main() -> int:
    output_dir = Path(__file__).resolve().parent / "output"
    frames, features = read_features(output_dir / "phi_psi.dat")
    if len(frames) <= PERPLEXITY:
        raise ValueError(
            f"t-SNE는 perplexity보다 많은 frame이 필요합니다: "
            f"frames={len(frames)}, perplexity={PERPLEXITY:g}"
        )

    model = TSNE(
        n_components=2,
        perplexity=PERPLEXITY,
        learning_rate="auto",
        init="pca",
        max_iter=1000,
        metric="euclidean",
        random_state=RANDOM_STATE,
        n_jobs=1,
    )
    embedding = model.fit_transform(features)

    np.savetxt(
        output_dir / "embedding.tsv",
        np.column_stack((frames, embedding)),
        delimiter="\t",
        header="frame\ttSNE1\ttSNE2",
        comments="",
    )
    (output_dir / "metadata.tsv").write_text(
        "parameter\tvalue\n"
        f"scikit_learn_version\t{sklearn.__version__}\n"
        f"perplexity\t{PERPLEXITY:g}\n"
        f"random_state\t{RANDOM_STATE}\n"
        "scaling\tStandardScaler\n",
        encoding="utf-8",
    )

    figure, axis = plt.subplots(figsize=(7, 5.5))
    scatter = axis.scatter(embedding[:, 0], embedding[:, 1], c=frames, s=14)
    axis.set_xlabel("t-SNE 1")
    axis.set_ylabel("t-SNE 2")
    figure.colorbar(scatter, ax=axis, label="Frame")
    figure.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
