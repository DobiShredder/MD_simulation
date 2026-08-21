#!/usr/bin/env python3
"""Calculate exchange and temperature-visit statistics from an AMBER T-REMD remlog."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

WORK = Path("work")
EXCHANGE_HEADER = re.compile(r"^#\s*exchange\s+(?P<number>\d+)", re.IGNORECASE)
EXPLICIT = re.compile(
    r"state_a=(?P<a>\d+)\s+state_b=(?P<b>\d+)\s+accepted=(?P<ok>[01])"
)


def read_states() -> list[dict[str, str]]:
    path = WORK / "states.tsv"
    if not path.is_file():
        raise SystemExit(f"state table not found: {path}")

    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def require_production_outputs(states: list[dict[str, str]]) -> None:
    if not (WORK / "exchange.log").is_file():
        raise SystemExit(f"exchange log not found: {WORK / 'exchange.log'}")
    for state in states:
        output = WORK / state["replica"] / "production.out"
        if not output.is_file():
            raise SystemExit(f"production output not found: {output}")


def temperature_state(value: float, temperatures: list[float]) -> int:
    state = min(range(len(temperatures)), key=lambda index: abs(temperatures[index] - value))

    if abs(temperatures[state] - value) > 0.1:
        raise ValueError(f"Target temperature is not present in the temperature ladder: {value}")

    return state


def block_records(
    exchange_number: int,
    rows: list[tuple[int, float, float, float]],
    state_count: int,
) -> tuple[list[tuple[int, int, int]], dict[int, int]]:
    attempted: list[tuple[int, int, int]] = []
    new_states: dict[int, int] = {}

    accepted_pairs = {
        tuple(sorted((old_state, new_state)))
        for _, velocity_scale, old_state, new_state in rows
        if velocity_scale > 0.0 and old_state != new_state
    }

    # AMBER alternates (0,1),(2,3),... with (1,2),(3,4),....
    # The latter block can also attempt an endpoint exchange; adjacent-state
    # acceptance output excludes that non-adjacent pair.
    offset = 1 if exchange_number % 2 == 1 else 0
    for state_a in range(offset, state_count - 1, 2):
        state_b = state_a + 1
        accepted = int((state_a, state_b) in accepted_pairs)
        attempted.append((state_a, state_b, accepted))

    for replica, _, _, new_state in rows:
        new_states[replica] = new_state

    return attempted, new_states


def parse_logs(
    temperatures: list[float],
) -> tuple[list[tuple[int, int, int]], list[list[int]] | None]:
    records: list[tuple[int, int, int]] = []
    visits = [[replica] for replica in range(len(temperatures))]
    found_temperature_rows = False

    for path in sorted(WORK.glob("exchange*.log")):
        exchange_number = 0
        rows: list[tuple[int, float, float, float]] = []

        def flush_block() -> None:
            nonlocal found_temperature_rows
            if not rows or exchange_number == 0:
                return

            attempted, new_states = block_records(
                exchange_number, rows, len(temperatures)
            )
            records.extend(attempted)

            if len(new_states) == len(temperatures):
                for replica in range(len(temperatures)):
                    visits[replica].append(new_states[replica])
                found_temperature_rows = True

        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            header = EXCHANGE_HEADER.match(line.strip())
            if header:
                flush_block()
                exchange_number = int(header.group("number"))
                rows = []
                continue

            explicit = EXPLICIT.search(line)
            if explicit:
                records.append(
                    (
                        int(explicit.group("a")),
                        int(explicit.group("b")),
                        int(explicit.group("ok")),
                    )
                )
                continue

            fields = line.split()
            if exchange_number == 0 or len(fields) < 7:
                continue

            try:
                replica = int(fields[0]) - 1
                velocity_scale = float(fields[1])
                old_temperature = float(fields[4])
                new_temperature = float(fields[5])
                old_state = temperature_state(old_temperature, temperatures)
                new_state = temperature_state(new_temperature, temperatures)
            except (ValueError, IndexError):
                continue

            if 0 <= replica < len(temperatures):
                rows.append((replica, velocity_scale, old_state, new_state))

        flush_block()

    if not records:
        raise SystemExit(
            "Exchange record not found. Check work/exchange.log."
        )

    return records, visits if found_temperature_rows else None


def reconstructed_visits(
    records: list[tuple[int, int, int]], state_count: int
) -> list[list[int]]:
    labels = list(range(state_count))
    visits = [[state] for state in labels]

    for state_a, state_b, accepted in records:
        if accepted:
            replica_a = labels.index(state_a)
            replica_b = labels.index(state_b)
            labels[replica_a], labels[replica_b] = labels[replica_b], labels[replica_a]

        for replica, state in enumerate(labels):
            visits[replica].append(state)

    return visits


def write_exchange_summary(
    records: list[tuple[int, int, int]], state_count: int
) -> None:
    totals: dict[tuple[int, int], list[int]] = defaultdict(lambda: [0, 0])

    for state_a, state_b, accepted in records:
        if abs(state_a - state_b) != 1:
            continue
        pair = (min(state_a, state_b), max(state_a, state_b))
        totals[pair][0] += 1
        totals[pair][1] += accepted

    output = WORK / "exchange_summary.tsv"
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["state_a", "state_b", "attempts", "accepted", "ratio"])

        for state_a in range(state_count - 1):
            state_b = state_a + 1
            attempts, accepted = totals[(state_a, state_b)]
            ratio = accepted / attempts if attempts else 0.0
            writer.writerow([state_a, state_b, attempts, accepted, f"{ratio:.6f}"])


def count_round_trips(states: list[int], highest: int) -> int:
    endpoint = None
    reached_highest = False
    round_trips = 0

    for state in states:
        if state == highest:
            reached_highest = True
            endpoint = highest
        elif state == 0:
            if endpoint == highest and reached_highest:
                round_trips += 1
            endpoint = 0
            reached_highest = False

    return round_trips


def write_visit_outputs(
    visits: list[list[int]], states: list[dict[str, str]]
) -> None:
    visit_output = WORK / "replica_visits.tsv"
    with visit_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["replica", "min_state", "max_state", "round_trips"])

        for replica, history in enumerate(visits):
            writer.writerow(
                [
                    f"{replica:03d}",
                    min(history),
                    max(history),
                    count_round_trips(history, len(states) - 1),
                ]
            )

    occupancy_output = WORK / "temperature_occupancy.tsv"
    with occupancy_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["replica", "state", "temperature_K", "visits", "fraction"])

        for replica, history in enumerate(visits):
            for state_index, state in enumerate(states):
                count = history.count(state_index)
                writer.writerow(
                    [
                        f"{replica:03d}",
                        state_index,
                        state["temperature_K"],
                        count,
                        f"{count / len(history):.6f}",
                    ]
                )


def main() -> None:
    states = read_states()
    require_production_outputs(states)
    temperatures = [float(state["temperature_K"]) for state in states]
    records, direct_visits = parse_logs(temperatures)

    if direct_visits is None:
        visits = reconstructed_visits(records, len(states))
    else:
        visits = direct_visits

    write_exchange_summary(records, len(states))
    write_visit_outputs(visits, states)
    print(f"Exchange and temperature-visit summary: {WORK}")


if __name__ == "__main__":
    main()
