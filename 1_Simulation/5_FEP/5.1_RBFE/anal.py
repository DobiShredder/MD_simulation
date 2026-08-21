#!/usr/bin/env python3
"""Calculate RBFE free energies and overlap with Amber FE-ToolKit."""

from __future__ import annotations

import csv
import importlib.util
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import ModuleType


WORK = Path("work")
TEMPERATURE_K = 300.0
BOOTSTRAP_SAMPLES = 20


def read_states() -> list[dict[str, str]]:
    states_file = WORK / "states.tsv"
    if not states_file.is_file():
        raise SystemExit(f"states.tsv not found: {states_file}")
    with states_file.open(encoding="utf-8") as handle:
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

    mdout = window_directory / "production.out"
    if not mdout.is_file():
        raise SystemExit(f"production output not found: {mdout}")

    window_data = data_directory / f"window_{state['window']}"
    window_data.mkdir(parents=True)
    run_command([extractor, "--odir", str(window_data), str(mdout)], log_file)

    pattern = f"efep_{trajectory_lambda:.8f}_*.dat"
    extracted_files = sorted(window_data.glob(pattern))
    if not extracted_files:
        raise SystemExit(f"MBAR energy could not be extracted: {mdout}")

    for source in extracted_files:
        destination = data_directory / source.name
        with source.open(encoding="utf-8") as input_handle:
            with destination.open("a", encoding="utf-8") as output_handle:
                output_handle.write(input_handle.read())


def prepare_environment_data(
    extractor: str,
    environment_name: str,
    states: list[dict[str, str]],
    mbar_directory: Path,
) -> tuple[Path, list[str], str]:
    environment_states = [
        state for state in states if state["environment"] == environment_name
    ]
    environment_states.sort(key=lambda state: float(state["lambda"]))
    data_directory = mbar_directory / "data" / environment_name
    data_directory.mkdir(parents=True)
    log_file = mbar_directory / "extract.log"

    for state in environment_states:
        extract_window(extractor, state, data_directory, log_file)

    lambdas = [f"{float(state['lambda']):.8f}" for state in environment_states]
    observed_files = {path.name for path in data_directory.glob("efep_*.dat")}
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
        estimator = "MBAR"
    elif bar_files.issubset(observed_files):
        estimator = "BAR"
        print(
            f"{environment_name}: full MBAR matrix is unavailable; "
            "using adjacent-state BAR."
        )
    else:
        missing_files = sorted(bar_files - observed_files)
        missing_preview = ", ".join(missing_files[:4])
        raise SystemExit(
            f"{environment_name} energy matrix cannot support adjacent-state BAR: "
            f"missing={len(missing_files)} ({missing_preview}). "
            f"Check {log_file}."
        )
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
    complex_data: tuple[Path, list[str], str],
    solvent_data: tuple[Path, list[str], str],
) -> None:
    edge = ET.Element("edge", name="benzene_to_toluene")
    target = ET.SubElement(edge, "env", name="target")
    reference = ET.SubElement(edge, "env", name="reference")
    add_trial(target, "complex", *complex_data)
    add_trial(reference, "solvent", *solvent_data)
    ET.indent(edge)
    ET.ElementTree(edge).write(path, encoding="unicode")


def load_report(path: Path) -> ModuleType:
    specification = importlib.util.spec_from_file_location("rbfe_mbar_report", path)
    if specification is None or specification.loader is None:
        raise SystemExit(f"MBAR report could not be read: {path}")
    report = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(report)
    return report


def environment_result(edge: object, name: str) -> tuple[float, float]:
    for environment in edge.GetEnvs():
        if environment.stages[0].name == name:
            return environment.GetValueAndError(edge.results.prod)
    raise SystemExit(f"Environment {name} not found in FE-ToolKit report.")


def environment_estimator(edge: object, name: str) -> str:
    for environment in edge.GetEnvs():
        if environment.stages[0].name == name:
            return environment.stages[0].trials[0].GetMode()
    raise SystemExit(f"Environment {name} not found in FE-ToolKit report.")


def write_free_energy(edge: object) -> None:
    complex_value, complex_error = environment_result(edge, "complex")
    solvent_value, solvent_error = environment_result(edge, "solvent")
    relative_value, relative_error = edge.GetValueAndError(edge.results.prod)
    complex_estimator = environment_estimator(edge, "complex")
    solvent_estimator = environment_estimator(edge, "solvent")
    if complex_estimator == solvent_estimator:
        relative_estimator = complex_estimator
    else:
        relative_estimator = (
            f"complex={complex_estimator};solvent={solvent_estimator}"
        )

    with (WORK / "free_energy.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["quantity", "value_kcal_mol", "uncertainty_kcal_mol", "estimator"])
        writer.writerow([
            "complex_delta_g",
            f"{complex_value:.8f}",
            f"{complex_error:.8f}",
            complex_estimator,
        ])
        writer.writerow([
            "solvent_delta_g",
            f"{solvent_value:.8f}",
            f"{solvent_error:.8f}",
            solvent_estimator,
        ])
        writer.writerow([
            "relative_binding_delta_delta_g",
            f"{relative_value:.8f}",
            f"{relative_error:.8f}",
            relative_estimator,
        ])


def write_diagnostics(edge: object) -> None:
    diagnostics_path = WORK / "mbar_diagnostics.tsv"
    overlap_path = WORK / "overlap_matrix.tsv"

    with diagnostics_path.open("w", encoding="utf-8", newline="") as diagnostics_handle:
        diagnostics = csv.writer(diagnostics_handle, delimiter="\t")
        diagnostics.writerow([
            "environment", "lambda", "input_samples", "production_samples",
            "equilibration_start", "statistical_stride", "equilibrated",
        ])

        with overlap_path.open("w", encoding="utf-8", newline="") as overlap_handle:
            overlap = csv.writer(overlap_handle, delimiter="\t")
            overlap.writerow(["environment", "sampled_lambda", "evaluated_lambda", "overlap"])

            for environment in edge.GetEnvs():
                trial = environment.stages[0].trials[0]
                environment_name = environment.stages[0].name
                for state_index, state_result in enumerate(trial.results):
                    diagnostics.writerow([
                        environment_name,
                        trial.ene[state_index],
                        state_result.osize,
                        state_result.psize,
                        state_result.pstart,
                        state_result.pstride,
                        str(state_result.isequil).lower(),
                    ])
                    for evaluated_index, value in enumerate(state_result.overlaps):
                        overlap.writerow([
                            environment_name,
                            trial.ene[state_index],
                            trial.ene[evaluated_index],
                            f"{float(value):.8f}",
                        ])


def main() -> None:
    extractor = require_program("edgembar-amber2dats.py")
    edgembar = require_program("edgembar")
    states = read_states()

    mbar_directory = WORK / "mbar"
    if mbar_directory.exists():
        shutil.rmtree(mbar_directory)
    mbar_directory.mkdir(parents=True)

    complex_data = prepare_environment_data(extractor, "complex", states, mbar_directory)
    solvent_data = prepare_environment_data(extractor, "solvent", states, mbar_directory)
    xml_path = mbar_directory / "rbfe.xml"
    report_path = mbar_directory / "rbfe_report.py"
    write_edge_xml(xml_path, complex_data, solvent_data)

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
    write_free_energy(report.edge)
    write_diagnostics(report.edge)
    run_command([sys.executable, str(report_path), "--html"], mbar_directory / "report.log")

    print(f"RBFE free-energy results: {WORK / 'free_energy.tsv'}")


if __name__ == "__main__":
    main()
