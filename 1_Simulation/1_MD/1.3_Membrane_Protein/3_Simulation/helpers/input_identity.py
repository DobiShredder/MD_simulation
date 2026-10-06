"""Compare small immutable calculation inputs before launch or result reuse."""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read_identity(record):
    try:
        previous = json.loads(record.read_text())
        if not isinstance(previous, dict):
            raise ValueError("expected an object")
        if (not isinstance(previous.get("stage"), str)
                or not isinstance(previous.get("files"), dict)
                or not isinstance(previous.get("values"), list)
                or not isinstance(previous.get("outputs"), list)):
            raise ValueError("missing stage, files, values, or outputs")
        if not all(isinstance(name, str) and isinstance(value, str)
                   for name, value in previous["files"].items()):
            raise ValueError("invalid input hashes")
        if not all(isinstance(name, str) for name in previous["outputs"]):
            raise ValueError("invalid output paths")
        return previous
    except (OSError, ValueError) as error:
        raise RuntimeError(f"Input identity record is unreadable: {record}: {error}. "
                           "Files were preserved. Use a new work directory.") from error


def require_writer(record):
    owner_file = os.environ.get("MD_WRITER_OWNER", "")
    if not owner_file:
        raise RuntimeError("Input identity requires an active writer guard.")
    owner = json.loads(Path(owner_file).read_text())
    if owner["token"] != os.environ.get("MD_WRITER_TOKEN"):
        raise RuntimeError("Writer lock ownership does not match this execution.")
    path = record.resolve()
    if not any(path == Path(scope) or Path(scope) in path.parents for scope in owner["writes"]):
        raise RuntimeError(f"Input identity is outside the protected writer scope: {record}")


def check(record, stage, inputs, values, outputs, config_path=None):
    require_writer(record)
    files = {}
    for name in inputs:
        path = Path(name).resolve()
        if not path.is_file() or not path.stat().st_size:
            raise RuntimeError(f"{stage}: calculation input missing or empty: {name}")
        files[str(path)] = digest(path)
    current = {"stage": stage, "files": files, "values": values,
               "outputs": [str(Path(name).resolve()) for name in outputs]}
    if record.exists():
        previous = read_identity(record)
        changed = [name for name in set(previous["files"]) | set(files)
                   if previous["files"].get(name) != files.get(name)]
        if (changed or previous["values"] != values or previous["stage"] != stage
                or previous["outputs"] != current["outputs"]):
            context = ", ".join(sorted(changed)) if changed else "execution settings"
            if not changed and config_path:
                context = f"{config_path} (consumed settings)"
            raise RuntimeError(f"{stage}: input changed: {context}. Existing results and identity were preserved. Use a new work directory.")
        return
    existing = [name for name in outputs if Path(name).exists() or Path(name).is_symlink()]
    completion_marker = record.with_name(record.name.replace(".identity.json", ".success.json"))
    if completion_marker.exists() or completion_marker.is_symlink():
        existing.append(str(completion_marker))
    if existing:
        raise RuntimeError(f"{stage}: results have no input identity: {existing[0]}. Files were preserved. Use a new work directory.")
    record.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation: never replace an earlier identity with current inputs.
    with record.open("x") as handle:
        json.dump(current, handle, indent=2)
        handle.write("\n")


def amber(args):
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    inputs = []
    outputs = [args.marker] if args.marker else []
    directory = Path(args.directory)
    for index, value in enumerate(command[:-1]):
        if value in ("-i", "-p", "-c", "-ref"):
            inputs.append(str(directory / command[index + 1]))
        if value in ("-o", "-r", "-x", "-inf", "-gamd"):
            outputs.append(str(directory / command[index + 1]))
    check(Path(args.record), args.stage, inputs + args.input, command, outputs + args.output, args.config)


def verify(directory, managed_outputs=False):
    directory = Path(directory)
    require_writer(directory)
    if not directory.exists():
        return
    known_outputs = set()
    for record in directory.rglob(".*.identity.json"):
        if managed_outputs and not (record.name == ".we-input.identity.json" or record.name.startswith(".block.")):
            continue
        previous = read_identity(record)
        for name, expected in previous["files"].items():
            path = Path(name)
            if not path.is_file() or digest(path) != expected:
                raise RuntimeError(f"{previous['stage']}: input changed: {name}. Files and identity were preserved. Use a new work directory.")
        known_outputs.update(previous["outputs"])
        # GaMD keeps a mutable engine file beside its recorded immutable snapshots.
        for name in previous["outputs"]:
            if name.endswith(".gamd.rst"):
                known_outputs.add(str(Path(name).parent / "gamd-restart.dat"))
    if managed_outputs:
        # WESTPA manages per-walker outputs and continuation through HDF5 state.
        # Its wrapper separately requires an identity for that HDF5 file.
        return
    for path in directory.rglob("*"):
        runtime_name = path.name.startswith(("min-solvent.", "min-environment.", "min-all.", "min-lipid.", "minimize.", "heat.", "equil-heavy.", "equil-backbone.", "equil.", "equilibrate.", "production.", "gamd_prepare."))
        result_file = (path.name.endswith(".complete") or path.suffix in (".out", ".nc", ".cpt")
                       or (runtime_name and path.suffix in (".gro", ".log", ".tpr", ".edr", ".rst7", ".info", ".rst"))
                       or path.name in ("mdinfo", "exchange.log", "production.group", "gamd.prepare.log", "gamd-restart.dat", "production_start.rst7",
                                        "prepared.gamd.rst", "HILLS", "KERNELS", "COLVAR", "opes.state", "DELTAFS", "FUNNEL_GRID"))
        if path.is_file() and result_file:
            if str(path.resolve()) not in known_outputs:
                raise RuntimeError(f"{path.name}: results have no input identity: {path}. Files were preserved. Use a new work directory.")



def check_completion(record):
    require_writer(record)
    previous = read_identity(record)
    marker = record.with_name(record.name.replace(".identity.json", ".success.json"))
    if marker.exists() or marker.is_symlink():
        try:
            proof = json.loads(marker.read_text())
        except (OSError, ValueError) as error:
            raise RuntimeError(f"{previous['stage']}: completion evidence unreadable: {marker}: {error}. Files were preserved.") from error
        if (not isinstance(proof, dict) or proof.get("identity_sha256") != digest(record)
                or not isinstance(proof.get("required_outputs"), list)
                or not proof["required_outputs"]
                or not all(isinstance(name, str) for name in proof["required_outputs"])):
            raise RuntimeError(f"{previous['stage']}: invalid completion evidence: {marker}. Files were preserved.")
        for name in proof["required_outputs"]:
            path = Path(name)
            if not path.is_file() or not path.stat().st_size:
                raise RuntimeError(f"{previous['stage']}: completed output is missing or empty: {path}. Files were preserved.")
        return "complete"
    for name in previous["outputs"]:
        path = Path(name)
        if path.exists() or path.is_symlink():
            raise RuntimeError(f"{previous['stage']}: output has no successful completion evidence: {path}. Files were preserved. Start a new work directory or tutorial copy.")
    return "new"


def finish_completion(record, directory, required):
    require_writer(record)
    previous = read_identity(record)
    command = previous["values"]
    directory = Path(directory)
    # AMBER's ntwx=0 (also the default) does not produce a trajectory.
    # Read the unchanged input; never infer freshness from an old output.
    ntwx = 0
    if "-i" in command:
        input_file = directory / command[command.index("-i") + 1]
        text = "\n".join(line.split("!", 1)[0] for line in input_file.read_text().splitlines())
        cntrl = re.search(r"&cntrl\b(.*?)(?:/|&end)", text, re.IGNORECASE | re.DOTALL)
        if cntrl:
            match = re.search(r"\bntwx\s*=\s*([+-]?\d+)", cntrl.group(1), re.IGNORECASE)
            if match:
                ntwx = int(match.group(1))
    for flag in ("-o", "-r", "-x", "-gamd"):
        if flag in command and (flag != "-x" or ntwx != 0):
            required.append(str(directory / command[command.index(flag) + 1]))
    paths = sorted({str(Path(name).resolve()) for name in required})
    if not paths:
        raise RuntimeError(f"{previous['stage']}: no required completion outputs were specified.")
    for name in paths:
        path = Path(name)
        if not path.is_file() or not path.stat().st_size:
            raise RuntimeError(f"{previous['stage']}: output was not created or is empty: {path}. Files were preserved.")
    marker = record.with_name(record.name.replace(".identity.json", ".success.json"))
    proof = {"identity_sha256": digest(record), "required_outputs": paths}
    # Call only after a successful engine exit and stage-specific output checks.
    # Exclusive creation prevents retroactive replacement of existing evidence.
    with marker.open("x") as handle:
        json.dump(proof, handle, indent=2)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", help="Stage identity record; existing records are never replaced.")
    parser.add_argument("--stage", help="Stage name shown on input mismatch.")
    parser.add_argument("--verify", help="Verify previous input records and reject identity-less results under this output path.")
    parser.add_argument("--westpa-records", help="Verify immutable records for a WESTPA-managed output tree; the wrapper checks HDF5 identity separately.")
    parser.add_argument("--input", action="append", default=[], help="Immutable input file to hash.")
    parser.add_argument("--output", action="append", default=[], help="Result file that requires a previous identity.")
    parser.add_argument("--value", action="append", default=[], help="Calculation setting to compare.")
    parser.add_argument("--marker", help="Completion marker associated with this stage.")
    parser.add_argument("--directory", default=".", help="Engine working directory for command paths.")
    parser.add_argument("--config", help="Resolved config consumed by a runtime input generator.")
    parser.add_argument("--section", action="append", default=[], help="Consumed scientific config section to compare.")
    parser.add_argument("--run-key", action="append", default=[], help="Consumed run setting to compare; segment counts are excluded.")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="AMBER command after --; parse its immutable input/output paths.")
    parser.add_argument("--check-completion", help="Return complete/new; refuse outputs without successful completion evidence.")
    parser.add_argument("--finish-completion", help="Record completion after a successful engine exit and output checks.")
    parser.add_argument("--required-output", action="append", default=[], help="Additional nonempty output required for stage completion.")
    args = parser.parse_args()
    try:
        if args.config:
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib
            with Path(args.config).open("rb") as handle:
                config = tomllib.load(handle)
            settings = {key: config[key] for key in args.section}
            run = config.get("run", config)
            settings["run"] = {key: run[key] for key in args.run_key}
            args.value.append(json.dumps(settings, sort_keys=True))
        if args.check_completion:
            print(check_completion(Path(args.check_completion)))
        elif args.finish_completion:
            finish_completion(Path(args.finish_completion), args.directory, args.required_output)
        elif args.verify:
            verify(args.verify)
        elif args.westpa_records:
            verify(args.westpa_records, managed_outputs=True)
        elif not args.record or not args.stage:
            raise RuntimeError("A record and stage are required for identity checks.")
        elif args.command:
            amber(args)
        else:
            check(Path(args.record), args.stage, args.input, args.value,
                  args.output + ([args.marker] if args.marker else []), args.config)
    except (OSError, KeyError, ValueError, RuntimeError) as error:
        print(f"Error: input identity: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
