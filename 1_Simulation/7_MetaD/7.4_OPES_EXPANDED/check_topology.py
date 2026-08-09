#!/usr/bin/env python3
"""Generated topology에서 capped alanine atom ordering을 확인한다."""

from pathlib import Path
import sys
import parmed

EXPECTED = {
    5: ("ACE", "C"),
    7: ("ALA", "N"),
    9: ("ALA", "CA"),
    15: ("ALA", "C"),
    17: ("ALA", "N"),
}


def main() -> int:
    if len(sys.argv) != 3:
        print("사용법: check_topology.py SYSTEM.parm7 ATOM_MAP.tsv", file=sys.stderr)
        return 2
    topology = parmed.load_file(sys.argv[1])
    rows = []
    for atom_number, expected in EXPECTED.items():
        atom = topology.atoms[atom_number - 1]
        observed = (atom.residue.name, atom.name)
        if observed != expected:
            raise ValueError(f"atom {atom_number}: expected {expected}, observed {observed}")
        rows.append((atom_number, *observed))
    output_path = Path(sys.argv[2])
    output_path.write_text(
        "atom\tresidue\tname\n" + "".join(f"{n}\t{r}\t{a}\n" for n, r, a in rows),
        encoding="utf-8",
    )
    output_path.with_name("atom_count.txt").write_text(
        f"{len(topology.atoms)}\n",
        encoding="ascii",
    )
    print(f"Atom ordering 검증 완료: {sys.argv[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
