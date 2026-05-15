import json
import os
import subprocess

import pytest

PROJECT_DIR = "/home/user/cleanup-task"
TRIAL_ID_PATH = "/logs/artifacts/trial_id"


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


def _trial_id():
    assert os.path.isfile(TRIAL_ID_PATH), (
        f"Expected trial id file at {TRIAL_ID_PATH} to exist for the verifier."
    )
    with open(TRIAL_ID_PATH) as f:
        value = f.read().strip()
    assert value, f"Trial id file {TRIAL_ID_PATH} is empty."
    return value


def _bucket_name():
    return f"harbor-cleanup-{_trial_id()}"


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
def defensive_bucket_cleanup():
    """Yield to the tests, then best-effort delete the bucket so the Tigris
    account is restored to a clean state even if the agent failed to delete
    the bucket itself. The Tigris CLI requires empty buckets, so this fixture
    first empties any residual objects with `tigris rm -r` before issuing the
    delete."""
    yield
    bucket_name = _bucket_name()
    # Best-effort cleanup; do not fail the suite if the bucket is already gone.
    _run_tigris(["rm", "-r", f"t3://{bucket_name}/"], timeout=120)
    _run_tigris(["buckets", "delete", bucket_name, "--force"], timeout=120)


def test_bucket_is_absent_from_list():
    """Priority 1: confirm via Tigris CLI that the seeded bucket has been
    removed from the account."""
    bucket_name = _bucket_name()
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
    assert bucket_name not in bucket_names, (
        f"Expected bucket {bucket_name!r} to be ABSENT after the task completed, "
        f"but it was still found in the account. Existing buckets: {bucket_names}"
    )
