#!/usr/bin/env python3
"""Reject committed notebook outputs and Colab session metadata."""

import json
import os
import subprocess
import sys
from pathlib import Path


def tracked_notebooks():
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.ipynb"],
        check=True,
        stdout=subprocess.PIPE,
    )
    return [os.fsdecode(path) for path in result.stdout.split(b"\0") if path]


def main():
    args = sys.argv[1:]
    staged = "--staged" in args
    paths = [path for path in args if path != "--staged"] or tracked_notebooks()
    errors = []

    for path in paths:
        try:
            raw = (
                subprocess.run(
                    ["git", "show", f":{path}"],
                    check=True,
                    stdout=subprocess.PIPE,
                ).stdout
                if staged
                else Path(path).read_bytes()
            )
            notebook = json.loads(raw)
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            errors.append(f"{path}: unable to inspect notebook ({type(exc).__name__})")
            continue

        if b"prod.colab.dev" in raw or b"colab.googleusercontent.com" in raw:
            errors.append(f"{path}: contains a Colab session URL")

        for index, cell in enumerate(notebook.get("cells", []), start=1):
            if cell.get("cell_type") != "code":
                continue
            metadata = cell.get("metadata", {})
            if cell.get("outputs") or cell.get("execution_count") is not None:
                errors.append(f"{path}: code cell {index} has saved execution output")
            if "outputId" in metadata or "base_uri" in metadata.get("colab", {}):
                errors.append(f"{path}: code cell {index} has session metadata")

    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        print("Clear notebook outputs and execution metadata before committing.", file=sys.stderr)
        return 1
    print(f"Checked {len(paths)} notebook(s): no saved outputs or session URLs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
