import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/tigris-task"
REPORT_FILE = os.path.join(PROJECT_DIR, "report.txt")
TRIAL_ID_FILE = "/logs/artifacts/trial_id"


def test_aws_cli_available():
    assert shutil.which("aws") is not None, "aws CLI binary not found in PATH."


def test_aws_cli_runs():
    result = subprocess.run(
        ["aws", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"'aws --version' failed with exit code {result.returncode}: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} does not exist."
    )


def test_report_file_exists():
    assert os.path.isfile(REPORT_FILE), (
        f"Pre-existing file {REPORT_FILE} does not exist."
    )


def test_report_file_contents():
    with open(REPORT_FILE, "rb") as f:
        data = f.read()
    assert data == b"quarterly report", (
        f"Expected {REPORT_FILE} to contain exactly b'quarterly report', got {data!r}."
    )


def test_trial_id_file_exists():
    assert os.path.isfile(TRIAL_ID_FILE), (
        f"Trial id file {TRIAL_ID_FILE} is required to derive the bucket name "
        f"but does not exist."
    )


def test_tigris_endpoint_env_set():
    endpoint = os.environ.get("AWS_ENDPOINT_URL_S3")
    assert endpoint == "https://t3.storage.dev", (
        f"Expected AWS_ENDPOINT_URL_S3=https://t3.storage.dev, got {endpoint!r}."
    )


def test_aws_credentials_env_set():
    assert os.environ.get("AWS_ACCESS_KEY_ID"), (
        "AWS_ACCESS_KEY_ID must be set in the environment."
    )
    assert os.environ.get("AWS_SECRET_ACCESS_KEY"), (
        "AWS_SECRET_ACCESS_KEY must be set in the environment."
    )


def test_aws_region_env_set():
    region = os.environ.get("AWS_REGION")
    assert region == "auto", (
        f"Expected AWS_REGION=auto, got {region!r}."
    )
