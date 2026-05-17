import json
import os
import subprocess

import pytest

PROJECT_DIR = "/home/user/tigris-task"
LISTING_FILE = os.path.join(PROJECT_DIR, "logs-listing.txt")
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
    name = f"harbor-prefix-{trial_id}"
    name = re.sub(r"[^a-z0-9.-]", "-", name.lower())
    return name


@pytest.fixture(scope="module", autouse=True)
def cleanup_bucket_after_tests():
    """Yield to the tests, then delete the bucket so subsequent runs are clean."""
    yield
    try:
        bucket = _bucket_name()
    except AssertionError:
        return
    # Best-effort cleanup; the bucket still contains objects, so `--force` is
    # required to drop it. Ignore failures if the bucket is already gone.
    _run_tigris(["buckets", "delete", bucket, "--force", "--yes"], timeout=180)


def _parse_ls_keys(stdout):
    """Parse `tigris ls` text output into the set of object keys present."""
    keys = set()
    for raw in stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        if "│" in line:
            parts = line.split("│")
            if len(parts) > 1:
                key = parts[1].strip()
                if key.endswith(".txt"):
                    keys.add(key)
        else:
            token = line.split()[-1]
            if token.endswith(".txt"):
                keys.add(token)
    return keys


def test_logs_prefix_has_exactly_two_objects():
    """Priority 1: Use the Tigris CLI to list the `logs/` prefix and confirm
    exactly two objects ending in logs/a.txt and logs/b.txt."""
    bucket = _bucket_name()
    result = _run_tigris(["ls", f"t3://{bucket}/logs/"])
    assert result.returncode == 0, (
        f"'tigris ls t3://{bucket}/logs/' failed: returncode="
        f"{result.returncode}, stderr={result.stderr!r}, stdout={result.stdout!r}"
    )
    keys = _parse_ls_keys(result.stdout)
    assert len(keys) == 2, (
        f"Expected exactly 2 objects under logs/ prefix in bucket {bucket}, "
        f"got {len(keys)} keys: {sorted(keys)}. Raw output:\n{result.stdout}"
    )
    has_a = any(k.endswith("logs/a.txt") or k == "a.txt" for k in keys)
    has_b = any(k.endswith("logs/b.txt") or k == "b.txt" for k in keys)
    assert has_a, (
        f"Expected an object key ending in 'logs/a.txt' in bucket {bucket}. "
        f"Got keys: {sorted(keys)}"
    )
    assert has_b, (
        f"Expected an object key ending in 'logs/b.txt' in bucket {bucket}. "
        f"Got keys: {sorted(keys)}"
    )
    # The `logs/` listing must NEVER include c.txt (which belongs to data/).
    for k in keys:
        assert not k.endswith("c.txt"), (
            f"Object key {k!r} unexpectedly appeared under the logs/ prefix; "
            f"c.txt should only exist under the data/ prefix."
        )


def test_data_prefix_has_exactly_one_object():
    """Priority 1: Use the Tigris CLI to list the `data/` prefix and confirm
    exactly one object ending in data/c.txt."""
    bucket = _bucket_name()
    result = _run_tigris(["ls", f"t3://{bucket}/data/"])
    assert result.returncode == 0, (
        f"'tigris ls t3://{bucket}/data/' failed: returncode="
        f"{result.returncode}, stderr={result.stderr!r}, stdout={result.stdout!r}"
    )
    keys = _parse_ls_keys(result.stdout)
    assert len(keys) == 1, (
        f"Expected exactly 1 object under data/ prefix in bucket {bucket}, "
        f"got {len(keys)} keys: {sorted(keys)}. Raw output:\n{result.stdout}"
    )
    only = next(iter(keys))
    assert only.endswith("data/c.txt") or only == "c.txt", (
        f"Expected the single object under data/ to end in 'data/c.txt', "
        f"got {only!r}."
    )


def test_listing_file_saved_and_correct():
    """Priority 3 fallback: verify the saved listing file exists and contains
    only the logs/ prefix object keys."""
    assert os.path.isfile(LISTING_FILE), (
        f"Expected the agent to save the prefix listing to {LISTING_FILE}, "
        "but the file is missing."
    )
    with open(LISTING_FILE) as f:
        content = f.read()
    assert content.strip(), (
        f"{LISTING_FILE} exists but is empty. The agent must save the full "
        "stdout of `tigris ls t3://<bucket>/logs/` to this file."
    )
    assert "a.txt" in content, (
        f"Expected {LISTING_FILE} to contain 'a.txt'. Got:\n{content}"
    )
    assert "b.txt" in content, (
        f"Expected {LISTING_FILE} to contain 'b.txt'. Got:\n{content}"
    )
    assert "c.txt" not in content, (
        f"{LISTING_FILE} must NOT contain 'c.txt' — the listing should be "
        f"scoped to the logs/ prefix, but data/c.txt appears in the saved "
        f"output:\n{content}"
    )
