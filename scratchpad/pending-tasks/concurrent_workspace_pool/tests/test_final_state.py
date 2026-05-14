import json
import os
import subprocess

import pytest

PROJECT_DIR = "/home/user/ws-pool"
INDEX_TS = os.path.join(PROJECT_DIR, "index.ts")
POOL_JSON = os.path.join(PROJECT_DIR, "pool.json")
EXPECTED_NAMES = {"pool-agent-1", "pool-agent-2", "pool-agent-3", "pool-agent-4"}


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
def script_run():
    """Execute `npx tsx index.ts` once and capture the result for downstream assertions."""
    assert os.path.isfile(INDEX_TS), (
        f"Expected the user-implemented script at {INDEX_TS}, but it does not exist."
    )
    result = subprocess.run(
        ["npx", "tsx", "index.ts"],
        capture_output=True,
        text=True,
        cwd=PROJECT_DIR,
        timeout=300,
    )
    return result


@pytest.fixture(scope="module")
def pool_data(script_run):
    assert os.path.isfile(POOL_JSON), (
        f"pool.json was not created at {POOL_JSON}. Script stdout: {script_run.stdout[:500]} stderr: {script_run.stderr[:500]}"
    )
    with open(POOL_JSON) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as exc:
            pytest.fail(f"pool.json is not valid JSON: {exc}")


@pytest.fixture(scope="module", autouse=True)
def cleanup_buckets(pool_data):
    """Best-effort cleanup so no buckets leak across runs even if the script's teardown failed."""
    yield
    if not isinstance(pool_data, list):
        return
    env = _tigris_env()
    for entry in pool_data:
        if not isinstance(entry, dict):
            continue
        bucket = entry.get("bucket")
        if not isinstance(bucket, str) or not bucket:
            continue
        subprocess.run(
            ["tigris", "buckets", "delete", bucket],
            capture_output=True,
            text=True,
            env=env,
        )


def test_script_exits_zero(script_run):
    assert script_run.returncode == 0, (
        f"`npx tsx index.ts` exited with status {script_run.returncode}. "
        f"stdout: {script_run.stdout[:1000]}\nstderr: {script_run.stderr[:1000]}"
    )


def test_pool_json_is_list_of_four(pool_data):
    assert isinstance(pool_data, list), (
        f"pool.json must be a JSON array, got: {type(pool_data).__name__}"
    )
    assert len(pool_data) == 4, (
        f"pool.json must contain exactly 4 entries, got: {len(pool_data)}"
    )


def test_pool_entries_have_required_keys(pool_data):
    for idx, entry in enumerate(pool_data):
        assert isinstance(entry, dict), (
            f"pool.json entry {idx} must be an object, got: {type(entry).__name__}"
        )
        assert "name" in entry and isinstance(entry["name"], str) and entry["name"], (
            f"pool.json entry {idx} must have a non-empty 'name' string, got: {entry!r}"
        )
        assert "bucket" in entry and isinstance(entry["bucket"], str) and entry["bucket"], (
            f"pool.json entry {idx} must have a non-empty 'bucket' string, got: {entry!r}"
        )


def test_pool_names_match_expected(pool_data):
    names = [entry["name"] for entry in pool_data if isinstance(entry, dict)]
    assert set(names) == EXPECTED_NAMES, (
        f"pool.json names must exactly cover {sorted(EXPECTED_NAMES)}, got: {sorted(names)}"
    )
    assert len(names) == len(set(names)), (
        f"pool.json names must be unique, got duplicates in: {names}"
    )


def test_index_ts_uses_promise_all_for_creation():
    with open(INDEX_TS) as f:
        source = f.read()
    assert "Promise.all" in source, (
        "index.ts must invoke Promise.all to provision the four workspaces in parallel."
    )


def test_index_ts_uses_promise_all_settled_for_teardown():
    with open(INDEX_TS) as f:
        source = f.read()
    assert "Promise.allSettled" in source, (
        "index.ts must invoke Promise.allSettled when tearing down workspaces so partial failures don't break others."
    )


def test_all_buckets_torn_down_via_cli(pool_data):
    """Priority 1: Use the tigris CLI to confirm every workspace bucket has been deleted."""
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

    raw_output = result.stdout
    for entry in pool_data:
        if not isinstance(entry, dict):
            continue
        bucket = entry.get("bucket")
        if not isinstance(bucket, str) or not bucket:
            continue
        assert bucket not in names and bucket not in raw_output, (
            f"Bucket {bucket!r} is still present after teardown; "
            f"all four pool workspaces must be deleted via Promise.allSettled([teardownWorkspace(...), ...])."
        )
