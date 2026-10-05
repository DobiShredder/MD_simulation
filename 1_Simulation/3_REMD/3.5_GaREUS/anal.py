#!/usr/bin/env python3
"""Summarize GaREUS exchanges and restraint sampling as TSV."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

WORK = Path("work")
EXPLICIT = re.compile(
    r"state_a=(?P<a>\d+)\s+state_b=(?P<b>\d+)\s+accepted=(?P<ok>[01])"
)


def read_states() -> list[dict[str, str]]:
    path = WORK / "states.tsv"
    if not path.is_file():
        raise SystemExit(f"window table not found: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        states = list(csv.DictReader(handle, delimiter="\t"))
    if len(states) < 2 or len(states) % 2:
        raise SystemExit(f"Replica exchange requires at least two and an even number of states: {WORK / 'states.tsv'} ({len(states)} states)")
    return states


def require_production_output() -> None:
    path = WORK / "exchange.log"
    if not path.is_file():
        raise SystemExit(f"exchange log not found: {path}")


def native_exchange_event(
    rows: dict[int, tuple[int, int]], state_count: int, path: Path
) -> list[tuple[int, int, int]]:
    if len(rows) != state_count:
        raise SystemExit(f"Exchange analysis: incomplete exchange block in {path}")
    event = []
    for replica, (neighbor, accepted) in sorted(rows.items()):
        if rows.get(neighbor) != (replica, accepted):
            raise SystemExit(f"Exchange analysis: inconsistent partner rows in {path}")
        if replica < neighbor:
            event.append((replica, neighbor, accepted))
    return event


def parse_exchanges(state_count: int) -> list[list[tuple[int, int, int]]]:
    events: list[list[tuple[int, int, int]]] = []
    path = WORK / "exchange.log"
    block_rows: dict[int, tuple[int, int]] = {}
    in_native_block = False

    for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if re.match(r"^\s*#\s*exchange\s+\d+\b", line):
            if in_native_block:
                events.append(native_exchange_event(block_rows, state_count, path))
            block_rows = {}
            in_native_block = True
            continue

        match = EXPLICIT.search(line)
        if match:
            if in_native_block:
                raise SystemExit(f"Exchange analysis: mixed log formats in {path}:{line_number}")
            replica = int(match.group("a"))
            neighbor = int(match.group("b"))
            if not 0 <= replica < state_count or not 0 <= neighbor < state_count or replica == neighbor:
                raise SystemExit(f"Exchange analysis: invalid state index in {path}:{line_number}")
            events.append([(min(replica, neighbor), max(replica, neighbor), int(match.group("ok")))])
            continue

        fields = line.split()
        if not fields or fields[0].startswith("#"):
            continue
        if not fields[0].isdigit():
            continue
        if not in_native_block or len(fields) != 9 or fields[7] not in {"T", "F"}:
            raise SystemExit(f"Exchange analysis: invalid native record in {path}:{line_number}")
        try:
            replica, neighbor = int(fields[0]) - 1, int(fields[1]) - 1
        except ValueError:
            raise SystemExit(f"Exchange analysis: invalid replica index in {path}:{line_number}") from None
        if not 0 <= replica < state_count or not 0 <= neighbor < state_count or replica == neighbor or replica in block_rows:
            raise SystemExit(f"Exchange analysis: invalid or duplicated replica in {path}:{line_number}")
        block_rows[replica] = (neighbor, int(fields[7] == "T"))

    if in_native_block:
        events.append(native_exchange_event(block_rows, state_count, path))
    if not events:
        raise SystemExit(f"Exchange analysis: AMBER replica-exchange record not found in {path}.")
    return events


def count_round_trips(states: list[int], highest: int) -> int:
    if highest < 1:
        return 0
    starting_endpoint = None
    reached_opposite = False
    round_trips = 0

    for state in states:
        if state not in {0, highest}:
            continue
        if starting_endpoint is None:
            starting_endpoint = state
        elif state != starting_endpoint:
            reached_opposite = True
        elif reached_opposite:
            round_trips += 1
            reached_opposite = False

    return round_trips


def write_exchange_outputs(
    records: list[list[tuple[int, int, int]]], states: list[dict[str, str]]
) -> None:
    totals: dict[tuple[int, int], list[int]] = defaultdict(lambda: [0, 0])
    labels = list(range(len(states)))
    visits = [[state] for state in labels]

    for event in records:
        for state_a, state_b, accepted in event:
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
            round_trips = count_round_trips(history, len(states) - 1)
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

    for path in [replica_dir / "restraint.production.dat"]:
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
                    f"Restraint sampling: no DUMPAVE values in {WORK / state['replica'] / 'restraint.production.dat'}"
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



def read_total_boost(path: Path) -> list[float]:
    fields = None
    values = []
    components = ("boost-energy-potential", "boost-energy-dihedral")
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            candidate = [name.strip().lower() for name in stripped.lstrip("#").split(",")]
            if not all(name in candidate for name in components):
                continue
            if len(candidate) != len(set(candidate)) or fields is not None and fields != candidate:
                raise SystemExit(f"Boost analysis: inconsistent header in {path}:{line_number}")
            fields = candidate
            continue
        if fields is None:
            raise SystemExit(f"Boost analysis: dual-boost header missing in {path}:{line_number}")
        columns = stripped.split()
        if len(columns) != len(fields):
            raise SystemExit(f"Boost analysis: column count differs from header in {path}:{line_number}")
        try:
            total = sum(float(columns[fields.index(name)]) for name in components)
        except ValueError:
            raise SystemExit(f"Boost analysis: nonnumeric boost in {path}:{line_number}") from None
        if not np.isfinite(total):
            raise SystemExit(f"Boost analysis: nonfinite boost in {path}:{line_number}")
        values.append(total)
    if not values:
        raise SystemExit(f"Boost analysis: no boost values in {path}")
    return values


def boost_range_rows(states: list[dict[str, str]]) -> list[list[object]]:
    rows = []
    for state in states:
        values = read_total_boost(WORK / state["replica"] / "gamd.production.log")
        rows.append([state["replica"], state["window_center_A"], len(values),
                     f"{min(values):.6f}", f"{max(values):.6f}"])

    return rows


def write_boost_range(rows: list[list[object]]) -> None:
    with (WORK / "boost_potential.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["state", "window_center_A", "samples", "boost_min_kcal_mol", "boost_max_kcal_mol"])
        writer.writerows(rows)


def main() -> None:
    print(f"Reading exchange-analysis inputs: {WORK / 'states.tsv'} and {WORK / 'exchange.log'}", flush=True)
    require_production_output()
    states = read_states()
    records = parse_exchanges(len(states))
    # Validate boost data before replacing any diagnostics.
    boost_rows = boost_range_rows(states)
    print(f"Writing exchange summaries: {WORK}", flush=True)
    write_exchange_outputs(records, states)
    print(f"Calculating restraint sampling for {len(states)} replicas: {WORK / 'restraint_sampling.tsv'}", flush=True)
    write_restraint_sampling(states)
    print(f"Calculating replica boost ranges: {WORK / 'boost_potential.tsv'}", flush=True)
    write_boost_range(boost_rows)
    print(f"GaREUS Analysis results: {WORK}")


if __name__ == "__main__":
    main()
