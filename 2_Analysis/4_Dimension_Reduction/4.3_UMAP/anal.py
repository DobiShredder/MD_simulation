#!/usr/bin/env python3
"""Project Chignolin backbone-dihedral features with UMAP."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

numba_cache = Path(tempfile.gettempdir()) / "md-tutorial-numba-cache"
numba_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("NUMBA_CACHE_DIR", str(numba_cache))

try:
    import matplotlib.pyplot as plt
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    import umap
except (ModuleNotFoundError, RuntimeError) as error:
    raise SystemExit(
        "UMAP dependency is unavailable. Run: "
        "conda install -n ambertools26 -c conda-forge 'umap-learn>=0.5.7,<0.6'"
    ) from error


N_NEIGHBORS = 15
MIN_DIST = 0.1
RANDOM_STATE = 20260809


def read_features(path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = np.loadtxt(path, comments="#", ndmin=2)
    if data.shape[1] < 3:
        raise ValueError("Check the format of phi_psi.dat.")
    angles = np.deg2rad(data[:, 1:])
    features = np.column_stack((np.sin(angles), np.cos(angles)))
    return data[:, 0], StandardScaler().fit_transform(features)


def main() -> int:
    output_dir = Path(__file__).resolve().parent / "output"
    frames, features = read_features(output_dir / "phi_psi.dat")
    if len(frames) <= N_NEIGHBORS:
        raise ValueError(
            f"UMAP requires more frames than the n_neighbors value: "
            f"frames={len(frames)}, n_neighbors={N_NEIGHBORS}"
        )

    model = umap.UMAP(
        n_neighbors=N_NEIGHBORS,
        min_dist=MIN_DIST,
        n_components=2,
        metric="euclidean",
        random_state=RANDOM_STATE,
        n_jobs=1,
    )
    embedding = model.fit_transform(features)

    np.savetxt(
        output_dir / "embedding.tsv",
        np.column_stack((frames, embedding)),
        delimiter="\t",
        header="frame\tUMAP1\tUMAP2",
        comments="",
    )
    (output_dir / "metadata.tsv").write_text(
        "parameter\tvalue\n"
        f"umap_version\t{umap.__version__}\n"
        f"n_neighbors\t{N_NEIGHBORS}\n"
        f"min_dist\t{MIN_DIST}\n"
        f"random_state\t{RANDOM_STATE}\n"
        "scaling\tStandardScaler\n",
        encoding="utf-8",
    )

    figure, axis = plt.subplots(figsize=(7, 5.5))
    scatter = axis.scatter(embedding[:, 0], embedding[:, 1], c=frames, s=14)
    axis.set_xlabel("UMAP 1")
    axis.set_ylabel("UMAP 2")
    figure.colorbar(scatter, ax=axis, label="Frame")
    figure.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
