#!/usr/bin/env python3
"""Backbone dihedral PCA feature를 HDBSCAN으로 clustering한다."""

from __future__ import annotations

from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import numpy as np
    import sklearn
    from sklearn.cluster import HDBSCAN
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
except (ImportError, ModuleNotFoundError) as error:
    raise SystemExit(
        "sklearn.cluster.HDBSCAN이 필요합니다. 다음을 실행하세요: "
        "conda install -n ambertools26 -c conda-forge 'scikit-learn>=1.5,<2'"
    ) from error


MIN_CLUSTER_SIZE = 50
MIN_SAMPLES = 10


def pca_features(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    data = np.loadtxt(path, comments="#", ndmin=2)
    angles = np.deg2rad(data[:, 1:])
    periodic = np.column_stack((np.sin(angles), np.cos(angles)))
    scaled = StandardScaler().fit_transform(periodic)
    projection = PCA(n_components=5).fit_transform(scaled)
    return data[:, 0], projection, StandardScaler().fit_transform(projection)


def representative_index(
    labels: np.ndarray, probabilities: np.ndarray, cluster: int
) -> int:
    members = np.flatnonzero(labels == cluster)
    return int(members[np.argmax(probabilities[members])])


def main() -> int:
    output_dir = Path(__file__).resolve().parent / "output"
    frames, projection, feature = pca_features(output_dir / "phi_psi.dat")
    if len(frames) < MIN_CLUSTER_SIZE:
        raise ValueError(f"HDBSCAN에는 최소 {MIN_CLUSTER_SIZE}개 frame이 필요합니다.")

    model = HDBSCAN(
        min_cluster_size=MIN_CLUSTER_SIZE,
        min_samples=MIN_SAMPLES,
        cluster_selection_method="eom",
        allow_single_cluster=False,
        copy=True,
    ).fit(feature)
    labels = model.labels_
    probabilities = model.probabilities_

    np.savetxt(
        output_dir / "pca_projection.tsv",
        np.column_stack((frames, projection)),
        delimiter="\t",
        header="frame\tPC1\tPC2\tPC3\tPC4\tPC5",
        comments="",
    )
    np.savetxt(
        output_dir / "cluster_labels.tsv",
        np.column_stack((frames, labels, probabilities)),
        delimiter="\t",
        header="frame\tcluster\tmembership_probability",
        comments="",
    )

    clusters = [int(value) for value in np.unique(labels) if value >= 0]
    summary = [
        "cluster\tframes\tpopulation\tmean_membership_probability\trepresentative_frame"
    ]
    representatives = ["cluster\tframe"]
    for cluster in clusters:
        selected = labels == cluster
        count = int(np.sum(selected))
        index = representative_index(labels, probabilities, cluster)
        summary.append(
            f"{cluster}\t{count}\t{count / len(frames):.8f}\t"
            f"{np.mean(probabilities[selected]):.8f}\t{frames[index]:g}"
        )
        representatives.append(f"{cluster}\t{frames[index]:g}")
    noise_count = int(np.sum(labels == -1))
    summary.append(
        f"-1\t{noise_count}\t{noise_count / len(frames):.8f}\t0.00000000\tNA"
    )
    (output_dir / "cluster_summary.tsv").write_text("\n".join(summary) + "\n", encoding="utf-8")
    (output_dir / "representative_frames.tsv").write_text(
        "\n".join(representatives) + "\n", encoding="utf-8"
    )
    (output_dir / "metadata.tsv").write_text(
        "parameter\tvalue\n"
        f"scikit_learn_version\t{sklearn.__version__}\n"
        f"min_cluster_size\t{MIN_CLUSTER_SIZE}\n"
        f"min_samples\t{MIN_SAMPLES}\n"
        "cluster_selection_method\teom\n",
        encoding="utf-8",
    )

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].scatter(projection[:, 0], projection[:, 1], c=labels, s=14, cmap="tab10")
    axes[0].set_xlabel("PC1")
    axes[0].set_ylabel("PC2")
    axes[1].hist(probabilities[labels >= 0], bins=20)
    axes[1].set_xlabel("Membership probability")
    axes[1].set_ylabel("Frames")
    figure.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
