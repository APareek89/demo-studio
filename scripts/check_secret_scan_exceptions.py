#!/usr/bin/env python3
"""Fail closed if a reviewed secret-scan exception line changes.

Run before every scan. --source index validates exactly staged blobs; HEAD
validates the committed tree; working-tree validates the current files.
Matched values are never printed. History fingerprints include immutable commits.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def verify(repo: Path, source: str = "working-tree") -> list[str]:
    def read(name):
        if source == "working-tree":
            return (repo / name).read_bytes()
        ref = ":" if source == "index" else "HEAD:"
        return subprocess.check_output(["git", "show", ref + name], cwd=repo, stderr=subprocess.DEVNULL)
    try:
        review = json.loads(read("docs/security/secret-scan-exceptions.json"))
        ignore = read(".gitleaksignore").decode()
    except (OSError, ValueError, subprocess.CalledProcessError):
        return [f"Reviewed exception metadata is missing or invalid in {source}"]
    expected = {item[key] for item in review["findings"]
                for key in ("head_fingerprint", "history_fingerprint") if item.get(key)}
    actual = [line.strip() for line in ignore.splitlines()
              if line.strip() and not line.lstrip().startswith("#")]
    errors = []
    if set(actual) != expected or len(actual) != len(expected):
        errors.append("Exception fingerprints differ from the reviewed exact set")
    for item in review["findings"]:
        name, number = item["file"], item["line"]
        try:
            path = (repo / name).resolve()
            if not path.is_relative_to(repo.resolve()):
                raise ValueError("path outside repository")
            data = read(name)
            line = data.decode().splitlines()[number - 1]
            if hashlib.sha256(line.encode()).hexdigest() != item["head_line_sha256"]:
                errors.append(f"{name}:{number}: reviewed line changed; renew review before scan")
        except (OSError, ValueError, IndexError, subprocess.CalledProcessError):
            errors.append(f"{name}:{number}: reviewed line cannot be verified")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("working-tree", "index", "HEAD"), default="working-tree")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    errors = verify(repo, args.source)
    for error in errors:
        print(error)
    if errors:
        return 1
    print(f"Reviewed secret-scan exceptions unchanged ({args.source}); exact fingerprints and line hashes verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
