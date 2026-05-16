import json
import os
import subprocess

import pytest

PROJECT_DIR = "/home/user/lifecycle"
RUN_SCRIPT = os.path.join(PROJECT_DIR, "run.sh")
SNAPSHOTS_FILE = os.path.join(PROJECT_DIR, "snapshots.txt")
BUCKET_NAME = "lifecycle-demo"


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


def _bucket_exists(name):
    result = _run_tigris(["buckets", "list", "--format", "json"])
    if result.returncode != 0:
        pytest.fail(
            f"'tigris buckets list --format json' failed during verification: "
            f"returncode={result.returncode}, stderr={result.stderr!r}"
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
    return any(
        isinstance(b, dict) and b.get("name") == name for b in buckets
    )


@pytest.fixture(scope="module", autouse=True)
def execute_run_script():
    """Pre-clean any stale bucket, run the agent's `run.sh`, then ensure the
    bucket is removed afterwards regardless of what the script did."""
    # Best-effort pre-clean — ignore failures (bucket may not exist).
    _run_tigris(["buckets", "delete", BUCKET_NAME, "--yes"], timeout=120)

    assert os.path.isfile(RUN_SCRIPT), (
        f"Expected {RUN_SCRIPT} to exist after the agent finished. The agent "
        "must author this script."
    )

    proc = subprocess.run(
        ["bash", "run.sh"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        env=_tigris_env(),
        timeout=300,
    )
    # Expose the captured output on the fixture so tests can reference it.
    yield proc

    # Final cleanup — make subsequent runs idempotent even if the agent's
    # cleanup step was missing or failed mid-way.
    _run_tigris(["buckets", "delete", BUCKET_NAME, "--yes"], timeout=120)


def test_run_script_exits_zero(execute_run_script):
    proc = execute_run_script
    assert proc.returncode == 0, (
        f"`bash run.sh` exited with status {proc.returncode}. "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )


def test_snapshots_file_exists(execute_run_script):
    assert os.path.isfile(SNAPSHOTS_FILE), (
        f"Expected snapshot ID file {SNAPSHOTS_FILE} to exist after `run.sh` "
        "completed."
    )


def test_snapshots_file_has_at_least_one_line(execute_run_script):
    with open(SNAPSHOTS_FILE) as f:
        contents = f.read()
    non_empty_lines = [
        line for line in contents.split("\n") if line.strip() != ""
    ]
    assert len(non_empty_lines) >= 1, (
        f"Expected {SNAPSHOTS_FILE} to contain at least one non-empty snapshot "
        f"version line; got contents={contents!r}."
    )


def test_bucket_was_deleted_at_end(execute_run_script):
    """Priority 1: the script's final step must delete the bucket so the run
    is self-cleaning."""
    assert not _bucket_exists(BUCKET_NAME), (
        f"Bucket {BUCKET_NAME!r} still exists after `run.sh` finished. The "
        "script must delete the bucket as its final cleanup step."
    )
