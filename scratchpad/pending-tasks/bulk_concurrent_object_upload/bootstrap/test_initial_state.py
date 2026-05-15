import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/tigris-task"
BULK_SCRIPT = os.path.join(PROJECT_DIR, "bulk.py")
TIMING_FILE = os.path.join(PROJECT_DIR, "timing.txt")
TRIAL_ID_PATH = "/logs/artifacts/trial_id"


def test_python3_available():
    assert shutil.which("python3") is not None, (
        "python3 binary not found in PATH. python3 is required to run the "
        "agent's bulk.py upload script."
    )


def test_boto3_importable():
    """The agent must be able to `import boto3` and `from botocore.client import Config`."""
    result = subprocess.run(
        ["python3", "-c", "import boto3, botocore; from botocore.client import Config; print(boto3.__version__)"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        "Expected boto3 + botocore to be importable in the task environment, "
        f"but got returncode={result.returncode} stderr={result.stderr!r} stdout={result.stdout!r}"
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


def test_tigris_credentials_env_vars_present():
    assert os.environ.get("TIGRIS_STORAGE_ACCESS_KEY_ID"), (
        "TIGRIS_STORAGE_ACCESS_KEY_ID environment variable must be provided by Harbor."
    )
    assert os.environ.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY"), (
        "TIGRIS_STORAGE_SECRET_ACCESS_KEY environment variable must be provided by Harbor."
    )


def test_aws_endpoint_url_s3_env_var_present():
    """The AWS_ENDPOINT_URL_S3 env var must be exported so boto3 can target Tigris."""
    endpoint = os.environ.get("AWS_ENDPOINT_URL_S3")
    assert endpoint, (
        "AWS_ENDPOINT_URL_S3 environment variable must be exported (expected "
        "value: https://t3.storage.dev) so boto3 can route requests to Tigris."
    )
    assert "t3.storage.dev" in endpoint, (
        f"AWS_ENDPOINT_URL_S3 must point at the Tigris global endpoint "
        f"(https://t3.storage.dev). Got: {endpoint!r}"
    )


def test_bulk_script_does_not_yet_exist():
    assert not os.path.exists(BULK_SCRIPT), (
        f"{BULK_SCRIPT} must NOT exist at the start of the task; the agent "
        "is expected to create it."
    )


def test_timing_file_does_not_yet_exist():
    assert not os.path.exists(TIMING_FILE), (
        f"{TIMING_FILE} must NOT exist at the start of the task; the agent's "
        "bulk.py is expected to create it after the upload phase."
    )
