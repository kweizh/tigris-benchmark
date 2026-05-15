import json
import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/snapshot-list"
SNAPSHOTS_FILE = os.path.join(PROJECT_DIR, "snapshots.txt")
TRIAL_ID_PATH = "/logs/artifacts/trial_id"

def _read_trial_id():
    with open(TRIAL_ID_PATH, "r", encoding="utf-8") as handle:
        return handle.read().strip()

def _bucket_name():
    name = f"harbor-history-{_read_trial_id()}"
    import re
    name = re.sub(r"[^a-z0-9.-]", "-", name.lower())
    return name

def _tigris_cmd():
    """Return the command list for invoking the Tigris CLI."""
    if shutil.which("tigris") is not None:
        return ["tigris"]
    pytest.fail(
        "tigris CLI binary not available on PATH; cannot verify final state."
    )


def _list_snapshots():
    """Run `tigris snapshots list <bucket> --format json` and return the
    parsed JSON payload."""
    bucket = _bucket_name()
    cmd = _tigris_cmd() + [
        "snapshots", "list", bucket, "--format", "json",
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, (
        f"'tigris snapshots list {bucket} --format json' failed: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"'tigris snapshots list --format json' did not emit valid JSON: "
            f"{exc!s}; stdout={result.stdout!r}"
        )
    return payload


def test_snapshots_output_file_exists():
    assert os.path.isfile(SNAPSHOTS_FILE), (
        f"User must produce the snapshot list at {SNAPSHOTS_FILE}."
    )


def test_cli_reports_at_least_three_snapshots():
    """Priority 1: Use the Tigris CLI to confirm snapshots exist for the
    bucket pre-populated by setup.sh."""
    payload = _list_snapshots()
    snapshots = payload.get("snapshots")
    assert isinstance(snapshots, list), (
        f"Expected 'snapshots' to be a list in CLI output, got: {payload!r}"
    )
    bucket = _bucket_name()
    assert len(snapshots) >= 3, (
        f"Expected at least 3 snapshots in bucket '{bucket}', got "
        f"{len(snapshots)}: {snapshots!r}"
    )
    for entry in snapshots:
        assert isinstance(entry.get("version"), str) and entry["version"], (
            f"Each snapshot entry must include a non-empty 'version' "
            f"string. Got: {entry!r}"
        )


def test_snapshots_file_matches_cli_in_chronological_order():
    """Priority 1: The contents of snapshots.txt must equal the snapshot
    versions reported by the CLI, reversed into chronological (oldest-first)
    order, with no extra header, blank lines, JSON, or whitespace."""
    payload = _list_snapshots()
    snapshots = payload.get("snapshots") or []
    # The Tigris API returns snapshots in reverse-chronological order. The
    # task requires the file to be ordered oldest first, so reverse here.
    expected_ids = [s["version"] for s in snapshots][::-1]

    with open(SNAPSHOTS_FILE) as f:
        raw = f.read()

    # Split on newlines without trimming the entire file beforehand so we
    # can detect blank lines / surrounding whitespace in individual entries.
    lines = raw.split("\n")
    # Allow a single trailing newline by dropping a trailing empty element.
    if lines and lines[-1] == "":
        lines = lines[:-1]

    assert lines, f"{SNAPSHOTS_FILE} must not be empty."
    assert len(lines) == len(expected_ids), (
        f"{SNAPSHOTS_FILE} has {len(lines)} line(s) but the CLI reports "
        f"{len(expected_ids)} snapshot(s). File contents: {raw!r}; "
        f"expected IDs (oldest first): {expected_ids!r}"
    )

    for idx, (actual, expected) in enumerate(zip(lines, expected_ids)):
        assert actual == expected, (
            f"Line {idx + 1} of {SNAPSHOTS_FILE} must be exactly the "
            f"snapshot version '{expected}' (oldest-first ordering); got "
            f"{actual!r}. Full file: {raw!r}"
        )


def test_snapshots_file_has_no_blank_or_whitespace_lines():
    with open(SNAPSHOTS_FILE) as f:
        raw = f.read()
    lines = raw.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    for idx, line in enumerate(lines):
        assert line.strip() == line and line != "", (
            f"Line {idx + 1} of {SNAPSHOTS_FILE} must contain only the "
            f"snapshot ID with no surrounding whitespace and no blank "
            f"lines. Got: {line!r}"
        )
        assert line.isdigit() or all(c.isalnum() or c in "-_" for c in line), (
            f"Line {idx + 1} of {SNAPSHOTS_FILE} does not look like a "
            f"snapshot version: {line!r}"
        )
