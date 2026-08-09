#!/usr/bin/env python3
"""Backbone dihedral PCA feature를 DBSCAN으로 clustering한다."""

from __future__ import annotations

from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import numpy as np
    from sklearn.cluster import DBSCAN
    from sklearn.decomposition import PCA
    from sklearn.neighbors import NearestNeighbors
    from sklearn.preprocessing import StandardScaler
except ModuleNotFoundError as error:
    raise SystemExit("ambertools26 환경에 scikit-learn과 matplotlib을 설치하세요.") from error


EPS = 1.2
MIN_SAMPLES = 10


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
    return int(members[np.argmin(np.linalg.norm(feature[members] - center, axis=1))])


def main() -> int:
    output_dir = Path(__file__).resolve().parent / "output"
    frames, projection, feature = pca_features(output_dir / "phi_psi.dat")
    if len(frames) < MIN_SAMPLES:
        raise ValueError(f"DBSCAN에는 최소 {MIN_SAMPLES}개 frame이 필요합니다.")

    labels = DBSCAN(eps=EPS, min_samples=MIN_SAMPLES).fit_predict(feature)
    neighbors = NearestNeighbors(n_neighbors=MIN_SAMPLES).fit(feature)
    distances, _ = neighbors.kneighbors(feature)
    k_distance = np.sort(distances[:, -1])

    np.savetxt(
        output_dir / "pca_projection.tsv",
        np.column_stack((frames, projection)),
        delimiter="\t",
        header="frame\tPC1\tPC2\tPC3\tPC4\tPC5",
        comments="",
    )
    np.savetxt(
        output_dir / "cluster_labels.tsv",
        np.column_stack((frames, labels)),
        delimiter="\t",
        header="frame\tcluster",
        comments="",
    )
    np.savetxt(
        output_dir / "k_distance.tsv",
        np.column_stack((np.arange(1, len(frames) + 1), k_distance)),
        delimiter="\t",
        header="sorted_index\tk_distance",
        comments="",
    )

    clusters = [int(value) for value in np.unique(labels) if value >= 0]
    summary = ["cluster\tframes\tpopulation\trepresentative_frame"]
    representatives = ["cluster\tframe"]
    for cluster in clusters:
        count = int(np.sum(labels == cluster))
        index = representative_index(feature, labels, cluster)
        summary.append(
            f"{cluster}\t{count}\t{count / len(frames):.8f}\t{frames[index]:g}"
        )
        representatives.append(f"{cluster}\t{frames[index]:g}")
    noise_count = int(np.sum(labels == -1))
    summary.append(f"-1\t{noise_count}\t{noise_count / len(frames):.8f}\tNA")
    (output_dir / "cluster_summary.tsv").write_text("\n".join(summary) + "\n", encoding="utf-8")
    (output_dir / "representative_frames.tsv").write_text(
        "\n".join(representatives) + "\n", encoding="utf-8"
    )

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].scatter(projection[:, 0], projection[:, 1], c=labels, s=14, cmap="tab10")
    axes[0].set_xlabel("PC1")
    axes[0].set_ylabel("PC2")
    axes[1].plot(np.arange(1, len(frames) + 1), k_distance)
    axes[1].axhline(EPS, color="tab:red", linestyle="--", label=f"eps={EPS}")
    axes[1].set_xlabel("Sorted frame")
    axes[1].set_ylabel(f"{MIN_SAMPLES}-neighbor distance")
    axes[1].legend()
    figure.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
