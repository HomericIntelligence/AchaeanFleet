"""Run inside the image with fresh private storage; never make a model turn."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import subprocess
import time


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def exchange(message: dict) -> dict:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(8)
        connection.connect("/var/lib/fleet/state/worker.sock")
        connection.sendall((json.dumps(message) + "\n").encode())
        with connection.makefile("rb") as stream:
            return json.loads(stream.readline(1048576))


def worker() -> dict:
    codex_home = Path("/var/lib/fleet/codex")
    codex_home.mkdir(mode=0o700)
    Path("/var/lib/fleet/state").mkdir(mode=0o700)
    Path("/workspace/gate-workspace").mkdir(mode=0o700)
    require(not (codex_home / "auth.json").exists(), "authentication storage is not empty")
    argv = ["/opt/fleet-entrypoint.sh", "serve", "--state-dir", "/var/lib/fleet/state",
            "--workspace-root", "/workspace", "--codex-home", str(codex_home),
            "--worker-id", "fleet-ci", "--pool-id", "fleet-ci", "--host-id", "isolated-ci",
            "--generation", "1", "--capacity", "1", "--codex-bin", "/opt/codex-bin/codex"]
    with Path("/var/lib/fleet/startup.log").open("w") as log:
        process = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 40
            while not Path("/var/lib/fleet/state/worker.sock").exists():
                require(process.poll() is None and time.monotonic() < deadline,
                        "worker startup failed; see startup.log")
                time.sleep(0.1)
            before = exchange({"operation": "inventory"})
            rejection = exchange({
                "schema": "hi/fleet/v1", "commandId": "gate-1", "idempotencyKey": "gate-1",
                "workerId": "fleet-ci", "generation": 1, "targetKind": "sessions",
                "targetId": "gate-session", "operation": "start", "workspace": "gate-workspace",
                "agentId": "gate-agent", "taskId": "gate-task", "executionId": "gate-execution",
                "stage": "metadata-probe", "payload": {}})
            after = exchange({"operation": "inventory"})
            require(rejection.get("status") == "failed" and rejection.get("receipt", {}).get("error") ==
                    "linux_execution_requires_verified_boundary", "expected Linux admission rejection")
            for inventory in (before, after):
                require(inventory.get("sessions") == [] and inventory.get("activeReservations") == 0
                        and inventory.get("capacity") == 1, "unexpected worker admission or inventory")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
                raise
    require(process.returncode == 0, "worker shutdown failed")
    require(not (codex_home / "auth.json").exists(), "authentication storage changed")
    return {"before": before, "rejection": rejection, "after": after, "workerExit": process.returncode}


def build_tools() -> dict:
    require(not Path("/opt/codex-bin").exists(), "build-tools must not contain a provider")
    recipe = Path("/workspace/justfile")
    recipe.write_text("probe:\n    @python -c 'from pathlib import Path; Path(\"receipt.txt\").write_text(\"fleet-build-smoke\\n\")'\n")
    subprocess.run(["just", "--justfile", str(recipe), "probe"], check=True, timeout=10)
    require(Path("/workspace/receipt.txt").read_text() == "fleet-build-smoke\n", "recipe output mismatch")
    return {"recipe": "probe", "recipeCompleted": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=("worker", "build-tools"))
    args = parser.parse_args()
    os.umask(0o077)
    require(os.getuid() == 1000, "runtime must use UID 1000")
    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines() if ":" in line)
    require(int(status["CapEff"].strip(), 16) == 0 and status["NoNewPrivs"].strip() == "1",
            "effective capability/no-new-privileges policy mismatch")
    Path("/var/lib/fleet/home").mkdir(mode=0o700)
    observations = worker() if args.target == "worker" else build_tools()
    print(json.dumps({"target": args.target, "passed": True, "uid": os.getuid(),
                      "packageVersion": importlib.metadata.version("homericintelligence-hephaestus"),
                      "effectiveCapabilities": status["CapEff"].strip(), "noNewPrivileges": True,
                      "authorizesAdmission": False, "normalModelToolRouteTested": False,
                      "observations": observations}, sort_keys=True))


if __name__ == "__main__":
    main()
