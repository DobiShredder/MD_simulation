"""Protect explicit writer scopes until the shell and its engine children stop."""

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path


def gate_acquire(gate):
    # The gate only serializes registration, not independent calculations.
    deadline = time.monotonic() + 3
    token = uuid.uuid4().hex
    while True:
        try:
            gate.mkdir()
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Writer registration gate is occupied: {gate}. Check running jobs before manual recovery.")
            time.sleep(0.02)
            continue
        owner = {"token": token, "host": socket.gethostname(), "pid": os.getpid(),
                 "started": time.time(), "command": sys.argv}
        (gate / "owner.json").write_text(json.dumps(owner, indent=2) + "\n")
        return token


def gate_release(gate, token):
    owner_file = gate / "owner.json"
    owner = json.loads(owner_file.read_text())
    if owner["token"] != token:
        raise RuntimeError(f"Writer registration ownership changed; retained: {gate}")
    owner_file.unlink()
    gate.rmdir()


def overlaps(first, second):
    first, second = Path(first), Path(second)
    return first == second or first in second.parents or second in first.parents


def acquire(registry, reads, writes, command):
    registry.mkdir(parents=True, exist_ok=True)
    gate = registry / ".gate"
    gate_token = gate_acquire(gate)
    token = uuid.uuid4().hex
    lock = registry / token
    owner = {
        "token": token, "host": socket.gethostname(), "pid": os.getpid(),
        "started": time.time(), "command": command, "reads": reads, "writes": writes,
    }
    try:
        for read in reads:
            for parent in (Path(read), *Path(read).parents):
                for pending in (parent / ".download.pending", parent.parent / f".{parent.name}.download.pending"):
                    if pending.exists() or pending.is_symlink():
                        raise RuntimeError(f"Source download publication is incomplete; inspect {pending}")
        for existing in registry.iterdir():
            if existing == gate:
                continue
            try:
                other = json.loads((existing / "owner.json").read_text())
            except (OSError, ValueError) as error:
                raise RuntimeError(f"Unresolved writer lock: {existing}. Check jobs before manual recovery.") from error
            for write in writes:
                for scope in other["reads"] + other["writes"]:
                    if overlaps(write, scope):
                        raise RuntimeError(f"Writer scope {write} conflicts with {scope}; lock: {existing}; owner: {other['host']} PID {other['pid']}.")
            for read in reads:
                for scope in other["writes"]:
                    if overlaps(read, scope):
                        raise RuntimeError(f"Input scope {read} has an active writer; lock: {existing}; owner: {other['host']} PID {other['pid']}.")
        lock.mkdir()
        (lock / "owner.json").write_text(json.dumps(owner, indent=2) + "\n")
    finally:
        gate_release(gate, gate_token)
    return lock, token


def release(lock, token):
    gate = lock.parent / ".gate"
    gate_token = gate_acquire(gate)
    try:
        owner_file = lock / "owner.json"
        owner = json.loads(owner_file.read_text())
        if owner["token"] != token:
            raise RuntimeError(f"Writer lock ownership changed; retained: {lock}")
        owner_file.unlink()
        lock.rmdir()
    finally:
        gate_release(gate, gate_token)


def live_group(group):
    # Ignore reparented zombies: they cannot write files or be killed.
    result = subprocess.run(["ps", "-axo", "pgid=,stat="], text=True, capture_output=True, check=True)
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0] == str(group) and not fields[1].startswith("Z"):
            return True
    return False


def signal_group(group, signum):
    try:
        os.killpg(group, signum)
    except ProcessLookupError:
        pass


def supervise(args):
    registry = Path(str(Path(args.registry).resolve()) + ".writers")
    reads = [str(Path(path).resolve()) for path in args.read]
    writes = [str(Path(path).resolve()) for path in args.write]
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command or not (reads or writes):
        raise RuntimeError("An entry and at least one input or output scope are required.")
    if args.callback_entry and os.environ.get("MD_WRITER_OWNER"):
        # Local WESTPA callbacks inherit the manager's session and root writer.
        owner_file = Path(os.environ["MD_WRITER_OWNER"])
        owner = json.loads(owner_file.read_text())
        root = Path(args.registry).resolve()
        if (owner_file.parent.parent != registry
                or owner.get("token") != os.environ.get("MD_WRITER_TOKEN")
                or not any(Path(scope) == root or Path(scope) in root.parents
                           for scope in owner["writes"])):
            raise RuntimeError(f"Callback cannot borrow manager writer: {owner_file}")
        env = os.environ.copy()
        env.update(MD_WRITER_PARENT=str(os.getppid()), MD_WRITER_ENTRY=command[0])
        # Keep the process group: the manager supervisor drains callbacks before unlock.
        os.execvpe("bash", ["bash", *command], env)
    child = None
    interrupted = 0

    def forward(signum, _frame):
        nonlocal interrupted
        interrupted = signum
        if child is not None:
            signal_group(child.pid, signum)

    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, forward)
    lock, token = acquire(registry, reads, writes, command)
    env = os.environ.copy()
    env.update(MD_WRITER_PARENT=str(os.getpid()), MD_WRITER_ENTRY=command[0],
               MD_WRITER_OWNER=str(lock / "owner.json"), MD_WRITER_TOKEN=token)
    drained = False
    try:
        if interrupted:
            return 128 + interrupted
        interpreter = sys.executable if args.python_entry else "bash"
        child = subprocess.Popen([interpreter, *command], env=env, start_new_session=True)
        if interrupted:
            signal_group(child.pid, interrupted)
        status = child.wait()
        # A failing shell may leave background engines. Terminate them before unlock.
        signal_group(child.pid, signal.SIGTERM)
        deadline = time.monotonic() + 5
        while live_group(child.pid):
            if time.monotonic() >= deadline:
                signal_group(child.pid, signal.SIGKILL)
            time.sleep(0.02)
        drained = True
        return 128 + interrupted if interrupted else (128 - status if status < 0 else status)
    finally:
        if child is None or drained:
            release(lock, token)
        else:
            print(f"Warning: child termination was not verified; writer lock retained: {lock}", file=sys.stderr)



def protect_python_entry(registry, *, reads=(), writes=()):
    """Protect a public Python workflow, borrowing a verified parent scope."""
    registry_path = Path(str(Path(registry).resolve()) + ".writers")
    read_paths = [str(Path(path).resolve()) for path in reads]
    write_paths = [str(Path(path).resolve()) for path in writes]
    try:
        owner_path = os.environ.get("MD_WRITER_OWNER")
        if owner_path:
            owner_file = Path(owner_path)
            owner = json.loads(owner_file.read_text())
            if (owner_file.parent.parent != registry_path
                    or owner.get("token") != os.environ.get("MD_WRITER_TOKEN")
                    or owner.get("host") != socket.gethostname()):
                raise RuntimeError(f"Cannot borrow parent writer: {owner_file}")
            os.kill(owner["pid"], 0)
            for path in write_paths:
                if not any(Path(scope) == Path(path) or Path(scope) in Path(path).parents
                           for scope in owner["writes"]):
                    raise RuntimeError(f"Output is outside parent writer scope: {path}")
            for path in read_paths:
                if not any(Path(scope) == Path(path) or Path(scope) in Path(path).parents
                           for scope in owner["reads"] + owner["writes"]):
                    raise RuntimeError(f"Input is outside parent writer scope: {path}")
            return
        args = argparse.Namespace(
            registry=str(registry), read=list(reads), write=list(writes),
            command=[sys.argv[0], *sys.argv[1:]],
            python_entry=True, callback_entry=False,
        )
        status = supervise(args)
    except (OSError, KeyError, ValueError, RuntimeError) as error:
        print(f"Error: writer protection: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    raise SystemExit(status)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, help="Built-system path defining the shared lock registry.")
    parser.add_argument("--read", action="append", default=[], help="Shared input path protected from builders.")
    parser.add_argument("--write", action="append", default=[], help="Exclusive output/state path.")
    parser.add_argument("--python-entry", action="store_true", help="Run a Python entry with this interpreter instead of bash.")
    parser.add_argument("--callback-entry", action="store_true", help="Borrow a verified local WESTPA manager writer, or acquire a standalone writer.")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Shell entry and its original arguments after --.")
    args = parser.parse_args()
    try:
        return supervise(args)
    except (OSError, KeyError, ValueError, RuntimeError) as error:
        print(f"Error: writer protection: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
