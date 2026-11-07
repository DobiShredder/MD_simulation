#!/usr/bin/env python3
"""Cluster backbone-dihedral PCA features with a Gaussian mixture model."""

from __future__ import annotations

import argparse
from pathlib import Path

from result_generation import input_generation

try:
    import matplotlib.pyplot as plt
    import numpy as np
    from sklearn.decomposition import PCA
    from sklearn.mixture import GaussianMixture
    from sklearn.preprocessing import StandardScaler
except ModuleNotFoundError as error:
    raise SystemExit("Install scikit-learn and matplotlib in the ambertools26 environment.") from error


# Defaults assume the 100-frame example trajectory.
# Number of PCA components used as clustering features.
PCA_COMPONENTS = 5
COMPONENT_COUNT = 3
# "full" fits one unrestricted covariance matrix per Gaussian component.
COVARIANCE_TYPE = "full"
# Independent EM initializations; the best likelihood is kept.
GMM_N_INIT = 10
# Added to covariance diagonals (standardized PC units squared) for stability.
REG_COVAR = 1.0e-6
# model_selection.tsv scans 1 to MODEL_SELECTION_MAX_COMPONENTS components.
MODEL_SELECTION_MAX_COMPONENTS = 8
RANDOM_STATE = 20260809

# Used only with --save-figure DIR.
FIGURE_NAME = "gmm.png"
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
    if max(COMPONENT_COUNT, MODEL_SELECTION_MAX_COMPONENTS) > frame_count:
        raise SystemExit(
            f"Error: COMPONENT_COUNT ({COMPONENT_COUNT}) and MODEL_SELECTION_MAX_COMPONENTS "
            f"({MODEL_SELECTION_MAX_COMPONENTS}) must not exceed the frame count ({frame_count})."
        )


def new_model(component_count: int) -> GaussianMixture:
    return GaussianMixture(
        n_components=component_count,
        covariance_type=COVARIANCE_TYPE,
        n_init=GMM_N_INIT,
        reg_covar=REG_COVAR,
        random_state=RANDOM_STATE,
    )


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
        print(f"Running: GMM analysis; input directory: {output_dir}")
        frames, scaled = periodic_features(output_dir / "phi_psi.dat")
        print(f"Frames: {len(frames)}")
        check_frame_count(*scaled.shape)
        projection, feature = pca_features(scaled)

        model = new_model(COMPONENT_COUNT).fit(feature)
        probability = model.predict_proba(feature)
        labels = np.argmax(probability, axis=1)
        maximum_probability = np.max(probability, axis=1)

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
            np.column_stack((frames, labels, maximum_probability)),
            delimiter="\t",
            header="frame\tcluster\tposterior_probability",
            comments="",
        )

        summary = ["cluster\tframes\tpopulation\tmean_probability\trepresentative_frame"]
        representatives = ["cluster\tframe"]
        for cluster in range(COMPONENT_COUNT):
            members = np.flatnonzero(labels == cluster)
            if len(members) == 0:
                summary.append(f"{cluster}\t0\t0.00000000\tNA\tNA")
                continue
            representative = int(members[np.argmax(probability[members, cluster])])
            summary.append(
                f"{cluster}\t{len(members)}\t{len(members) / len(frames):.8f}\t"
                f"{np.mean(probability[members, cluster]):.8f}\t{frames[representative]:g}"
            )
            representatives.append(f"{cluster}\t{frames[representative]:g}")
        (output_dir / "cluster_summary.tsv").write_text("\n".join(summary) + "\n", encoding="utf-8")
        (output_dir / "representative_frames.tsv").write_text(
            "\n".join(representatives) + "\n", encoding="utf-8"
        )

        diagnostic = ["components\tAIC\tBIC"]
        for component_count in range(1, MODEL_SELECTION_MAX_COMPONENTS + 1):
            candidate = new_model(component_count).fit(feature)
            diagnostic.append(
                f"{component_count}\t{candidate.aic(feature):.8f}\t{candidate.bic(feature):.8f}"
            )
        (output_dir / "model_selection.tsv").write_text(
            "\n".join(diagnostic) + "\n", encoding="utf-8"
        )

    output_dir = completed_output_dir
    # Tables are published before the figure window opens.
    print(f"Completed: GMM analysis; results: {output_dir}")

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].scatter(projection[:, 0], projection[:, 1], c=labels, s=14, cmap="tab10")
    axes[0].set_xlabel("PC1")
    axes[0].set_ylabel("PC2")
    axes[1].hist(maximum_probability, bins=20)
    axes[1].set_xlabel("Maximum posterior probability")
    axes[1].set_ylabel("Frames")
    figure.tight_layout()
    if figure_dir is not None:
        save_figure(figure, figure_dir)
    print("Displaying GMM analysis figure.")
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
