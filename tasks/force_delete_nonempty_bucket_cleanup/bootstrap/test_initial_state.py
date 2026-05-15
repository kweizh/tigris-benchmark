import json
import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/cleanup-task"
TRIAL_ID_PATH = "/logs/artifacts/trial_id"
EXPECTED_OBJECT_KEYS = ("temp/a.tmp", "temp/b.tmp", "temp/c.tmp")


def _tigris_env():
    """Build an env dict that maps Tigris credentials into the AWS-compatible
    variables consumed by the `tigris` CLI."""
    env = os.environ.copy()
    access_key = os.environ.get("TIGRIS_STORAGE_ACCESS_KEY_ID")
    secret_key = os.environ.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY")
    assert access_key, "TIGRIS_STORAGE_ACCESS_KEY_ID is not set in the environment."
    assert secret_key, "TIGRIS_STORAGE_SECRET_ACCESS_KEY is not set in the environment."
    env["AWS_ACCESS_KEY_ID"] = access_key
    env["AWS_SECRET_ACCESS_KEY"] = secret_key
    env.setdefault("AWS_REGION", "auto")
    return env


def _trial_id():
    assert os.path.isfile(TRIAL_ID_PATH), (
        f"Expected trial id file at {TRIAL_ID_PATH} to exist before the task starts."
    )
    with open(TRIAL_ID_PATH) as f:
        value = f.read().strip()
    assert value, f"Trial id file {TRIAL_ID_PATH} is empty."
    return value


def _bucket_name():
    return f"harbor-cleanup-{_trial_id()}"


def _list_bucket_names():
    result = subprocess.run(
        ["tigris", "buckets", "list", "--format", "json"],
        capture_output=True,
        text=True,
        env=_tigris_env(),
        cwd=PROJECT_DIR,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"'tigris buckets list --format json' failed: returncode="
        f"{result.returncode}, stderr={result.stderr!r}"
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"'tigris buckets list --format json' did not return valid JSON: {exc}. "
            f"stdout={result.stdout!r}"
        )
    if isinstance(payload, dict):
        buckets = payload.get("items", []) or payload.get("buckets", [])
    else:
        buckets = payload
    return [b.get("name") for b in buckets if isinstance(b, dict)]


def test_tigris_cli_available():
    assert shutil.which("tigris") is not None, (
        "tigris CLI binary not found in PATH. The @tigrisdata/cli npm package "
        "must be installed globally so the `tigris` command is available."
    )


def test_node_available():
    assert shutil.which("node") is not None, (
        "node binary not found in PATH. Node.js is required to run the "
        "@tigrisdata/cli npm package."
    )


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected project directory {PROJECT_DIR} to exist before the task starts."
    )


def test_trial_id_file_exists_and_non_empty():
    trial_id = _trial_id()
    assert trial_id, "Trial id file must contain a non-empty value."


def test_tigris_credentials_env_vars_present():
    assert os.environ.get("TIGRIS_STORAGE_ACCESS_KEY_ID"), (
        "TIGRIS_STORAGE_ACCESS_KEY_ID environment variable must be provided by Harbor."
    )
    assert os.environ.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY"), (
        "TIGRIS_STORAGE_SECRET_ACCESS_KEY environment variable must be provided by Harbor."
    )


def test_seed_bucket_exists():
    """The pre-seeded bucket must already be present in the Tigris account."""
    bucket_name = _bucket_name()
    bucket_names = _list_bucket_names()
    assert bucket_name in bucket_names, (
        f"Expected pre-seeded bucket {bucket_name!r} to already exist before the "
        f"task starts, but it was not found. Existing buckets: {bucket_names}"
    )


def test_seed_bucket_contains_three_objects():
    """The pre-seeded bucket must contain three scratch objects under temp/."""
    bucket_name = _bucket_name()
    result = subprocess.run(
        ["tigris", "ls", f"t3://{bucket_name}/temp/"],
        capture_output=True,
        text=True,
        env=_tigris_env(),
        cwd=PROJECT_DIR,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"'tigris ls t3://{bucket_name}/temp/' failed: returncode="
        f"{result.returncode}, stderr={result.stderr!r}"
    )
    output = result.stdout
    for key in EXPECTED_OBJECT_KEYS:
        # The CLI may print full keys or just the basename — accept either.
        basename = key.rsplit("/", 1)[-1]
        assert (key in output) or (basename in output), (
            f"Expected pre-seeded object {key!r} to be listed by "
            f"`tigris ls t3://{bucket_name}/temp/` but it was not found. "
            f"stdout={output!r}"
        )
