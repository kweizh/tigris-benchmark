import json
import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/bucket-create"
BUCKET_NAME = "eval-gold-corpus"


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


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected project directory {PROJECT_DIR} to exist before the task starts."
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
    # The CLI must emit valid JSON on success.
    try:
        json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"'tigris buckets list --format json' did not return valid JSON: "
            f"{exc}. stdout={result.stdout!r}"
        )


def test_target_bucket_does_not_yet_exist():
    """The bucket the agent must create must NOT already exist in the org."""
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
    # The CLI returns either a bare list or an object with an `items` array
    # depending on whether pagination metadata is attached. Normalize both.
    if isinstance(payload, dict):
        buckets = payload.get("items", []) or payload.get("buckets", [])
    else:
        buckets = payload
    bucket_names = [b.get("name") for b in buckets if isinstance(b, dict)]
    assert BUCKET_NAME not in bucket_names, (
        f"Bucket {BUCKET_NAME!r} unexpectedly already exists in the Tigris "
        f"organization before the task begins. Existing buckets: {bucket_names}"
    )
