"""Build the static Pages artifact from one commit of the public lab website."""

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from .catalog import catalog

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "kybak90/kybak90.github.io"
REFERENCE = "be7b4065287dd801c2070506dc53b80d0dc23558"


def fetch(url):
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "coauthor-network-build"})
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)


def read_sources(commit=None):
    if commit is None:
        commit = json.loads(fetch(f"https://api.github.com/repos/{SOURCE}/commits/main"))["sha"]
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Expected a full lab website commit SHA")
    base = f"https://raw.githubusercontent.com/{SOURCE}/{commit}"
    return commit, fetch(base + "/_bibliography/papers.bib"), fetch(base + "/_pages/publications.md")


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def build(commit=None):
    commit, bib, markdown = read_sources(commit)
    data = catalog(bib, markdown)
    payload = encode(data)
    version = hashlib.sha256(payload).hexdigest()
    # The manifest changes only with the delivered app or data, never just the time or source HEAD.
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        stage = Path(directory) / "site"
        shutil.copytree(ROOT / "web", stage)
        asset_hash = hashlib.sha256()
        for path in sorted(p for p in stage.rglob("*") if p.is_file()):
            asset_hash.update(path.relative_to(stage).as_posix().encode() + b"\0")
            asset_hash.update(hashlib.sha256(path.read_bytes()).digest())
        (stage / f"data-{version}.json").write_bytes(payload)
        (stage / "version.json").write_bytes(encode({"version": version, "app": asset_hash.hexdigest()}))
        out = ROOT / "dist"
        previous = Path(directory) / "previous"
        if out.exists():
            out.rename(previous)
        try:
            stage.rename(out)
        except OSError:
            if previous.exists():
                previous.rename(out)
            raise
    lines = [f"Lab source: https://github.com/{SOURCE}/tree/{commit}"]
    for key, view in data["modes"].items():
        lines.append(f"{key}: {len(view['papers'])} papers, {len(view['nodes'])} authors, "
                     f"{len(view['edges'])} coauthor pairs")
    print("\n".join(lines))
    if "GITHUB_STEP_SUMMARY" in os.environ:
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write("\n\n".join(lines) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", help="Reproduce a specific public lab commit (default: latest main)")
    build(parser.parse_args().commit)
