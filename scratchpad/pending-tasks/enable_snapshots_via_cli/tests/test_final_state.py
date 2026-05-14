import os
import re
import shutil
import subprocess

import pytest

BUCKET_NAME = "agent-corpus"


@pytest.fixture(scope="module", autouse=True)
def configure_tigris_cli():
    """Authenticate the Tigris CLI for the verifier session.

    Uses the same TIGRIS_STORAGE_ACCESS_KEY_ID / TIGRIS_STORAGE_SECRET_ACCESS_KEY
    env vars that were available to the task environment.
    """
    access_key = os.environ.get("TIGRIS_STORAGE_ACCESS_KEY_ID")
    secret_key = os.environ.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY")
    assert access_key, (
        "TIGRIS_STORAGE_ACCESS_KEY_ID is not set in the verifier environment."
    )
    assert secret_key, (
        "TIGRIS_STORAGE_SECRET_ACCESS_KEY is not set in the verifier environment."
    )
    assert shutil.which("tigris") is not None, (
        "Tigris CLI binary `tigris` not found in PATH for the verifier."
    )

    result = subprocess.run(
        [
            "tigris",
            "configure",
            "--access-key",
            access_key,
            "--access-secret",
            secret_key,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"`tigris configure` failed in the verifier: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    yield


def _run_tigris(args):
    """Run a tigris CLI command, returning the CompletedProcess."""
    return subprocess.run(
        ["tigris", *args],
        capture_output=True,
        text=True,
    )


def test_bucket_still_exists_in_list():
    """Priority 1 (CLI): `agent-corpus` must appear in `tigris buckets list`."""
    result = _run_tigris(["buckets", "list"])
    assert result.returncode == 0, (
        f"`tigris buckets list` failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert BUCKET_NAME in result.stdout, (
        f"Expected bucket '{BUCKET_NAME}' to be present in `tigris buckets list` output. "
        f"Got: {result.stdout!r}"
    )


def test_bucket_get_succeeds():
    """Priority 1 (CLI): `tigris buckets get agent-corpus` must succeed."""
    result = _run_tigris(["buckets", "get", BUCKET_NAME])
    assert result.returncode == 0, (
        f"`tigris buckets get {BUCKET_NAME}` failed: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_snapshots_enabled_on_bucket():
    """Priority 1 (CLI): the bucket's Snapshots field must indicate 'enabled'.

    Per the Tigris Agent Kit docs:
        Verify by running `tigris buckets get <bucket>` in the CLI —
        the `Snapshots` field should read `enabled`.
    We accept any of: 'Snapshots: enabled', 'Snapshot enabled', 'Snapshots: true',
    'EnableSnapshots: true', or similar JSON/text shapes the CLI may emit.
    """
    result = _run_tigris(["buckets", "get", BUCKET_NAME])
    assert result.returncode == 0, (
        f"`tigris buckets get {BUCKET_NAME}` failed: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )

    combined = (result.stdout + "\n" + result.stderr).lower()

    # Match a few accepted phrasings of "snapshots enabled".
    patterns = [
        r"snapshots?\s*[:=]\s*enabled",
        r"snapshots?\s*[:=]\s*true",
        r"enable[_-]?snapshots?\s*[:=]\s*true",
        r"snapshots?\s+enabled",
        r'"snapshots?"\s*:\s*"?enabled"?',
        r'"snapshots?"\s*:\s*true',
        r'"enablesnapshots?"\s*:\s*true',
    ]
    matched = any(re.search(p, combined) for p in patterns)
    assert matched, (
        "Expected `tigris buckets get agent-corpus` output to indicate that "
        "snapshots are ENABLED on the bucket (e.g., 'Snapshots: enabled'). "
        f"Got: {result.stdout!r} / stderr={result.stderr!r}"
    )
