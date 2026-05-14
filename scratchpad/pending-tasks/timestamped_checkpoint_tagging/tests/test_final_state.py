import json
import os
import re
import subprocess

import pytest

PROJECT_DIR = "/home/user/ckpt-tag"
INDEX_TS = os.path.join(PROJECT_DIR, "index.ts")
SNAPSHOT_JSON = os.path.join(PROJECT_DIR, "snapshot.json")
SOURCE_BUCKET = "agent-pipeline-data"
NAME_REGEX = re.compile(r"^release-v42-\d{10,}$")


def _tigris_env():
    env = os.environ.copy()
    access = env.get("TIGRIS_STORAGE_ACCESS_KEY_ID", "")
    secret = env.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY", "")
    env["AWS_ACCESS_KEY_ID"] = access
    env["AWS_SECRET_ACCESS_KEY"] = secret
    env["AWS_REGION"] = "auto"
    env["AWS_DEFAULT_REGION"] = "auto"
    return env


@pytest.fixture(scope="module")
def script_run_result():
    assert os.path.isfile(INDEX_TS), (
        f"User script not found at {INDEX_TS}; the agent must create it."
    )

    env = _tigris_env()

    install = subprocess.run(
        ["npm", "install", "--no-audit", "--no-fund"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )
    assert install.returncode == 0, (
        f"'npm install' failed in {PROJECT_DIR}: "
        f"stdout={install.stdout!r} stderr={install.stderr!r}"
    )

    result = subprocess.run(
        ["npx", "tsx", "index.ts"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )

    yield result

    # Best-effort cleanup of the source bucket.
    try:
        subprocess.run(
            ["tigris", "buckets", "delete", SOURCE_BUCKET, "--force"],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
    except Exception:
        pass


def test_user_script_runs_successfully(script_run_result):
    assert script_run_result.returncode == 0, (
        "User script 'npx tsx index.ts' did not exit 0. "
        f"stdout={script_run_result.stdout!r} stderr={script_run_result.stderr!r}"
    )


def test_snapshot_json_exists_and_has_expected_shape(script_run_result):
    assert script_run_result.returncode == 0, (
        "Skipping snapshot.json check because the user script failed: "
        f"{script_run_result.stderr!r}"
    )
    assert os.path.isfile(SNAPSHOT_JSON), (
        f"Expected {SNAPSHOT_JSON} to exist after the script ran."
    )
    with open(SNAPSHOT_JSON) as f:
        try:
            payload = json.load(f)
        except json.JSONDecodeError as exc:
            pytest.fail(f"{SNAPSHOT_JSON} is not valid JSON: {exc}")
    assert isinstance(payload, dict), (
        f"snapshot.json must decode to a JSON object, got: {type(payload).__name__}"
    )

    snapshot_id = payload.get("snapshotId")
    assert isinstance(snapshot_id, str) and snapshot_id, (
        f"snapshot.json must contain a non-empty string 'snapshotId', got: {payload!r}"
    )

    name = payload.get("name")
    assert isinstance(name, str) and name, (
        f"snapshot.json must contain a non-empty string 'name', got: {payload!r}"
    )
    assert NAME_REGEX.match(name), (
        f"snapshot.json 'name' must match regex {NAME_REGEX.pattern!r}, got: {name!r}"
    )


def test_named_snapshot_exists_in_tigris(script_run_result):
    assert script_run_result.returncode == 0, (
        "Skipping snapshot existence check because the user script failed."
    )
    with open(SNAPSHOT_JSON) as f:
        payload = json.load(f)
    expected_name = payload["name"]

    env = _tigris_env()
    result = subprocess.run(
        ["tigris", "snapshots", "list", SOURCE_BUCKET, "--format", "json"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert result.returncode == 0, (
        "'tigris snapshots list agent-pipeline-data --format json' failed: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    stdout = result.stdout.strip()
    assert stdout, "Expected non-empty output from 'tigris snapshots list'."
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Could not parse snapshots-list JSON: {exc}\nOutput: {stdout!r}")

    snapshots = []
    if isinstance(data, list):
        snapshots = data
    elif isinstance(data, dict):
        snapshots = data.get("snapshots") or data.get("Snapshots") or []

    names = []
    for entry in snapshots:
        if isinstance(entry, dict):
            name = entry.get("name") or entry.get("Name")
            if isinstance(name, str):
                names.append(name)

    assert expected_name in names, (
        f"Expected a snapshot named {expected_name!r} on bucket {SOURCE_BUCKET!r}, "
        f"found names: {names}"
    )
