#!/usr/bin/env python3
"""Project Chignolin backbone-dihedral features with t-SNE."""

from __future__ import annotations

import argparse
from pathlib import Path

from result_generation import input_generation

try:
    import matplotlib.pyplot as plt
    import numpy as np
    import sklearn
    from sklearn.manifold import TSNE
    from sklearn.preprocessing import StandardScaler
except ModuleNotFoundError as error:
    raise SystemExit(
        "Required Python package is missing. Run: "
        "conda install -n ambertools26 -c conda-forge 'scikit-learn>=1.5,<2'"
    ) from error


# Defaults assume the 100-frame example trajectory.
# Perplexity (effective neighbor count) must be smaller than the frame count.
PERPLEXITY = 30.0
MAX_ITERATIONS = 1000
RANDOM_STATE = 20260809

# Used only with --save-figure DIR.
FIGURE_NAME = "tsne.png"
FIGURE_DPI = 150


def read_features(path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = np.loadtxt(path, comments="#", ndmin=2)
    if data.shape[1] < 3:
        raise ValueError("Check the format of phi_psi.dat.")
    angles = np.deg2rad(data[:, 1:])
    features = np.column_stack((np.sin(angles), np.cos(angles)))
    return data[:, 0], StandardScaler().fit_transform(features)


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
        print(f"Running: tSNE analysis; input directory: {output_dir}")
        frames, features = read_features(output_dir / "phi_psi.dat")
        frame_count = len(frames)
        print(f"Frames: {frame_count}")
        if frame_count <= PERPLEXITY:
            raise SystemExit(
                f"Error: t-SNE PERPLEXITY ({PERPLEXITY:g}) must be smaller than "
                f"the frame count ({frame_count}); lower PERPLEXITY in anal.py."
            )

        model = TSNE(
            n_components=2,
            perplexity=PERPLEXITY,
            learning_rate="auto",
            init="pca",
            max_iter=MAX_ITERATIONS,
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

    output_dir = completed_output_dir
    # Tables are published before the figure window opens.
    print(f"Completed: tSNE analysis; results: {output_dir}")

    figure, axis = plt.subplots(figsize=(7, 5.5))
    scatter = axis.scatter(embedding[:, 0], embedding[:, 1], c=frames, s=14)
    axis.set_xlabel("t-SNE 1")
    axis.set_ylabel("t-SNE 2")
    figure.colorbar(scatter, ax=axis, label="Frame")
    figure.tight_layout()
    if figure_dir is not None:
        save_figure(figure, figure_dir)
    print("Displaying tSNE analysis figure.")
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
