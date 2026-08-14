#!/usr/bin/env python3
"""Summarize REST2 exchanges and structural metrics by effective temperature."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

import MDAnalysis as mda
import numpy as np

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "work"
EXPLICIT = re.compile(
    r"state_a=(?P<a>\d+)\s+state_b=(?P<b>\d+)\s+accepted=(?P<ok>[01])"
)


def read_states() -> list[dict[str, str]]:
    with (WORK / "states.tsv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def require_completed_segments() -> None:
    logs = sorted((WORK / "000").glob("production.[0-9][0-9][0-9].log"))
    if not logs:
        raise SystemExit(f"production log not found: {WORK / '000'}")
    for log in logs:
        segment = log.stem.rsplit(".", 1)[1]
        marker = WORK / f".production.{segment}.complete"
        if not marker.is_file():
            raise SystemExit(f"production completion marker not found: {marker}")


def parse_exchanges(state_count: int) -> list[tuple[int, int, int]]:
    records: list[tuple[int, int, int]] = []
    logs = sorted((WORK / "000").glob("production.*.log"))
    event_index = 0

    for path in logs:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            explicit = EXPLICIT.search(line)
            if explicit:
                a = int(explicit.group("a"))
                b = int(explicit.group("b"))
                records.append((a, b, int(explicit.group("ok"))))
                continue

            if "Repl ex" not in line:
                continue

            numbers = [int(value) for value in re.findall(r"\d+", line)]
            if len(numbers) < 2:
                continue

            accepted_pairs = [
                (int(left), int(right))
                for left, right in re.findall(r"\\b(\\d+)\\s+x\\s+(\\d+)\\b", line)
            ]
            if accepted_pairs:
                offset = min(accepted_pairs[0]) % 2
            else:
                offset = (event_index + 1) % 2
            for index in range(offset, state_count - 1, 2):
                left = str(index)
                right = str(index + 1)
                accepted = int(
                    re.search(rf"\b{left}\s+x\s+{right}\b", line) is not None
                )
                records.append((index, index + 1, accepted))
            event_index += 1

    if not records:
        raise SystemExit("GROMACS replica-exchange record not found.")

    return records


def write_exchange_outputs(
    records: list[tuple[int, int, int]], states: list[dict[str, str]]
) -> None:
    totals: dict[tuple[int, int], list[int]] = defaultdict(lambda: [0, 0])
    labels = list(range(len(states)))
    visits = [[state] for state in labels]

    for state_a, state_b, accepted in records:
        totals[(state_a, state_b)][0] += 1
        totals[(state_a, state_b)][1] += accepted

        if accepted:
            replica_a = labels.index(state_a)
            replica_b = labels.index(state_b)
            labels[replica_a], labels[replica_b] = labels[replica_b], labels[replica_a]

        for replica, state in enumerate(labels):
            visits[replica].append(state)

    with (WORK / "exchange_summary.tsv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["state_a", "state_b", "attempts", "accepted", "ratio"])
        for pair, (attempts, accepted) in sorted(totals.items()):
            writer.writerow([*pair, attempts, accepted, f"{accepted / attempts:.6f}"])

    with (WORK / "replica_visits.tsv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["replica", "min_state", "max_state", "round_trips"])
        for replica, history in enumerate(visits):
            endpoints = [value for value in history if value in {0, len(states) - 1}]
            round_trips = sum(
                left == len(states) - 1 and right == 0
                for left, right in zip(endpoints, endpoints[1:])
            )
            writer.writerow(
                [f"{replica:03d}", min(history), max(history), round_trips]
            )

    with (WORK / "state_occupancy.tsv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            ["replica", "state", "effective_temperature_K", "visits", "fraction"]
        )
        for replica, history in enumerate(visits):
            for state_index, state in enumerate(states):
                count = history.count(state_index)
                writer.writerow(
                    [
                        f"{replica:03d}",
                        state_index,
                        state["effective_temperature_K"],
                        count,
                        f"{count / len(history):.6f}",
                    ]
                )


def structure_summary(states: list[dict[str, str]]) -> None:
    output = WORK / "structure_by_temperature.tsv"

    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "state",
                "effective_temperature_K",
                "frames",
                "Rg_mean_A",
                "Rg_std_A",
                "terminal_distance_mean_A",
                "terminal_distance_std_A",
            ]
        )

        for state in states:
            replica = state["replica"]
            replica_dir = WORK / replica
            trajectories = sorted(replica_dir.glob("production.*.xtc"))
            if not trajectories:
                raise SystemExit(f"trajectory not found: {replica_dir}")

            universe = mda.Universe(
                str(replica_dir / "system.gro"),
                [str(path) for path in trajectories],
            )
            protein = universe.select_atoms("protein")
            first_ca = universe.select_atoms("protein and resid 1 and name CA")
            last_ca = universe.select_atoms("protein and resid 10 and name CA")

            if len(first_ca) != 1 or len(last_ca) != 1:
                raise SystemExit("Could not select exactly one CA atom from each of residues 1 and 10.")

            radii: list[float] = []
            distances: list[float] = []

            for _ in universe.trajectory:
                radii.append(float(protein.radius_of_gyration()))
                distances.append(float(np.linalg.norm(first_ca.positions[0] - last_ca.positions[0])))

            writer.writerow(
                [
                    replica,
                    state["effective_temperature_K"],
                    len(radii),
                    f"{np.mean(radii):.6f}",
                    f"{np.std(radii):.6f}",
                    f"{np.mean(distances):.6f}",
                    f"{np.std(distances):.6f}",
                ]
            )


def main() -> None:
    require_completed_segments()
    states = read_states()
    records = parse_exchanges(len(states))
    write_exchange_outputs(records, states)
    structure_summary(states)
    print(f"REST2 Analysis results: {WORK}")


if __name__ == "__main__":
    main()
