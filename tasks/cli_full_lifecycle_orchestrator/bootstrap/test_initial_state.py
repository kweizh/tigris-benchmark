import json
import os
import re
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/lifecycle"
LOCAL_FILE = os.path.join(PROJECT_DIR, "local.txt")
TRIAL_ID_FILE = "/logs/artifacts/trial_id"


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
    name = f"harbor-lifecycle-{trial_id}"
    return re.sub(r"[^a-z0-9.-]", "-", name.lower())


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


def test_jq_available():
    assert shutil.which("jq") is not None, (
        "jq binary not found in PATH. The task hints at using jq to parse "
        "the JSON output of `tigris snapshots list`."
    )


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected project directory {PROJECT_DIR} to exist before the task starts."
    )


def test_local_seed_file_exists():
    assert os.path.isfile(LOCAL_FILE), (
        f"Expected the seed file {LOCAL_FILE} to be present at task start. "
        "The script must upload this file as the object 'seed.txt'."
    )


def test_local_seed_file_is_non_empty():
    assert os.path.getsize(LOCAL_FILE) > 0, (
        f"Seed file {LOCAL_FILE} must be non-empty so an object body can be uploaded."
    )


def test_tigris_credentials_env_vars_present():
    assert os.environ.get("TIGRIS_STORAGE_ACCESS_KEY_ID"), (
        "TIGRIS_STORAGE_ACCESS_KEY_ID environment variable must be provided by Harbor."
    )
    assert os.environ.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY"), (
        "TIGRIS_STORAGE_SECRET_ACCESS_KEY environment variable must be provided by Harbor."
    )


def test_tigris_cli_can_list_buckets():
    """The CLI must be functional and authenticated before the agent runs."""
    result = subprocess.run(
        ["tigris", "buckets", "list", "--format", "json"],
        capture_output=True,
        text=True,
        env=_tigris_env(),
        cwd=PROJECT_DIR,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"'tigris buckets list --format json' failed with returncode "
        f"{result.returncode}. stderr={result.stderr!r} stdout={result.stdout!r}"
    )
    try:
        json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"'tigris buckets list --format json' did not return valid JSON: "
            f"{exc}. stdout={result.stdout!r}"
        )


def test_target_bucket_does_not_yet_exist():
    """The bucket the agent will create must NOT already exist."""
    result = subprocess.run(
        ["tigris", "buckets", "list", "--format", "json"],
        capture_output=True,
        text=True,
        env=_tigris_env(),
        cwd=PROJECT_DIR,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"'tigris buckets list --format json' failed: stderr={result.stderr!r}"
    )
    payload = json.loads(result.stdout)
    if isinstance(payload, dict):
        buckets = payload.get("items", []) or payload.get("buckets", [])
    else:
        buckets = payload
    bucket_names = [b.get("name") for b in buckets if isinstance(b, dict)]
    name = bucket_name()
    assert name not in bucket_names, (
        f"Bucket {name!r} unexpectedly already exists in the Tigris "
        f"organization before the task begins. Existing buckets: {bucket_names}"
    )


def test_run_script_does_not_yet_exist():
    """The agent is expected to author run.sh; it must not be pre-shipped."""
    script_path = os.path.join(PROJECT_DIR, "run.sh")
    assert not os.path.exists(script_path), (
        f"{script_path} must NOT exist at the start of the task; the agent "
        "is expected to create it."
    )


def test_snapshots_output_file_does_not_yet_exist():
    snapshots_path = os.path.join(PROJECT_DIR, "snapshots.txt")
    assert not os.path.exists(snapshots_path), (
        f"{snapshots_path} must NOT exist at the start of the task; the "
        "agent's script is expected to create it."
    )
