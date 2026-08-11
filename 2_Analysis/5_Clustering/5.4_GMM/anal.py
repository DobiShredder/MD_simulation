#!/usr/bin/env python3
"""Cluster backbone-dihedral PCA features with a Gaussian mixture model."""

from __future__ import annotations

from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import numpy as np
    from sklearn.decomposition import PCA
    from sklearn.mixture import GaussianMixture
    from sklearn.preprocessing import StandardScaler
except ModuleNotFoundError as error:
    raise SystemExit("Install scikit-learn and matplotlib in the ambertools26 environment.") from error


COMPONENT_COUNT = 3
RANDOM_STATE = 20260809


def pca_features(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    data = np.loadtxt(path, comments="#", ndmin=2)
    angles = np.deg2rad(data[:, 1:])
    periodic = np.column_stack((np.sin(angles), np.cos(angles)))
    scaled = StandardScaler().fit_transform(periodic)
    projection = PCA(n_components=5).fit_transform(scaled)
    return data[:, 0], projection, StandardScaler().fit_transform(projection)


def new_model(component_count: int) -> GaussianMixture:
    return GaussianMixture(
        n_components=component_count,
        covariance_type="full",
        n_init=10,
        reg_covar=1.0e-6,
        random_state=RANDOM_STATE,
    )


def main() -> int:
    output_dir = Path(__file__).resolve().parent / "output"
    frames, projection, feature = pca_features(output_dir / "phi_psi.dat")
    if len(frames) < 9:
        raise ValueError("GMM diagnostics require at least 9 frames.")

    model = new_model(COMPONENT_COUNT).fit(feature)
    probability = model.predict_proba(feature)
    labels = np.argmax(probability, axis=1)
    maximum_probability = np.max(probability, axis=1)

    np.savetxt(
        output_dir / "pca_projection.tsv",
        np.column_stack((frames, projection)),
        delimiter="\t",
        header="frame\tPC1\tPC2\tPC3\tPC4\tPC5",
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
    for component_count in range(1, 9):
        candidate = new_model(component_count).fit(feature)
        diagnostic.append(
            f"{component_count}\t{candidate.aic(feature):.8f}\t{candidate.bic(feature):.8f}"
        )
    (output_dir / "model_selection.tsv").write_text(
        "\n".join(diagnostic) + "\n", encoding="utf-8"
    )

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].scatter(projection[:, 0], projection[:, 1], c=labels, s=14, cmap="tab10")
    axes[0].set_xlabel("PC1")
    axes[0].set_ylabel("PC2")
    axes[1].hist(maximum_probability, bins=20)
    axes[1].set_xlabel("Maximum posterior probability")
    axes[1].set_ylabel("Frames")
    figure.tight_layout()
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
