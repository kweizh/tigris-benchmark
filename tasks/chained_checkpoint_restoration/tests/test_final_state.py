import json
import os
import re
import shutil
import subprocess
import tempfile

import pytest

PROJECT_DIR = "/home/user/chained-ckpt"
INDEX_TS = os.path.join(PROJECT_DIR, "index.ts")
RECOVERY_JSON = os.path.join(PROJECT_DIR, "recovery.json")
TRIAL_ID_FILE = "/logs/artifacts/trial_id"
TIGRIS_ENDPOINT = "https://t3.storage.dev"


def _read_trial_id():
    assert os.path.isfile(TRIAL_ID_FILE), (
        f"Trial id file {TRIAL_ID_FILE} does not exist; cannot derive bucket name."
    )
    with open(TRIAL_ID_FILE, "r") as f:
        trial_id = f.read().strip()
    assert trial_id, f"Trial id file {TRIAL_ID_FILE} is empty."
    return trial_id


def bucket_name():
    trial_id = _read_trial_id()
    name = f"harbor-awscli-{trial_id}"
    name = re.sub(r"[^a-z0-9.-]", "-", name.lower())
    return name


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

    # Make sure dependencies are installed before running.
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

    # Best-effort cleanup of the source bucket and any leftover recovery forks.
    try:
        list_result = subprocess.run(
            ["tigris", "buckets", "list", "--format", "json"],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
        bucket_names = _parse_bucket_names(list_result.stdout)
        source_bucket = bucket_name()
        for name in bucket_names:
            if name == source_bucket or name.startswith("rollback-recovery"):
                subprocess.run(
                    ["tigris", "buckets", "delete", name, "--force"],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=120,
                )
    except Exception:
        pass


def _parse_bucket_names(stdout: str):
    stdout = stdout.strip()
    if not stdout:
        return []
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    names = []
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict):
                name = entry.get("name") or entry.get("Name") or entry.get("bucket")
                if isinstance(name, str):
                    names.append(name)
            elif isinstance(entry, str):
                names.append(entry)
    elif isinstance(data, dict):
        buckets = data.get("buckets") or data.get("Buckets") or []
        for entry in buckets:
            if isinstance(entry, dict):
                name = entry.get("name") or entry.get("Name") or entry.get("bucket")
                if isinstance(name, str):
                    names.append(name)
            elif isinstance(entry, str):
                names.append(entry)
    return names


def test_user_script_runs_successfully(script_run_result):
    assert script_run_result.returncode == 0, (
        "User script 'npx tsx index.ts' did not exit 0. "
        f"stdout={script_run_result.stdout!r} stderr={script_run_result.stderr!r}"
    )


def test_recovery_json_exists_and_has_expected_bucket(script_run_result):
    assert script_run_result.returncode == 0, (
        "Skipping recovery.json check because the user script failed: "
        f"{script_run_result.stderr!r}"
    )
    assert os.path.isfile(RECOVERY_JSON), (
        f"Expected {RECOVERY_JSON} to exist after the script ran."
    )
    with open(RECOVERY_JSON) as f:
        try:
            payload = json.load(f)
        except json.JSONDecodeError as exc:
            pytest.fail(f"{RECOVERY_JSON} is not valid JSON: {exc}")
    assert isinstance(payload, dict), (
        f"recovery.json must decode to a JSON object, got: {type(payload).__name__}"
    )
    bucket = payload.get("recoveryBucket")
    assert isinstance(bucket, str) and bucket, (
        f"recovery.json must contain a non-empty string 'recoveryBucket', got: {payload!r}"
    )
    assert bucket.startswith("rollback-recovery"), (
        f"recoveryBucket must start with 'rollback-recovery', got: {bucket!r}"
    )


def test_source_bucket_v1_now_contains_version_two(script_run_result):
    assert script_run_result.returncode == 0, (
        "Skipping source bucket content check because the user script failed."
    )
    env = _tigris_env()
    assert shutil.which("aws") is not None, "aws CLI is required for verification."
    source_bucket = bucket_name()
    with tempfile.TemporaryDirectory() as tmpdir:
        local_path = os.path.join(tmpdir, "v1.txt")
        result = subprocess.run(
            [
                "aws",
                "s3",
                "cp",
                f"s3://{source_bucket}/v1.txt",
                local_path,
                "--endpoint-url",
                TIGRIS_ENDPOINT,
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"Failed to download s3://{source_bucket}/v1.txt via aws CLI: "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        with open(local_path, "rb") as f:
            body = f.read()
    assert body == b"version=2", (
        f"Expected s3://{source_bucket}/v1.txt to contain 'version=2', got: {body!r}"
    )


def test_recovery_bucket_was_torn_down(script_run_result):
    assert script_run_result.returncode == 0, (
        "Skipping recovery-bucket teardown check because the user script failed."
    )
    with open(RECOVERY_JSON) as f:
        payload = json.load(f)
    recovery_bucket = payload["recoveryBucket"]

    env = _tigris_env()
    result = subprocess.run(
        ["tigris", "buckets", "list", "--format", "json"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"'tigris buckets list' failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    names = _parse_bucket_names(result.stdout)
    assert recovery_bucket not in names, (
        f"Recovery fork bucket '{recovery_bucket}' was not torn down. "
        f"Current buckets: {names}"
    )


def test_before_mutation_snapshot_exists(script_run_result):
    assert script_run_result.returncode == 0, (
        "Skipping snapshot check because the user script failed."
    )
    env = _tigris_env()
    source_bucket = bucket_name()
    result = subprocess.run(
        ["tigris", "snapshots", "list", source_bucket, "--format", "json"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"'tigris snapshots list {source_bucket} --format json' failed: "
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

    assert "before-mutation" in names, (
        f"Expected a snapshot named 'before-mutation' on bucket '{source_bucket}', "
        f"found names: {names}"
    )
