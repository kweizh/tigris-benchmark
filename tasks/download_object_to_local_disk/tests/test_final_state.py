import os
import subprocess

import pytest

PROJECT_DIR = "/home/user/tigris-task"
LOCAL_TARGET = os.path.join(PROJECT_DIR, "welcome.md")
TRIAL_ID_PATH = "/logs/artifacts/trial_id"
EXPECTED_BYTES = b"# Welcome to Tigris\n"


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


def _bucket_name():
    assert os.path.isfile(TRIAL_ID_PATH), (
        f"Expected trial id file at {TRIAL_ID_PATH} to exist."
    )
    with open(TRIAL_ID_PATH) as f:
        trial_id = f.read().strip()
    assert trial_id, f"{TRIAL_ID_PATH} must contain a non-empty trial id."
    import re
    name = f"harbor-download-{trial_id}"
    name = re.sub(r"[^a-z0-9.-]", "-", name.lower())
    return name


@pytest.fixture(scope="module", autouse=True)
def cleanup_bucket_after_tests():
    """Yield to the tests, then delete the per-trial bucket so subsequent runs
    are clean. Best-effort: ignore failures if the bucket is already gone."""
    yield
    try:
        bucket = _bucket_name()
    except AssertionError:
        return
    _run_tigris(["buckets", "delete", bucket, "--force", "--yes"], timeout=180)


def test_local_file_exists():
    assert os.path.isfile(LOCAL_TARGET), (
        f"Expected the agent to have downloaded the object to {LOCAL_TARGET}, "
        "but the file does not exist."
    )


def test_local_file_content_matches_exact_bytes():
    """Priority 3: read the local file and verify its bytes equal EXACTLY
    `# Welcome to Tigris\\n`."""
    assert os.path.isfile(LOCAL_TARGET), (
        f"Local file {LOCAL_TARGET} is missing; cannot verify content."
    )
    with open(LOCAL_TARGET, "rb") as f:
        contents = f.read()
    assert contents == EXPECTED_BYTES, (
        f"Expected {LOCAL_TARGET} to contain exactly {EXPECTED_BYTES!r} "
        f"({len(EXPECTED_BYTES)} bytes), got {contents!r} ({len(contents)} bytes)."
    )


def test_source_object_still_present_in_bucket():
    """Priority 1: use the Tigris CLI to confirm the source object was NOT
    deleted/moved by the agent — `tigris ls` on the exact object key must
    still succeed and reference the key."""
    bucket = _bucket_name()
    result = _run_tigris(["ls", f"t3://{bucket}/assets/welcome.md"])
    assert result.returncode == 0, (
        f"'tigris ls t3://{bucket}/assets/welcome.md' failed: returncode="
        f"{result.returncode} stderr={result.stderr!r} stdout={result.stdout!r}. "
        "The agent must NOT have moved or deleted the source object."
    )
    assert "welcome.md" in result.stdout, (
        f"Expected 'welcome.md' to appear in the listing for "
        f"t3://{bucket}/assets/welcome.md, but it was not in stdout:\n"
        f"{result.stdout}"
    )


def test_source_object_still_listed_under_assets_prefix():
    """Priority 1: also verify via a prefix-scoped `tigris ls` that the source
    object is still discoverable under the `assets/` prefix."""
    bucket = _bucket_name()
    result = _run_tigris(["ls", f"t3://{bucket}/assets/"])
    assert result.returncode == 0, (
        f"'tigris ls t3://{bucket}/assets/' failed: returncode="
        f"{result.returncode} stderr={result.stderr!r} stdout={result.stdout!r}"
    )
    assert "welcome.md" in result.stdout, (
        f"Expected 'welcome.md' to be listed under t3://{bucket}/assets/ "
        f"after the agent finished, but got:\n{result.stdout}"
    )
