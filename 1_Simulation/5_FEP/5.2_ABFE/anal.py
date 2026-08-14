#!/usr/bin/env python3
"""Calculate the ABFE cycle and corrections with Amber FE-ToolKit."""

from __future__ import annotations

import csv
import importlib.util
import math
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent
WORK = Path(os.environ.get("WORK_DIR", ROOT / "work"))
TEMPERATURE_K = 300.0
BOOTSTRAP_SAMPLES = 20
GAS_CONSTANT = 0.00198720425864083
STANDARD_VOLUME_A3 = 1660.539


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise SystemExit(f"input not found: {path}")
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def require_program(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise SystemExit(
            f"{name} not found. Activate the AmberTools 26 environment."
        )
    return executable


def run_command(command: list[str], log_file: Path) -> None:
    with log_file.open("a", encoding="utf-8") as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        raise SystemExit(f"MBAR command failed. Check the log: {log_file}")


def extract_window(
    extractor: str,
    state: dict[str, str],
    data_directory: Path,
    log_file: Path,
) -> None:
    window_directory = Path(state["directory"])
    trajectory_lambda = float(state["lambda"])

    production_outputs = sorted(window_directory.glob("production.[0-9][0-9][0-9].out"))
    if not production_outputs:
        raise SystemExit(f"production output not found: {window_directory}")

    for mdout in production_outputs:
        completion_marker = mdout.with_name(f".{mdout.stem}.complete")
        if not completion_marker.is_file():
            raise SystemExit(
                "production completion marker not found: "
                f"{completion_marker}. Run run.sh to completion before analysis."
            )

    for mdout in production_outputs:
        segment = mdout.stem.rsplit(".", 1)[1]
        segment_directory = data_directory / f"segment_{state['window']}_{segment}"
        segment_directory.mkdir(parents=True)
        run_command(
            [extractor, "--odir", str(segment_directory), str(mdout)],
            log_file,
        )

        pattern = f"efep_{trajectory_lambda:.8f}_*.dat"
        extracted_files = sorted(segment_directory.glob(pattern))
        if not extracted_files:
            raise SystemExit(f"MBAR energy could not be extracted: {mdout}")

        for source in extracted_files:
            destination = data_directory / source.name
            with source.open(encoding="utf-8") as input_handle:
                with destination.open("a", encoding="utf-8") as output_handle:
                    output_handle.write(input_handle.read())


def choose_estimator(
    stage: str,
    lambdas: list[str],
    observed_files: set[str],
    log_file: Path,
) -> str:
    mbar_files = {
        f"efep_{sampled_lambda}_{evaluated_lambda}.dat"
        for sampled_lambda in lambdas
        for evaluated_lambda in lambdas
    }
    bar_files = set()
    for state_index in range(len(lambdas) - 1):
        first_lambda = lambdas[state_index]
        second_lambda = lambdas[state_index + 1]
        bar_files.update({
            f"efep_{first_lambda}_{first_lambda}.dat",
            f"efep_{first_lambda}_{second_lambda}.dat",
            f"efep_{second_lambda}_{first_lambda}.dat",
            f"efep_{second_lambda}_{second_lambda}.dat",
        })

    if mbar_files.issubset(observed_files):
        return "MBAR"
    if bar_files.issubset(observed_files):
        print(
            f"{stage}: full MBAR matrix is unavailable; "
            "using adjacent-state BAR."
        )
        return "BAR"

    missing_files = sorted(bar_files - observed_files)
    missing_preview = ", ".join(missing_files[:4])
    raise SystemExit(
        f"{stage} energy matrix cannot support adjacent-state BAR: "
        f"missing={len(missing_files)} ({missing_preview}). "
        f"Check {log_file}."
    )


def prepare_stage_data(
    extractor: str,
    stage: str,
    states: list[dict[str, str]],
    mbar_directory: Path,
) -> tuple[Path, list[str], str]:
    stage_states = [state for state in states if state["stage"] == stage]
    stage_states.sort(key=lambda state: float(state["lambda"]))
    data_directory = mbar_directory / "data" / stage
    data_directory.mkdir(parents=True)
    log_file = mbar_directory / "extract.log"

    for state in stage_states:
        extract_window(extractor, state, data_directory, log_file)

    lambdas = [f"{float(state['lambda']):.8f}" for state in stage_states]
    observed_files = {path.name for path in data_directory.glob("efep_*.dat")}
    estimator = choose_estimator(stage, lambdas, observed_files, log_file)
    return data_directory, lambdas, estimator


def add_trial(
    parent: ET.Element,
    name: str,
    data_directory: Path,
    lambdas: list[str],
    estimator: str,
) -> None:
    stage = ET.SubElement(parent, "stage", name=name)
    trial = ET.SubElement(stage, "trial", name="trial_1", mode=estimator)
    ET.SubElement(trial, "dir").text = str(data_directory.resolve())
    for lambda_value in lambdas:
        ET.SubElement(trial, "ene").text = lambda_value


def write_edge_xml(
    path: Path,
    stage_data: dict[str, tuple[Path, list[str], str]],
) -> None:
    edge = ET.Element("edge", name="jz4_decoupling")
    solvent = ET.SubElement(edge, "env", name="target")
    complex_environment = ET.SubElement(edge, "env", name="reference")

    add_trial(solvent, "restraint", *stage_data["restraint"])
    add_trial(solvent, "solvent_charge", *stage_data["solvent_charge"])
    add_trial(solvent, "solvent_vdw", *stage_data["solvent_vdw"])
    add_trial(complex_environment, "complex_charge", *stage_data["complex_charge"])
    add_trial(complex_environment, "complex_vdw", *stage_data["complex_vdw"])

    ET.indent(edge)
    ET.ElementTree(edge).write(path, encoding="unicode")


def load_report(path: Path) -> ModuleType:
    specification = importlib.util.spec_from_file_location("abfe_mbar_report", path)
    if specification is None or specification.loader is None:
        raise SystemExit(f"MBAR report could not be read: {path}")
    report = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(report)
    return report


def stage_results(edge: object) -> dict[str, tuple[float, float]]:
    results: dict[str, tuple[float, float]] = {}
    for environment in edge.GetEnvs():
        for stage in environment.stages:
            results[stage.name] = stage.GetValueAndError(edge.results.prod)
    return results


def stage_estimators(edge: object) -> dict[str, str]:
    estimators: dict[str, str] = {}
    for environment in edge.GetEnvs():
        for stage in environment.stages:
            estimators[stage.name] = stage.trials[0].GetMode()
    return estimators


def standard_state_correction(restraints: list[dict[str, str]]) -> float:
    references = {row["restraint"]: float(row["reference"]) for row in restraints}
    amber_forces = {
        row["restraint"]: float(row["force_constant"])
        for row in restraints
    }
    spring_constants = {
        restraint: 2.0 * force
        for restraint, force in amber_forces.items()
    }
    distance_ref = references["distance"]
    angle_a = math.radians(references["angle_a"])
    angle_b = math.radians(references["angle_b"])
    force_product = math.prod(spring_constants.values())
    thermal = 2.0 * math.pi * GAS_CONSTANT * TEMPERATURE_K
    ratio = (
        8.0 * math.pi**2 * STANDARD_VOLUME_A3 * math.sqrt(force_product)
        / (distance_ref**2 * math.sin(angle_a) * math.sin(angle_b) * thermal**3)
    )
    return -GAS_CONSTANT * TEMPERATURE_K * math.log(ratio)


def combine_binding_free_energy(
    contributions: dict[str, float],
    standard_state: float,
    finite_size: float,
) -> tuple[float, float]:
    raw_binding = (
        contributions["solvent_charge"]
        + contributions["solvent_vdw"]
        - contributions["complex_charge"]
        - contributions["complex_vdw"]
        + contributions["restraint"]
        - standard_state
    )
    return raw_binding, raw_binding + finite_size


def write_free_energy(edge: object, results: dict[str, tuple[float, float]]) -> None:
    contributions = {stage: value for stage, (value, _) in results.items()}
    restraints = read_tsv(WORK / "restraints.tsv")
    standard = standard_state_correction(restraints)
    finite_size = 0.0
    raw_binding, corrected_binding = combine_binding_free_energy(
        contributions,
        standard,
        finite_size,
    )
    _, cycle_error = edge.GetValueAndError(edge.results.prod)
    estimators = stage_estimators(edge)
    sampled_stages = (
        "restraint",
        "complex_charge",
        "complex_vdw",
        "solvent_charge",
        "solvent_vdw",
    )
    unique_estimators = set(estimators.values())
    if len(unique_estimators) == 1:
        cycle_estimator = f"{next(iter(unique_estimators))}+analytic"
    else:
        stage_modes = ";".join(
            f"{stage}={estimators[stage]}" for stage in sampled_stages
        )
        cycle_estimator = f"{stage_modes};analytic"

    with (WORK / "free_energy.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["quantity", "value_kcal_mol", "uncertainty_kcal_mol", "estimator"])
        for stage in sampled_stages:
            value, error = results[stage]
            writer.writerow([
                stage,
                f"{value:.8f}",
                f"{error:.8f}",
                estimators[stage],
            ])
        restraint_error = results["restraint"][1]
        writer.writerow([
            "bound_restraint_cycle_contribution",
            f"{contributions['restraint']:.8f}",
            f"{restraint_error:.8f}",
            estimators["restraint"],
        ])
        writer.writerow(["standard_state_correction", f"{standard:.8f}", "", "analytic"])
        writer.writerow(["leading_pme_net_charge_correction", f"{finite_size:.8f}", "", "analytic"])
        writer.writerow([
            "raw_standard_binding_delta_g",
            f"{raw_binding:.8f}",
            f"{cycle_error:.8f}",
            cycle_estimator,
        ])
        writer.writerow([
            "corrected_standard_binding_delta_g",
            f"{corrected_binding:.8f}",
            f"{cycle_error:.8f}",
            cycle_estimator,
        ])


def write_diagnostics(edge: object) -> None:
    diagnostics_path = WORK / "mbar_diagnostics.tsv"
    overlap_path = WORK / "overlap_matrix.tsv"

    with diagnostics_path.open("w", encoding="utf-8", newline="") as diagnostics_handle:
        diagnostics = csv.writer(diagnostics_handle, delimiter="\t")
        diagnostics.writerow([
            "stage", "lambda", "input_samples", "production_samples",
            "equilibration_start", "statistical_stride", "equilibrated",
        ])

        with overlap_path.open("w", encoding="utf-8", newline="") as overlap_handle:
            overlap = csv.writer(overlap_handle, delimiter="\t")
            overlap.writerow(["stage", "sampled_lambda", "evaluated_lambda", "overlap"])

            for environment in edge.GetEnvs():
                for stage in environment.stages:
                    trial = stage.trials[0]
                    for state_index, state_result in enumerate(trial.results):
                        diagnostics.writerow([
                            stage.name,
                            trial.ene[state_index],
                            state_result.osize,
                            state_result.psize,
                            state_result.pstart,
                            state_result.pstride,
                            str(state_result.isequil).lower(),
                        ])
                        for evaluated_index, value in enumerate(state_result.overlaps):
                            overlap.writerow([
                                stage.name,
                                trial.ene[state_index],
                                trial.ene[evaluated_index],
                                f"{float(value):.8f}",
                            ])


def main() -> None:
    extractor = require_program("edgembar-amber2dats.py")
    edgembar = require_program("edgembar")
    states = read_tsv(WORK / "states.tsv")

    mbar_directory = WORK / "mbar"
    if mbar_directory.exists():
        shutil.rmtree(mbar_directory)
    mbar_directory.mkdir(parents=True)

    stages = (
        "restraint",
        "complex_charge",
        "complex_vdw",
        "solvent_charge",
        "solvent_vdw",
    )
    data = {
        stage: prepare_stage_data(extractor, stage, states, mbar_directory)
        for stage in stages
    }
    xml_path = mbar_directory / "abfe.xml"
    report_path = mbar_directory / "abfe_report.py"
    write_edge_xml(xml_path, data)

    run_command(
        [
            edgembar,
            "--mode=AUTO",
            f"--temp={TEMPERATURE_K}",
            f"--nboot={BOOTSTRAP_SAMPLES}",
            f"--out={report_path}",
            str(xml_path),
        ],
        mbar_directory / "edgembar.log",
    )
    report = load_report(report_path)
    results = stage_results(report.edge)
    write_free_energy(report.edge, results)
    write_diagnostics(report.edge)
    run_command([sys.executable, str(report_path), "--html"], mbar_directory / "report.log")

    print(f"ABFE free-energy results: {WORK / 'free_energy.tsv'}")


if __name__ == "__main__":
    main()
