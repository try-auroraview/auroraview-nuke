"""Reproduce the public, path-filtered history in a new local destination."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

SOURCE_COMMIT = "11b3a29ad95a46cb22aaa604614de16da16bfc22"
SOURCE_TREE = "4c66e7976d6cf8ea85821ed8d32b0c6d20723c1e"
FILTERED_HEAD = "5169694e541d1d3b4a953f289280ba5d46bae2c3"
BACKEND_PATH = "python/auroraview/utils/thread_dispatcher/backends/nuke.py"
MAPPING = {
    "LICENSE": "LICENSE",
    "python/auroraview/utils/thread_dispatcher.py": "migration/legacy-thread-dispatcher.py",
    BACKEND_PATH: "src/auroraview_nuke/dispatcher.py",
    "python/auroraview/adapter/hosts.py": "src/auroraview_nuke/host.py",
    "tests/python/integration/test_nuke_ipc.py": "migration/manual/test_nuke_ipc.py",
}


def run(command, cwd=None):
    environment = os.environ.copy()
    environment["GIT_NO_LAZY_FETCH"] = "1"
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    return subprocess.run(
        command, cwd=cwd, env=environment, check=True, capture_output=True, text=True, timeout=180
    ).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--filter-tool", default="git-filter-repo")
    args = parser.parse_args()
    source = args.source.resolve()
    destination = args.destination.resolve()
    if destination.exists() or source == destination or source in destination.parents:
        raise RuntimeError("destination must be new and outside the source repository")
    assert run(["git", "rev-parse", "HEAD"], source) == SOURCE_COMMIT
    assert run(["git", "rev-parse", "HEAD^{tree}"], source) == SOURCE_TREE
    assert run(["git", "rev-parse", "--is-shallow-repository"], source) == "false"
    assert run(["git", "rev-list", "--count", "HEAD"], source) == "1623"
    objects = run(["git", "rev-list", "--objects", "--missing=print", "HEAD"], source)
    assert not any(line.startswith("?") for line in objects.splitlines())
    run(
        [
            "git",
            "-c",
            "protocol.file.allow=always",
            "clone",
            "--no-local",
            "--no-checkout",
            "--single-branch",
            "--no-tags",
            str(source),
            str(destination),
        ]
    )
    # A detached source HEAD must not silently select an advanced source branch.
    assert run(["git", "rev-parse", "HEAD"], destination) == SOURCE_COMMIT
    command = [args.filter_tool, "--force"]
    for original, mapped in MAPPING.items():
        command += ["--path", original]
        if original != mapped:
            command += ["--path-rename", original + ":" + mapped]
    run(command, destination)
    assert run(["git", "rev-parse", "HEAD"], destination) == FILTERED_HEAD
    assert run(["git", "rev-list", "--count", "HEAD"], destination) == "9"
    migration = destination / "migration"
    migration.mkdir(exist_ok=True)
    shutil.copyfile(destination / ".git/filter-repo/commit-map", migration / "commit-map.txt")
    print("Filtered public history verified; package initialization remains a separate change.")


if __name__ == "__main__":
    main()
