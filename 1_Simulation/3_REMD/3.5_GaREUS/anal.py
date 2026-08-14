#!/usr/bin/env python3
"""Summarize GaREUS exchanges and restraint sampling as TSV."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "work"
EXPLICIT = re.compile(
    r"state_a=(?P<a>\d+)\s+state_b=(?P<b>\d+)\s+accepted=(?P<ok>[01])"
)


def read_states() -> list[dict[str, str]]:
    path = WORK / "states.tsv"
    if not path.is_file():
        raise SystemExit(f"window table not found: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def require_completed_segments() -> None:
    logs = sorted(WORK.glob("exchange.[0-9][0-9][0-9].log"))
    if not logs:
        raise SystemExit(f"exchange log not found: {WORK}")
    for log in logs:
        segment = log.stem.rsplit(".", 1)[1]
        marker = WORK / f".production.{segment}.complete"
        if not marker.is_file():
            raise SystemExit(f"production completion marker not found: {marker}")


def parse_exchanges(state_count: int) -> list[tuple[int, int, int]]:
    records: list[tuple[int, int, int]] = []

    for path in sorted(WORK.glob("exchange.*.log")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = EXPLICIT.search(line)
            if match:
                records.append(
                    (
                        int(match.group("a")),
                        int(match.group("b")),
                        int(match.group("ok")),
                    )
                )
                continue

            fields = line.split()
            if len(fields) < 8 or not fields[0].isdigit():
                continue

            try:
                replica = int(fields[0])
                neighbor = int(fields[1])
                accepted = int(float(fields[-2]) > 0.0)
            except ValueError:
                continue

            if 0 <= replica < state_count and 0 <= neighbor < state_count:
                records.append(
                    (min(replica, neighbor), max(replica, neighbor), accepted)
                )

    if not records:
        raise SystemExit("AMBER replica-exchange record not found.")

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

    with (WORK / "window_occupancy.tsv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["replica", "state", "window_center_A", "visits", "fraction"])
        for replica, history in enumerate(visits):
            for state_index, state in enumerate(states):
                count = history.count(state_index)
                writer.writerow(
                    [
                        f"{replica:03d}",
                        state_index,
                        state["window_center_A"],
                        count,
                        f"{count / len(history):.6f}",
                    ]
                )


def read_distances(replica_dir: Path) -> list[float]:
    values: list[float] = []

    for path in sorted(replica_dir.glob("restraint.production.*.dat")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "@")):
                continue
            try:
                values.append(float(stripped.split()[-1]))
            except ValueError:
                continue

    return values


def write_restraint_sampling(states: list[dict[str, str]]) -> None:
    output = WORK / "restraint_sampling.tsv"

    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "state",
                "window_center_A",
                "samples",
                "distance_mean_A",
                "distance_std_A",
                "distance_min_A",
                "distance_max_A",
            ]
        )

        for state in states:
            values = read_distances(WORK / state["replica"])
            if not values:
                raise SystemExit(
                    f"restraint DUMPAVE not found: replica {state['replica']}"
                )

            writer.writerow(
                [
                    state["replica"],
                    state["window_center_A"],
                    len(values),
                    f"{np.mean(values):.6f}",
                    f"{np.std(values):.6f}",
                    f"{min(values):.6f}",
                    f"{max(values):.6f}",
                ]
            )



def write_boost_range(states: list[dict[str, str]]) -> None:
    output = WORK / "boost_potential.tsv"

    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            ["state", "window_center_A", "samples", "boost_min_kcal_mol", "boost_max_kcal_mol"]
        )

        for state in states:
            replica_dir = WORK / state["replica"]
            values: list[float] = []

            for path in sorted(replica_dir.glob("gamd.production.*.log")):
                for line in path.read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines():
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue

                    try:
                        values.append(float(stripped.split()[-1]))
                    except ValueError:
                        continue

            if not values:
                raise SystemExit(
                    f"GaMD boost log could not be read: replica {state['replica']}"
                )

            writer.writerow(
                [
                    state["replica"],
                    state["window_center_A"],
                    len(values),
                    f"{min(values):.6f}",
                    f"{max(values):.6f}",
                ]
            )


def main() -> None:
    require_completed_segments()
    states = read_states()
    records = parse_exchanges(len(states))
    write_exchange_outputs(records, states)
    write_restraint_sampling(states)
    write_boost_range(states)
    print(f"GaREUS Analysis results: {WORK}")


if __name__ == "__main__":
    main()
