import json
import os
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

PROJECT_DIR = "/home/user/ttl-workspace"
WORKSPACE_JSON = os.path.join(PROJECT_DIR, "workspace.json")
EXPECTED_TTL_DAYS = 7
TTL_TOLERANCE = timedelta(minutes=5)


def _tigris_env():
    """Map Tigris credentials to AWS-style env vars the tigris CLI expects."""
    env = os.environ.copy()
    access_key = os.environ.get("TIGRIS_STORAGE_ACCESS_KEY_ID")
    secret_key = os.environ.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY")
    assert access_key, (
        "TIGRIS_STORAGE_ACCESS_KEY_ID is not set in the verifier environment."
    )
    assert secret_key, (
        "TIGRIS_STORAGE_SECRET_ACCESS_KEY is not set in the verifier environment."
    )
    env["AWS_ACCESS_KEY_ID"] = access_key
    env["AWS_SECRET_ACCESS_KEY"] = secret_key
    env.setdefault("AWS_REGION", "auto")
    return env


@pytest.fixture(scope="module")
def workspace_data():
    assert os.path.isfile(WORKSPACE_JSON), (
        f"workspace.json was not created at {WORKSPACE_JSON}."
    )
    with open(WORKSPACE_JSON) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"workspace.json at {WORKSPACE_JSON} is not valid JSON: {exc}"
            )
    return data


@pytest.fixture(scope="module", autouse=True)
def teardown_bucket(workspace_data):
    """Always tear down the provisioned bucket after the module's tests run."""
    yield
    bucket = workspace_data.get("bucket") if isinstance(workspace_data, dict) else None
    if not bucket:
        return
    env = _tigris_env()
    subprocess.run(
        ["tigris", "buckets", "delete", bucket],
        capture_output=True,
        text=True,
        env=env,
    )


def test_workspace_json_has_required_keys(workspace_data):
    assert isinstance(workspace_data, dict), (
        f"workspace.json should be a JSON object, got: {type(workspace_data).__name__}"
    )
    assert "bucket" in workspace_data, (
        "workspace.json is missing required key 'bucket'."
    )
    assert "expires_at" in workspace_data, (
        "workspace.json is missing required key 'expires_at'."
    )
    assert isinstance(workspace_data["bucket"], str) and workspace_data["bucket"], (
        f"'bucket' must be a non-empty string, got: {workspace_data['bucket']!r}"
    )
    assert isinstance(workspace_data["expires_at"], str) and workspace_data["expires_at"], (
        f"'expires_at' must be a non-empty string, got: {workspace_data['expires_at']!r}"
    )


def test_bucket_appears_in_tigris_list(workspace_data):
    """Priority 1: Use the tigris CLI to confirm the bucket exists."""
    bucket = workspace_data["bucket"]
    env = _tigris_env()
    result = subprocess.run(
        ["tigris", "buckets", "list", "--format", "json"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, (
        f"`tigris buckets list --format json` failed: {result.stderr.strip() or result.stdout.strip()}"
    )
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"`tigris buckets list --format json` returned invalid JSON: {exc}\nOutput: {result.stdout[:500]}"
        )

    # Normalise different possible shapes of the JSON listing into a list of bucket names.
    candidates = []
    if isinstance(parsed, list):
        candidates = parsed
    elif isinstance(parsed, dict):
        for key in ("buckets", "Buckets", "items", "data"):
            value = parsed.get(key)
            if isinstance(value, list):
                candidates = value
                break

    names = set()
    for entry in candidates:
        if isinstance(entry, str):
            names.add(entry)
        elif isinstance(entry, dict):
            for key in ("name", "Name", "bucket", "Bucket"):
                if isinstance(entry.get(key), str):
                    names.add(entry[key])
                    break

    # Fallback: the raw stdout itself is searched for the bucket name in case parsing missed nested fields.
    if bucket not in names:
        assert bucket in result.stdout, (
            f"Expected bucket {bucket!r} to appear in `tigris buckets list --format json` output. "
            f"Parsed names: {sorted(names)!r}. Raw output: {result.stdout[:500]}"
        )


def test_bucket_get_succeeds(workspace_data):
    """Priority 1: `tigris buckets get <bucket>` must succeed for the recorded bucket."""
    bucket = workspace_data["bucket"]
    env = _tigris_env()
    result = subprocess.run(
        ["tigris", "buckets", "get", bucket],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, (
        f"`tigris buckets get {bucket}` failed (rc={result.returncode}): "
        f"{result.stderr.strip() or result.stdout.strip()}"
    )


def test_expires_at_is_seven_days_from_now(workspace_data):
    """Verify the recorded expires_at is ~7 days from the current wall-clock time (±5 min)."""
    expires_at_str = workspace_data["expires_at"]
    # Accept both 'Z' and explicit offset forms.
    normalised = expires_at_str.replace("Z", "+00:00")
    try:
        expires_at = datetime.fromisoformat(normalised)
    except ValueError as exc:
        pytest.fail(
            f"'expires_at' value {expires_at_str!r} is not a valid ISO 8601 timestamp: {exc}"
        )
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    expected = now + timedelta(days=EXPECTED_TTL_DAYS)
    delta = expires_at - expected
    assert abs(delta) <= TTL_TOLERANCE, (
        f"expires_at ({expires_at.isoformat()}) is not within {TTL_TOLERANCE} of "
        f"7 days from now ({expected.isoformat()}); actual delta: {delta}."
    )
