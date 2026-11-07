#!/usr/bin/env python3
"""Apply PCA to Chignolin backbone-dihedral features."""

from __future__ import annotations

import argparse
from pathlib import Path

from result_generation import input_generation

try:
    import matplotlib.pyplot as plt
    import numpy as np
    import sklearn
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
except ModuleNotFoundError as error:
    raise SystemExit(
        "A required Python package is missing. "
        "Install scikit-learn and matplotlib in the ambertools26 environment."
    ) from error


# Used only with --save-figure DIR.
FIGURE_NAME = "pca.png"
FIGURE_DPI = 150


def read_dihedrals(path: Path) -> tuple[np.ndarray, list[str], np.ndarray]:
    with path.open(encoding="utf-8") as handle:
        header = handle.readline().lstrip("#").split()
    data = np.loadtxt(path, comments="#", ndmin=2)
    if data.shape[1] < 3 or len(header) != data.shape[1]:
        raise ValueError("Check the format of phi_psi.dat.")
    return data[:, 0], header[1:], data[:, 1:]


def periodic_features(
    angle_names: list[str], angles_degree: np.ndarray
) -> tuple[list[str], np.ndarray]:
    angles_radian = np.deg2rad(angles_degree)
    names: list[str] = []
    columns: list[np.ndarray] = []
    for column, name in enumerate(angle_names):
        names.extend((f"sin_{name}", f"cos_{name}"))
        columns.extend((np.sin(angles_radian[:, column]), np.cos(angles_radian[:, column])))
    return names, np.column_stack(columns)


def write_table(path: Path, header: list[str], data: np.ndarray) -> None:
    np.savetxt(path, data, delimiter="\t", header="\t".join(header), comments="")


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
        print(f"Running: PCA analysis; input directory: {output_dir}")
        frames, angle_names, raw_angles = read_dihedrals(output_dir / "phi_psi.dat")
        feature_names, features = periodic_features(angle_names, raw_angles)
        frame_count = len(frames)
        print(f"Frames: {frame_count}")
        if frame_count < 2:
            raise SystemExit(f"Error: PCA needs at least 2 frames; phi_psi.dat has {frame_count}.")
        scaled_features = StandardScaler().fit_transform(features)

        # PCA() keeps min(frames, features) components.
        model = PCA()
        projection = model.fit_transform(scaled_features)
        component_names = [f"PC{index}" for index in range(1, projection.shape[1] + 1)]

        write_table(
            output_dir / "features.tsv",
            ["frame", *feature_names],
            np.column_stack((frames, scaled_features)),
        )
        write_table(
            output_dir / "projection.tsv",
            ["frame", *component_names],
            np.column_stack((frames, projection)),
        )

        component_index = np.arange(1, len(model.explained_variance_ratio_) + 1)
        variance = np.column_stack(
            (
                component_index,
                model.explained_variance_ratio_,
                np.cumsum(model.explained_variance_ratio_),
            )
        )
        write_table(
            output_dir / "explained_variance.tsv",
            ["component", "explained_variance_ratio", "cumulative_ratio"],
            variance,
        )

    output_dir = completed_output_dir
    # Tables are published before the figure window opens.
    print(f"Completed: PCA analysis; results: {output_dir}")

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].plot(component_index, variance[:, 1], marker="o", label="Individual")
    axes[0].plot(component_index, variance[:, 2], marker="o", label="Cumulative")
    axes[0].set_xlabel("Principal component")
    axes[0].set_ylabel("Explained variance ratio")
    axes[0].legend()

    scatter = axes[1].scatter(projection[:, 0], projection[:, 1], c=frames, s=14)
    axes[1].set_xlabel("PC1")
    axes[1].set_ylabel("PC2")
    figure.colorbar(scatter, ax=axes[1], label="Frame")
    figure.suptitle(f"scikit-learn {sklearn.__version__}")
    figure.tight_layout()
    if figure_dir is not None:
        save_figure(figure, figure_dir)
    print("Displaying PCA analysis figure.")
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
