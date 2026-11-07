#!/usr/bin/env python3
"""Cluster backbone-dihedral PCA features with K-means."""

from __future__ import annotations

import argparse
from pathlib import Path

from result_generation import input_generation

try:
    import matplotlib.pyplot as plt
    import numpy as np
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler
except ModuleNotFoundError as error:
    raise SystemExit("Install scikit-learn and matplotlib in the ambertools26 environment.") from error


# Defaults assume the 100-frame example trajectory.
# Number of PCA components used as clustering features.
PCA_COMPONENTS = 5
CLUSTER_COUNT = 3
# Independent K-means initializations; the lowest-inertia result is kept.
KMEANS_N_INIT = 20
# silhouette.tsv scans k = 2 to SILHOUETTE_MAX_CLUSTERS (needs more frames than k).
SILHOUETTE_MAX_CLUSTERS = 8
RANDOM_STATE = 20260809

# Used only with --save-figure DIR.
FIGURE_NAME = "kmeans.png"
FIGURE_DPI = 150


def periodic_features(path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = np.loadtxt(path, comments="#", ndmin=2)
    angles = np.deg2rad(data[:, 1:])
    periodic = np.column_stack((np.sin(angles), np.cos(angles)))
    return data[:, 0], StandardScaler().fit_transform(periodic)


def pca_features(scaled: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    projection = PCA(n_components=PCA_COMPONENTS).fit_transform(scaled)
    # Re-standardize so that every PC has unit variance in the clustering space.
    return projection, StandardScaler().fit_transform(projection)


def check_frame_count(frame_count: int, feature_count: int) -> None:
    if PCA_COMPONENTS > min(frame_count, feature_count):
        raise SystemExit(
            f"Error: PCA_COMPONENTS ({PCA_COMPONENTS}) must not exceed the frame count "
            f"({frame_count}) or the feature count ({feature_count})."
        )
    if CLUSTER_COUNT > frame_count:
        raise SystemExit(
            f"Error: CLUSTER_COUNT ({CLUSTER_COUNT}) must not exceed the frame count ({frame_count})."
        )
    if SILHOUETTE_MAX_CLUSTERS >= frame_count:
        raise SystemExit(
            f"Error: SILHOUETTE_MAX_CLUSTERS ({SILHOUETTE_MAX_CLUSTERS}) must be smaller "
            f"than the frame count ({frame_count})."
        )


def representative_index(feature: np.ndarray, labels: np.ndarray, cluster: int) -> int:
    members = np.flatnonzero(labels == cluster)
    center = np.mean(feature[members], axis=0)
    distances = np.linalg.norm(feature[members] - center, axis=1)
    return int(members[np.argmin(distances)])


def save_figure(figure: plt.Figure, figure_dir: Path) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)
    figure_path = figure_dir / FIGURE_NAME
    figure.savefig(figure_path, dpi=FIGURE_DPI)
    print(f"Saved figure: {figure_path}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--save-figure",
        metavar="DIR",
        type=Path,
        help="also save the figure as PNG in DIR (outside output/); "
        "by default the figure is only displayed",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    output_dir = Path(__file__).resolve().parent / "output"
    figure_dir = args.save_figure
    if figure_dir is not None and figure_dir.resolve().is_relative_to(output_dir):
        # Extra files in output/ would invalidate its recorded generation hashes.
        raise SystemExit(f"Error: --save-figure DIR must be outside {output_dir}")
    from writer_guard import protect_python_entry
    protect_python_entry("output", writes=(output_dir,))
    completed_output_dir = output_dir
    with input_generation(output_dir) as output_dir:
        print(f"Running: KMeans analysis; input directory: {output_dir}")
        frames, scaled = periodic_features(output_dir / "phi_psi.dat")
        print(f"Frames: {len(frames)}")
        check_frame_count(*scaled.shape)
        projection, feature = pca_features(scaled)

        model = KMeans(
            n_clusters=CLUSTER_COUNT,
            n_init=KMEANS_N_INIT,
            random_state=RANDOM_STATE,
        ).fit(feature)
        labels = model.labels_
        distances = np.min(model.transform(feature), axis=1)

        pc_names = "\t".join(f"PC{index}" for index in range(1, PCA_COMPONENTS + 1))
        np.savetxt(
            output_dir / "pca_projection.tsv",
            np.column_stack((frames, projection)),
            delimiter="\t",
            header=f"frame\t{pc_names}",
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
        for cluster_count in range(2, SILHOUETTE_MAX_CLUSTERS + 1):
            candidate = KMeans(
                n_clusters=cluster_count,
                n_init=KMEANS_N_INIT,
                random_state=RANDOM_STATE,
            ).fit_predict(feature)
            diagnostic.append(f"{cluster_count}\t{silhouette_score(feature, candidate):.8f}")
        (output_dir / "silhouette.tsv").write_text(
            "\n".join(diagnostic) + "\n", encoding="utf-8"
        )

    output_dir = completed_output_dir
    # Tables are published before the figure window opens.
    print(f"Completed: KMeans analysis; results: {output_dir}")

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].scatter(projection[:, 0], projection[:, 1], c=labels, s=14, cmap="tab10")
    axes[0].set_xlabel("PC1")
    axes[0].set_ylabel("PC2")
    counts = np.bincount(labels, minlength=CLUSTER_COUNT)
    axes[1].bar(np.arange(CLUSTER_COUNT), counts / len(labels))
    axes[1].set_xlabel("Cluster")
    axes[1].set_ylabel("Population")
    figure.tight_layout()
    if figure_dir is not None:
        save_figure(figure, figure_dir)
    print("Displaying KMeans analysis figure.")
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
