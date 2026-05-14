import json
import os
import subprocess

import pytest

BUCKET_NAME = "eval-gold-corpus"
PROJECT_DIR = "/home/user/bucket-create"


def _tigris_env():
    """Map Harbor's TIGRIS_STORAGE_* credentials onto the AWS-compatible
    variables consumed by the `tigris` CLI."""
    env = os.environ.copy()
    access_key = os.environ.get("TIGRIS_STORAGE_ACCESS_KEY_ID")
    secret_key = os.environ.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY")
    assert access_key, "TIGRIS_STORAGE_ACCESS_KEY_ID is not set in the verifier environment."
    assert secret_key, "TIGRIS_STORAGE_SECRET_ACCESS_KEY is not set in the verifier environment."
    env["AWS_ACCESS_KEY_ID"] = access_key
    env["AWS_SECRET_ACCESS_KEY"] = secret_key
    env.setdefault("AWS_REGION", "auto")
    return env


def _run_tigris(args, timeout=120):
    return subprocess.run(
        ["tigris", *args],
        capture_output=True,
        text=True,
        env=_tigris_env(),
        cwd=PROJECT_DIR,
        timeout=timeout,
    )


@pytest.fixture(scope="module", autouse=True)
def cleanup_bucket_after_tests():
    """Yield to the tests, then delete the bucket so subsequent runs are clean."""
    yield
    # Best-effort cleanup; do not fail the suite if the bucket is already gone.
    _run_tigris(["buckets", "delete", BUCKET_NAME, "--yes"], timeout=120)


def test_bucket_appears_in_list():
    """Priority 1: confirm via Tigris CLI that the new bucket exists."""
    result = _run_tigris(["buckets", "list", "--format", "json"])
    assert result.returncode == 0, (
        f"'tigris buckets list --format json' failed: returncode="
        f"{result.returncode}, stderr={result.stderr!r}"
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"'tigris buckets list --format json' returned invalid JSON: {exc}. "
            f"stdout={result.stdout!r}"
        )
    if isinstance(payload, dict):
        buckets = payload.get("items", []) or payload.get("buckets", [])
    else:
        buckets = payload
    bucket_names = [b.get("name") for b in buckets if isinstance(b, dict)]
    assert BUCKET_NAME in bucket_names, (
        f"Expected bucket {BUCKET_NAME!r} to be present after the task completed, "
        f"but it was not found. Existing buckets: {bucket_names}"
    )


def test_bucket_has_snapshots_enabled():
    """Priority 1: confirm via Tigris CLI that snapshots are enabled on the bucket."""
    result = _run_tigris(["buckets", "get", BUCKET_NAME, "--format", "json"])
    assert result.returncode == 0, (
        f"'tigris buckets get {BUCKET_NAME} --format json' failed: returncode="
        f"{result.returncode}, stderr={result.stderr!r}"
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"'tigris buckets get {BUCKET_NAME} --format json' returned invalid "
            f"JSON: {exc}. stdout={result.stdout!r}"
        )

    # The CLI emits a list of {"property": label, "value": value} rows for
    # `buckets get --format json`. Locate the "Snapshots Enabled" row.
    rows = payload if isinstance(payload, list) else payload.get("items", [])
    snapshot_row = next(
        (
            row for row in rows
            if isinstance(row, dict) and row.get("property") == "Snapshots Enabled"
        ),
        None,
    )
    assert snapshot_row is not None, (
        "Expected a 'Snapshots Enabled' property in the output of "
        f"'tigris buckets get {BUCKET_NAME} --format json', but it was missing. "
        f"Got rows: {rows!r}"
    )
    assert str(snapshot_row.get("value")).strip().lower() == "yes", (
        f"Expected 'Snapshots Enabled' to be 'Yes' for bucket {BUCKET_NAME!r}, "
        f"but got {snapshot_row.get('value')!r}. The bucket must be created with "
        "the --enable-snapshots flag; this flag cannot be applied after creation."
    )
