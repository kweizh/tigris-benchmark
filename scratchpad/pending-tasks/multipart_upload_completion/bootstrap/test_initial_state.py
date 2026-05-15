import hashlib
import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/tigris-task"
LARGE_FILE = os.path.join(PROJECT_DIR, "large.bin")
TRIAL_ID_FILE = "/logs/artifacts/trial_id"
EXPECTED_SIZE = 16 * 1024 * 1024  # 16 MiB = 16777216 bytes


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


def test_large_file_exists():
    assert os.path.isfile(LARGE_FILE), (
        f"Pre-existing file {LARGE_FILE} does not exist."
    )


def test_large_file_size_is_16_mib():
    size = os.path.getsize(LARGE_FILE)
    assert size == EXPECTED_SIZE, (
        f"Expected {LARGE_FILE} to be exactly {EXPECTED_SIZE} bytes (16 MiB), "
        f"got {size} bytes."
    )


def test_large_file_is_deterministic_zeros():
    """The file must be exactly 16 MiB of NUL bytes (from `dd if=/dev/zero`)."""
    h = hashlib.sha256()
    with open(LARGE_FILE, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    # SHA256 of 16777216 zero bytes:
    expected_sha = (
        "080acf35a507ac9849cfcba47dc2ad83e01b75663a516279c8b9d243b719643e"
    )
    assert h.hexdigest() == expected_sha, (
        f"Expected {LARGE_FILE} to be 16 MiB of NUL bytes "
        f"(SHA256={expected_sha}), got SHA256={h.hexdigest()}."
    )


def test_local_md5_not_present_initially():
    """The agent is required to produce this file, so it must NOT exist yet."""
    md5_path = os.path.join(PROJECT_DIR, "local.md5")
    assert not os.path.exists(md5_path), (
        f"{md5_path} must not exist before the agent runs (the agent creates it)."
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
