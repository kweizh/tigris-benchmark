import json
import os
import re
import subprocess

import pytest

PROJECT_DIR = "/home/user/pool"
MANAGER_TS = os.path.join(PROJECT_DIR, "manager.ts")
CLI_TS = os.path.join(PROJECT_DIR, "cli.ts")
POOL_STATE = os.path.join(PROJECT_DIR, "pool-state.json")
SCENARIO_LOG = os.path.join(PROJECT_DIR, "scenario.log")
EXPECTED_POOL_SIZE = 3


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
def scenario_log_text():
    assert os.path.isfile(SCENARIO_LOG), (
        f"scenario.log was not created at {SCENARIO_LOG}; the four-step CLI scenario must produce it."
    )
    with open(SCENARIO_LOG) as f:
        text = f.read()
    assert text.strip(), f"scenario.log at {SCENARIO_LOG} is empty."
    return text


@pytest.fixture(scope="module")
def pool_buckets_from_log(scenario_log_text):
    """Parse the `status` step's output out of scenario.log: a `pool size: N` line
    followed by N non-empty bucket-name lines."""
    lines = scenario_log_text.splitlines()
    pool_line_idx = None
    for idx, line in enumerate(lines):
        if line.strip() == f"pool size: {EXPECTED_POOL_SIZE}":
            pool_line_idx = idx
            break
    assert pool_line_idx is not None, (
        f"scenario.log must contain a line exactly equal to 'pool size: {EXPECTED_POOL_SIZE}'. "
        f"Got log:\n{scenario_log_text}"
    )
    bucket_lines = []
    for line in lines[pool_line_idx + 1 : pool_line_idx + 1 + EXPECTED_POOL_SIZE]:
        stripped = line.strip()
        assert stripped, (
            f"Expected {EXPECTED_POOL_SIZE} non-empty bucket-name lines immediately after "
            f"'pool size: {EXPECTED_POOL_SIZE}'. Got blank line at offset {len(bucket_lines)}.\n"
            f"Full log:\n{scenario_log_text}"
        )
        # A bucket name should look like a plausible Tigris bucket: not start with `pool size:`,
        # not contain spaces.
        assert " " not in stripped, (
            f"Bucket-name line {stripped!r} should be a single bucket name (no spaces)."
        )
        assert not stripped.lower().startswith("pool size"), (
            f"Bucket-name slot contains another 'pool size' line: {stripped!r}."
        )
        bucket_lines.append(stripped)
    assert len(bucket_lines) == EXPECTED_POOL_SIZE, (
        f"Expected exactly {EXPECTED_POOL_SIZE} bucket-name lines after 'pool size: {EXPECTED_POOL_SIZE}', "
        f"got {len(bucket_lines)}."
    )
    return bucket_lines


@pytest.fixture(scope="module", autouse=True)
def cleanup_buckets(pool_buckets_from_log):
    """Best-effort cleanup so no buckets leak across runs even if the agent's teardown failed."""
    yield
    env = _tigris_env()
    for bucket in pool_buckets_from_log:
        subprocess.run(
            ["tigris", "buckets", "delete", bucket],
            capture_output=True,
            text=True,
            env=env,
        )


def test_manager_ts_exists():
    assert os.path.isfile(MANAGER_TS), (
        f"Expected the user-implemented manager at {MANAGER_TS}, but it does not exist."
    )


def test_cli_ts_exists():
    assert os.path.isfile(CLI_TS), (
        f"Expected the user-implemented CLI entrypoint at {CLI_TS}, but it does not exist."
    )


def test_manager_uses_promise_all_for_provisioning():
    with open(MANAGER_TS) as f:
        source = f.read()
    assert "Promise.all" in source, (
        "manager.ts must invoke Promise.all to provision workspaces concurrently."
    )


def test_manager_uses_promise_all_settled_for_teardown():
    with open(MANAGER_TS) as f:
        source = f.read()
    assert "Promise.allSettled" in source, (
        "manager.ts must invoke Promise.allSettled when tearing down workspaces so "
        "partial failures don't break others."
    )


def test_scenario_log_contains_pool_size_line(scenario_log_text):
    assert f"pool size: {EXPECTED_POOL_SIZE}" in scenario_log_text, (
        f"scenario.log must contain 'pool size: {EXPECTED_POOL_SIZE}' produced by the status step."
    )


def test_scenario_log_has_three_bucket_lines(pool_buckets_from_log):
    assert len(pool_buckets_from_log) == EXPECTED_POOL_SIZE, (
        f"Expected exactly {EXPECTED_POOL_SIZE} bucket-name lines after the 'pool size' line, "
        f"got: {pool_buckets_from_log}"
    )
    assert len(set(pool_buckets_from_log)) == EXPECTED_POOL_SIZE, (
        f"Bucket names must be unique, got duplicates in: {pool_buckets_from_log}"
    )


def test_pool_state_json_removed_after_teardown():
    assert not os.path.exists(POOL_STATE), (
        f"pool-state.json should have been removed by the `teardown` step, "
        f"but it still exists at {POOL_STATE}."
    )


def test_all_pool_buckets_torn_down_via_cli(pool_buckets_from_log):
    """Priority 1: use the tigris CLI to confirm every workspace bucket has been deleted."""
    env = _tigris_env()
    result = subprocess.run(
        ["tigris", "buckets", "list", "--format", "json"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, (
        f"`tigris buckets list --format json` failed: "
        f"{result.stderr.strip() or result.stdout.strip()}"
    )

    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"`tigris buckets list --format json` returned invalid JSON: {exc}\n"
            f"Output: {result.stdout[:500]}"
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

    live_names = set()
    for entry in candidates:
        if isinstance(entry, str):
            live_names.add(entry)
        elif isinstance(entry, dict):
            for key in ("name", "Name", "bucket", "Bucket"):
                if isinstance(entry.get(key), str):
                    live_names.add(entry[key])
                    break

    raw_output = result.stdout
    for bucket in pool_buckets_from_log:
        assert bucket not in live_names and bucket not in raw_output, (
            f"Bucket {bucket!r} is still present after the `teardown` step; "
            f"all pool workspaces must be deleted via Promise.allSettled([teardownWorkspace(...), ...])."
        )
