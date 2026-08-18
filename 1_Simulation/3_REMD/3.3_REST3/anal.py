#!/usr/bin/env python3
"""Summarize REST3 exchanges and structural metrics by effective temperature."""

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


def parse_gromacs_exchange_line(
    line: str, state_count: int, event_index: int
) -> list[tuple[int, int, int]]:
    payload = line.split("Repl ex", 1)[1]
    replica_labels = list(re.finditer(r"\d+", payload))
    if len(replica_labels) != state_count:
        return []

    # GROMACS prints the current replica order. An "x" between two labels
    # marks an accepted exchange across that state boundary.
    accepted_boundaries = {
        boundary
        for boundary in range(1, state_count)
        if "x"
        in payload[
            replica_labels[boundary - 1].end() : replica_labels[boundary].start()
        ]
    }

    # The first exchange event attempts (0,1), (2,3), ...; the next event
    # attempts (1,2), (3,4), ... . The pattern then alternates.
    offset = event_index % 2
    return [
        (state_a, state_a + 1, int(state_a + 1 in accepted_boundaries))
        for state_a in range(offset, state_count - 1, 2)
    ]


def parse_exchanges(state_count: int) -> list[list[tuple[int, int, int]]]:
    events: list[list[tuple[int, int, int]]] = []
    logs = sorted((WORK / "000").glob("production.*.log"))
    event_index = 0

    for path in logs:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            explicit = EXPLICIT.search(line)
            if explicit:
                a = int(explicit.group("a"))
                b = int(explicit.group("b"))
                events.append([(a, b, int(explicit.group("ok")))])
                continue

            if "Repl ex" not in line:
                continue

            event = parse_gromacs_exchange_line(line, state_count, event_index)
            if event:
                events.append(event)
            event_index += 1

    if not events:
        raise SystemExit("GROMACS replica-exchange record not found.")

    return events


def write_exchange_outputs(
    events: list[list[tuple[int, int, int]]], states: list[dict[str, str]]
) -> None:
    totals: dict[tuple[int, int], list[int]] = defaultdict(lambda: [0, 0])
    labels = list(range(len(states)))
    visits = [[state] for state in labels]

    for event in events:
        for state_a, state_b, accepted in event:
            totals[(state_a, state_b)][0] += 1
            totals[(state_a, state_b)][1] += accepted

            if accepted:
                replica_a = labels.index(state_a)
                replica_b = labels.index(state_b)
                labels[replica_a], labels[replica_b] = (
                    labels[replica_b],
                    labels[replica_a],
                )

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
            ca_atoms = protein.select_atoms("name CA")

            if len(ca_atoms) < 2:
                raise SystemExit("Could not select the terminal protein CA atoms.")

            radii: list[float] = []
            distances: list[float] = []

            for _ in universe.trajectory:
                radii.append(float(protein.radius_of_gyration()))
                distances.append(
                    float(np.linalg.norm(ca_atoms.positions[0] - ca_atoms.positions[-1]))
                )

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
    events = parse_exchanges(len(states))
    write_exchange_outputs(events, states)
    structure_summary(states)
    print(f"REST3 Analysis results: {WORK}")


if __name__ == "__main__":
    main()
