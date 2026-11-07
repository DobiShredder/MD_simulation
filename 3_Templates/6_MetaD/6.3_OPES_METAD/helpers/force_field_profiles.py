#!/usr/bin/env python3
"""Validated protein force-field and water-model compatibility profiles."""

from __future__ import annotations

from collections.abc import Collection


ForceFieldPair = tuple[str, str]

FORCE_FIELD_PROFILES: dict[ForceFieldPair, dict[str, object]] = {
    ("ff99SB-ILDN", "TIP3P"): {
        "protein_leaprc": "oldff/leaprc.ff99SBildn",
        "water_leaprc": "leaprc.water.tip3p",
        "water_box": "TIP3PBOX",
        "water_residue": "WAT",
        "water_atom_types": ("OW", "HW", "HW"),
        "ion_parameter_files": (
            "frcmod.ions1lm_126_tip3p",
            "frcmod.ionsjc_tip3p",
            "frcmod.ions234lm_126_tip3p",
        ),
    },
    ("ff14SB", "TIP3P"): {
        "protein_leaprc": "leaprc.protein.ff14SB",
        "water_leaprc": "leaprc.water.tip3p",
        "water_box": "TIP3PBOX",
        "water_residue": "WAT",
        "water_atom_types": ("OW", "HW", "HW"),
        "ion_parameter_files": (
            "frcmod.ions1lm_126_tip3p",
            "frcmod.ionsjc_tip3p",
            "frcmod.ions234lm_126_tip3p",
        ),
    },
    ("ff19SB", "OPC"): {
        "protein_leaprc": "leaprc.protein.ff19SB",
        "water_leaprc": "leaprc.water.opc",
        "water_box": "OPCBOX",
        "water_residue": "WAT",
        "water_atom_types": ("OW", "HW", "HW", "EP"),
        "ion_parameter_files": ("frcmod.ionslm_126_opc",),
    },
}


def resolve_force_field_profile(
    protein_force_field: str,
    water_model: str,
    supported_pairs: Collection[ForceFieldPair] | None = None,
) -> dict[str, object]:
    """Return one validated compatibility profile or raise a config error."""

    pair = (protein_force_field, water_model.upper())
    allowed_pairs = set(FORCE_FIELD_PROFILES if supported_pairs is None else supported_pairs)
    if pair not in allowed_pairs or pair not in FORCE_FIELD_PROFILES:
        allowed = ", ".join(
            f"{force_field} + {water}"
            for force_field, water in sorted(allowed_pairs)
        )
        expected_waters = sorted(
            water
            for force_field, water in allowed_pairs
            if force_field == protein_force_field
        )
        if len(expected_waters) == 1:
            reason = (
                f"protein_force_field={protein_force_field} requires "
                f"water_model={expected_waters[0]}"
            )
        else:
            reason = (
                f"unsupported pair protein_force_field={protein_force_field}, "
                f"water_model={water_model}"
            )
        raise ValueError(f"{reason}; supported pairs: {allowed}")

    return FORCE_FIELD_PROFILES[pair]
