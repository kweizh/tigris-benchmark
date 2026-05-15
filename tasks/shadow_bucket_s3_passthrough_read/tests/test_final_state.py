import json
import os
import subprocess
import time

import pytest

PROJECT_DIR = "/home/user/tigris-task"
LOCAL_TARGET = os.path.join(PROJECT_DIR, "proxied.md")
TRIAL_ID_PATH = "/logs/artifacts/trial_id"
EXPECTED_BYTES = b"from origin"
TIGRIS_ENDPOINT = "https://t3.storage.dev"


def _tigris_env():
    """Map Harbor's TIGRIS_STORAGE_* credentials onto the AWS-compatible
    variables consumed by both the `tigris` CLI and the `aws` CLI."""
    env = os.environ.copy()
    access_key = os.environ.get("TIGRIS_STORAGE_ACCESS_KEY_ID")
    secret_key = os.environ.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY")
    assert access_key, "TIGRIS_STORAGE_ACCESS_KEY_ID is not set in the verifier environment."
    assert secret_key, "TIGRIS_STORAGE_SECRET_ACCESS_KEY is not set in the verifier environment."
    env["AWS_ACCESS_KEY_ID"] = access_key
    env["AWS_SECRET_ACCESS_KEY"] = secret_key
    env.setdefault("AWS_REGION", "auto")
    env.setdefault("AWS_DEFAULT_REGION", "auto")
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


def _run_aws(args, timeout=120):
    return subprocess.run(
        ["aws", *args],
        capture_output=True,
        text=True,
        env=_tigris_env(),
        cwd=PROJECT_DIR,
        timeout=timeout,
    )


def _read_trial_id():
    assert os.path.isfile(TRIAL_ID_PATH), (
        f"Expected trial id file at {TRIAL_ID_PATH} to exist."
    )
    with open(TRIAL_ID_PATH) as f:
        trial_id = f.read().strip()
    assert trial_id, f"{TRIAL_ID_PATH} must contain a non-empty trial id."
    return trial_id


def _origin_bucket():
    return f"harbor-origin-{_read_trial_id()}"


def _shadow_bucket():
    return f"harbor-shadow-{_read_trial_id()}"


@pytest.fixture(scope="module", autouse=True)
def cleanup_buckets_after_tests():
    """Yield to the tests, then delete BOTH the shadow and origin buckets so
    subsequent runs are clean. Best-effort: ignore failures if the buckets
    are already gone."""
    yield
    try:
        shadow = _shadow_bucket()
        origin = _origin_bucket()
    except AssertionError:
        return
    # Delete shadow first so the migration configuration is torn down before
    # we delete the origin (which the shadow references).
    _run_tigris(["buckets", "delete", shadow, "--force", "--yes"], timeout=180)
    _run_tigris(["buckets", "delete", origin, "--force", "--yes"], timeout=180)


def test_local_file_exists():
    assert os.path.isfile(LOCAL_TARGET), (
        f"Expected the agent to have downloaded the object to {LOCAL_TARGET} "
        "via the shadow read-through, but the file does not exist."
    )


def test_local_file_content_matches_exact_bytes():
    """Read the local file and verify its bytes equal EXACTLY `from origin`
    (11 bytes, no trailing newline). This proves the shadow bucket served the
    origin's content."""
    assert os.path.isfile(LOCAL_TARGET), (
        f"Local file {LOCAL_TARGET} is missing; cannot verify content."
    )
    with open(LOCAL_TARGET, "rb") as f:
        contents = f.read()
    assert contents == EXPECTED_BYTES, (
        f"Expected {LOCAL_TARGET} to contain exactly {EXPECTED_BYTES!r} "
        f"({len(EXPECTED_BYTES)} bytes), got {contents!r} ({len(contents)} bytes)."
    )


def test_shadow_bucket_created_by_agent():
    """Priority 1: confirm the agent created the shadow bucket."""
    shadow = _shadow_bucket()
    result = _run_tigris(["buckets", "get", shadow])
    assert result.returncode == 0, (
        f"'tigris buckets get {shadow}' failed: returncode="
        f"{result.returncode} stderr={result.stderr!r} stdout={result.stdout!r}. "
        "The agent must have created the shadow bucket."
    )


def test_both_buckets_present_in_listing():
    """Priority 1: both the origin (pre-seeded) and the shadow (agent-created)
    buckets must be visible in the account."""
    shadow = _shadow_bucket()
    origin = _origin_bucket()
    result = _run_tigris(["buckets", "list", "--format", "json"])
    assert result.returncode == 0, (
        f"'tigris buckets list --format json' failed: returncode="
        f"{result.returncode} stderr={result.stderr!r} stdout={result.stdout!r}"
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"'tigris buckets list --format json' did not return valid JSON: "
            f"{exc}. stdout={result.stdout!r}"
        )
    if isinstance(payload, dict):
        buckets = payload.get("items", []) or payload.get("buckets", []) or []
    else:
        buckets = payload
    names = [b.get("name") for b in buckets if isinstance(b, dict)]
    assert origin in names, (
        f"Expected origin bucket {origin!r} to still exist in the account "
        f"(agent must NOT delete it). Got: {names}"
    )
    assert shadow in names, (
        f"Expected agent-created shadow bucket {shadow!r} to exist. Got: {names}"
    )


def test_origin_object_still_present():
    """Priority 1: the source object in the origin bucket must NOT have been
    deleted or moved by the agent."""
    origin = _origin_bucket()
    result = _run_tigris(["ls", f"t3://{origin}/docs/readme.md"])
    assert result.returncode == 0, (
        f"'tigris ls t3://{origin}/docs/readme.md' failed: returncode="
        f"{result.returncode} stderr={result.stderr!r} stdout={result.stdout!r}. "
        "The agent must NOT have moved or deleted the origin object."
    )
    assert "readme.md" in result.stdout, (
        f"Expected 'readme.md' in the origin listing under t3://{origin}/docs/, "
        f"but got:\n{result.stdout}"
    )


def test_shadow_bucket_serves_object_via_aws_cli():
    """Priority 1: independently verify that the shadow bucket serves the
    object via the AWS CLI (this exercises the shadow read-through end-to-end
    from the verifier's perspective)."""
    shadow = _shadow_bucket()
    tmp_out = "/tmp/verifier_proxied.md"
    if os.path.exists(tmp_out):
        os.remove(tmp_out)
    result = _run_aws([
        "s3", "cp",
        f"s3://{shadow}/docs/readme.md",
        tmp_out,
        "--endpoint-url", TIGRIS_ENDPOINT,
        "--region", "auto",
    ])
    assert result.returncode == 0, (
        f"'aws s3 cp s3://{shadow}/docs/readme.md' failed: returncode="
        f"{result.returncode} stderr={result.stderr!r} stdout={result.stdout!r}. "
        "The shadow bucket must serve the object via read-through from the origin."
    )
    assert os.path.isfile(tmp_out), (
        f"Verifier expected {tmp_out} to exist after `aws s3 cp` from the "
        "shadow bucket, but it does not."
    )
    with open(tmp_out, "rb") as f:
        contents = f.read()
    assert contents == EXPECTED_BYTES, (
        f"Expected the shadow read-through to return exactly {EXPECTED_BYTES!r}, "
        f"got {contents!r}."
    )


def test_shadow_bucket_materializes_object_after_read():
    """Priority 1: Per https://www.tigrisdata.com/docs/migration/ — with
    write-through DISABLED, the list API only includes objects that have been
    accessed and asynchronously materialized into the Tigris bucket. Because
    the agent (and the previous test) read `docs/readme.md` via the shadow
    bucket, the asynchronous materialization should eventually surface the
    object in `aws s3 ls --recursive`. Poll for up to 60 seconds."""
    shadow = _shadow_bucket()
    deadline = time.time() + 60.0
    last_stdout = ""
    last_stderr = ""
    last_rc = None
    while time.time() < deadline:
        result = _run_aws([
            "s3", "ls", "--recursive",
            f"s3://{shadow}/",
            "--endpoint-url", TIGRIS_ENDPOINT,
            "--region", "auto",
        ])
        last_stdout = result.stdout
        last_stderr = result.stderr
        last_rc = result.returncode
        if result.returncode == 0 and "docs/readme.md" in result.stdout:
            return
        time.sleep(3)
    pytest.fail(
        "Expected `aws s3 ls --recursive s3://"
        f"{shadow}/` to eventually list `docs/readme.md` after the agent's "
        "shadow read-through (Tigris asynchronously materializes accessed "
        "objects). Final returncode="
        f"{last_rc!r} stderr={last_stderr!r} stdout={last_stdout!r}"
    )
