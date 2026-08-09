#!/usr/bin/env python3
"""Chignolin backbone dihedral feature에 PCA를 적용한다."""

from __future__ import annotations

from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import numpy as np
    import sklearn
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
except ModuleNotFoundError as error:
    raise SystemExit(
        "필요한 Python package가 없습니다. ambertools26 환경에 "
        "scikit-learn과 matplotlib을 설치하세요."
    ) from error


def read_dihedrals(path: Path) -> tuple[np.ndarray, list[str], np.ndarray]:
    with path.open(encoding="utf-8") as handle:
        header = handle.readline().lstrip("#").split()
    data = np.loadtxt(path, comments="#", ndmin=2)
    if data.shape[1] < 3 or len(header) != data.shape[1]:
        raise ValueError("phi_psi.dat 형식을 확인하세요.")
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


def main() -> int:
    output_dir = Path(__file__).resolve().parent / "output"
    frames, angle_names, raw_angles = read_dihedrals(output_dir / "phi_psi.dat")
    feature_names, features = periodic_features(angle_names, raw_angles)
    scaled_features = StandardScaler().fit_transform(features)

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
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
