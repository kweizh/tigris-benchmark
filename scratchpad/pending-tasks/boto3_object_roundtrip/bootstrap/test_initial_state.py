import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/tigris-task"
TRIAL_ID_PATH = "/logs/artifacts/trial_id"


def test_python3_available():
    assert shutil.which("python3") is not None, (
        "python3 binary not found in PATH. The task requires python3 to run the "
        "boto3 roundtrip script."
    )


def test_pip3_available():
    assert shutil.which("pip3") is not None, (
        "pip3 binary not found in PATH. pip3 is required because boto3 is "
        "installed via pip on Ubuntu 24.04."
    )


def test_boto3_importable():
    """boto3 must be pre-installed in the task environment."""
    result = subprocess.run(
        ["python3", "-c", "import boto3, botocore; print(boto3.__version__)"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"Failed to import boto3 / botocore in the task environment. "
        f"stderr={result.stderr!r} stdout={result.stdout!r}"
    )
    assert result.stdout.strip(), (
        "`python3 -c 'import boto3; print(boto3.__version__)'` produced no "
        f"output. stderr={result.stderr!r}"
    )


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected project directory {PROJECT_DIR} to exist before the task starts."
    )


def test_roundtrip_script_does_not_yet_exist():
    """The agent is responsible for creating roundtrip.py."""
    script_path = os.path.join(PROJECT_DIR, "roundtrip.py")
    assert not os.path.exists(script_path), (
        f"Unexpected pre-existing file at {script_path}; the agent must create it."
    )


def test_downloaded_artifact_does_not_yet_exist():
    """The agent is responsible for producing downloaded.json."""
    download_path = os.path.join(PROJECT_DIR, "downloaded.json")
    assert not os.path.exists(download_path), (
        f"Unexpected pre-existing file at {download_path}; the agent must create it."
    )


def test_trial_id_file_present():
    """Harbor places the per-trial id at /logs/artifacts/trial_id."""
    assert os.path.isfile(TRIAL_ID_PATH), (
        f"Expected trial id file at {TRIAL_ID_PATH}; the bucket name depends on it."
    )
    with open(TRIAL_ID_PATH, "r") as fh:
        trial_id = fh.read().strip()
    assert trial_id, (
        f"Trial id file {TRIAL_ID_PATH} is empty; cannot derive a bucket name."
    )


def test_aws_credentials_env_vars_present():
    assert os.environ.get("AWS_ACCESS_KEY_ID"), (
        "AWS_ACCESS_KEY_ID environment variable must be provided to the task "
        "(it is mapped from TIGRIS_STORAGE_ACCESS_KEY_ID by Harbor)."
    )
    assert os.environ.get("AWS_SECRET_ACCESS_KEY"), (
        "AWS_SECRET_ACCESS_KEY environment variable must be provided to the "
        "task (it is mapped from TIGRIS_STORAGE_SECRET_ACCESS_KEY by Harbor)."
    )


def test_aws_endpoint_env_var_present():
    endpoint = os.environ.get("AWS_ENDPOINT_URL_S3")
    assert endpoint, (
        "AWS_ENDPOINT_URL_S3 environment variable must be set so boto3 talks "
        "to Tigris instead of AWS S3."
    )
    assert "t3.storage.dev" in endpoint, (
        f"AWS_ENDPOINT_URL_S3 should point at the Tigris endpoint "
        f"(https://t3.storage.dev), got {endpoint!r}."
    )


def test_aws_region_env_var_present():
    region = os.environ.get("AWS_REGION")
    assert region, (
        "AWS_REGION environment variable must be set (Tigris uses the "
        "literal value 'auto')."
    )
