import json
import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/tigris-task"
SEED_FILES = {
    "a.txt": "alpha",
    "b.txt": "beta",
    "c.txt": "gamma",
}
TRIAL_ID_PATH = "/logs/artifacts/trial_id"


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


def _expected_bucket_name():
    assert os.path.isfile(TRIAL_ID_PATH), (
        f"Expected trial id file at {TRIAL_ID_PATH} to exist before the task starts."
    )
    with open(TRIAL_ID_PATH) as f:
        trial_id = f.read().strip()
    assert trial_id, f"{TRIAL_ID_PATH} must contain a non-empty trial id."
    name = f"harbor-prefix-{trial_id}"
    import re
    name = re.sub(r"[^a-z0-9.-]", "-", name.lower())
    return name


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


def test_trial_id_file_exists():
    assert os.path.isfile(TRIAL_ID_PATH), (
        f"Expected trial id file at {TRIAL_ID_PATH} to exist before the task starts."
    )
    with open(TRIAL_ID_PATH) as f:
        trial_id = f.read().strip()
    assert trial_id, f"{TRIAL_ID_PATH} must contain a non-empty trial id."


def test_seed_files_present_with_expected_contents():
    for name, expected in SEED_FILES.items():
        path = os.path.join(PROJECT_DIR, name)
        assert os.path.isfile(path), (
            f"Expected pre-seeded file {path} to exist before the task starts."
        )
        with open(path) as f:
            contents = f.read().strip()
        assert contents == expected, (
            f"Expected {path} to contain {expected!r}, got {contents!r}."
        )


def test_listing_output_file_does_not_yet_exist():
    log = os.path.join(PROJECT_DIR, "logs-listing.txt")
    assert not os.path.exists(log), (
        f"{log} must NOT exist at the start of the task; it is produced by the agent."
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
    """The bucket the agent must create must NOT already exist in the org."""
    bucket_name = _expected_bucket_name()
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
    assert bucket_name not in bucket_names, (
        f"Bucket {bucket_name!r} unexpectedly already exists in the Tigris "
        f"organization before the task begins. Existing buckets: {bucket_names}"
    )
