#!/usr/bin/env python3
"""Cluster backbone-dihedral PCA features with K-means."""

from __future__ import annotations

from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import numpy as np
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler
except ModuleNotFoundError as error:
    raise SystemExit("Install scikit-learn and matplotlib in the ambertools26 environment.") from error


CLUSTER_COUNT = 3
RANDOM_STATE = 20260809


def pca_features(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    data = np.loadtxt(path, comments="#", ndmin=2)
    angles = np.deg2rad(data[:, 1:])
    periodic = np.column_stack((np.sin(angles), np.cos(angles)))
    scaled = StandardScaler().fit_transform(periodic)
    projection = PCA(n_components=5).fit_transform(scaled)
    return data[:, 0], projection, StandardScaler().fit_transform(projection)


def representative_index(feature: np.ndarray, labels: np.ndarray, cluster: int) -> int:
    members = np.flatnonzero(labels == cluster)
    center = np.mean(feature[members], axis=0)
    distances = np.linalg.norm(feature[members] - center, axis=1)
    return int(members[np.argmin(distances)])


def main() -> int:
    output_dir = Path(__file__).resolve().parent / "output"
    frames, projection, feature = pca_features(output_dir / "phi_psi.dat")
    if len(frames) < 9:
        raise ValueError("K-means diagnostics require at least 9 frames.")

    model = KMeans(
        n_clusters=CLUSTER_COUNT,
        n_init=20,
        random_state=RANDOM_STATE,
    ).fit(feature)
    labels = model.labels_
    distances = np.min(model.transform(feature), axis=1)

    np.savetxt(
        output_dir / "pca_projection.tsv",
        np.column_stack((frames, projection)),
        delimiter="\t",
        header="frame\tPC1\tPC2\tPC3\tPC4\tPC5",
        comments="",
    )
    np.savetxt(
        output_dir / "cluster_labels.tsv",
        np.column_stack((frames, labels, distances)),
        delimiter="\t",
        header="frame\tcluster\tcentroid_distance",
        comments="",
    )

    summary = ["cluster\tframes\tpopulation\trepresentative_frame"]
    representatives = ["cluster\tframe"]
    for cluster in range(CLUSTER_COUNT):
        count = int(np.sum(labels == cluster))
        index = representative_index(feature, labels, cluster)
        summary.append(
            f"{cluster}\t{count}\t{count / len(frames):.8f}\t{frames[index]:g}"
        )
        representatives.append(f"{cluster}\t{frames[index]:g}")
    (output_dir / "cluster_summary.tsv").write_text("\n".join(summary) + "\n", encoding="utf-8")
    (output_dir / "representative_frames.tsv").write_text(
        "\n".join(representatives) + "\n", encoding="utf-8"
    )

    diagnostic = ["clusters\tsilhouette_score"]
    for cluster_count in range(2, 9):
        candidate = KMeans(
            n_clusters=cluster_count,
            n_init=20,
            random_state=RANDOM_STATE,
        ).fit_predict(feature)
        diagnostic.append(f"{cluster_count}\t{silhouette_score(feature, candidate):.8f}")
    (output_dir / "silhouette.tsv").write_text(
        "\n".join(diagnostic) + "\n", encoding="utf-8"
    )

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].scatter(projection[:, 0], projection[:, 1], c=labels, s=14, cmap="tab10")
    axes[0].set_xlabel("PC1")
    axes[0].set_ylabel("PC2")
    counts = np.bincount(labels, minlength=CLUSTER_COUNT)
    axes[1].bar(np.arange(CLUSTER_COUNT), counts / len(labels))
    axes[1].set_xlabel("Cluster")
    axes[1].set_ylabel("Population")
    figure.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
