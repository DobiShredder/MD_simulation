#!/usr/bin/env python3
"""Cluster backbone-dihedral PCA features with HDBSCAN."""

from __future__ import annotations

import argparse
from pathlib import Path

from result_generation import input_generation

try:
    import matplotlib.pyplot as plt
    import numpy as np
    import sklearn
    from sklearn.cluster import HDBSCAN
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
except (ImportError, ModuleNotFoundError) as error:
    raise SystemExit(
        "sklearn.cluster.HDBSCAN is required. Run: "
        "conda install -n ambertools26 -c conda-forge 'scikit-learn>=1.5,<2'"
    ) from error


# Number of PCA components used as clustering features.
PCA_COMPONENTS = 5
# The 1 ns example writes 100 frames (ntwx=5000). A cluster needs at least
# 10 frames (100 ps of sampling); scale both values with the number of frames.
MIN_CLUSTER_SIZE = 10
MIN_SAMPLES = 5
# "eom" (excess of mass) or "leaf"; see the scikit-learn HDBSCAN documentation.
CLUSTER_SELECTION_METHOD = "eom"

# Used only with --save-figure DIR.
FIGURE_NAME = "hdbscan.png"
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
    if MIN_CLUSTER_SIZE > frame_count or MIN_SAMPLES > frame_count:
        raise SystemExit(
            f"Error: MIN_CLUSTER_SIZE ({MIN_CLUSTER_SIZE}) and MIN_SAMPLES ({MIN_SAMPLES}) "
            f"must not exceed the frame count ({frame_count})."
        )


def representative_index(
    labels: np.ndarray, probabilities: np.ndarray, cluster: int
) -> int:
    members = np.flatnonzero(labels == cluster)
    return int(members[np.argmax(probabilities[members])])


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
        print(f"Running: HDBSCAN analysis; input directory: {output_dir}")
        frames, scaled = periodic_features(output_dir / "phi_psi.dat")
        print(f"Frames: {len(frames)}")
        check_frame_count(*scaled.shape)
        projection, feature = pca_features(scaled)

        model = HDBSCAN(
            min_cluster_size=MIN_CLUSTER_SIZE,
            min_samples=MIN_SAMPLES,
            cluster_selection_method=CLUSTER_SELECTION_METHOD,
            allow_single_cluster=False,
            copy=True,
        ).fit(feature)
        labels = model.labels_
        probabilities = model.probabilities_

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
            f"cluster_selection_method\t{CLUSTER_SELECTION_METHOD}\n",
            encoding="utf-8",
        )

    output_dir = completed_output_dir
    # Tables are published before the figure window opens.
    print(f"Completed: HDBSCAN analysis; results: {output_dir}")

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].scatter(projection[:, 0], projection[:, 1], c=labels, s=14, cmap="tab10")
    axes[0].set_xlabel("PC1")
    axes[0].set_ylabel("PC2")
    axes[1].hist(probabilities[labels >= 0], bins=20)
    axes[1].set_xlabel("Membership probability")
    axes[1].set_ylabel("Frames")
    figure.tight_layout()
    if figure_dir is not None:
        save_figure(figure, figure_dir)
    print("Displaying HDBSCAN analysis figure.")
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
