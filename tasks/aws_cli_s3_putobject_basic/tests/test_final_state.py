import os
import re
import subprocess
import pytest

TRIAL_ID_FILE = "/logs/artifacts/trial_id"
EXPECTED_CONTENT = b"hello tigris"


def _read_trial_id():
    assert os.path.isfile(TRIAL_ID_FILE), (
        f"Trial id file {TRIAL_ID_FILE} does not exist; cannot derive bucket name."
    )
    with open(TRIAL_ID_FILE, "r") as f:
        trial_id = f.read().strip()
    assert trial_id, f"Trial id file {TRIAL_ID_FILE} is empty."
    return trial_id


@pytest.fixture(scope="module")
def bucket_name():
    trial_id = _read_trial_id()
    name = f"harbor-awscli-{trial_id}"
    name = re.sub(r"[^a-z0-9.-]", "-", name.lower())
    yield name
    # Cleanup: forcefully remove the bucket and any objects it contains,
    # regardless of whether the assertions above passed or failed.
    subprocess.run(
        ["aws", "s3", "rb", f"s3://{name}", "--force"],
        capture_output=True,
        text=True,
    )


def test_bucket_exists_via_cli(bucket_name):
    """Priority 1: use the AWS CLI against Tigris to verify the bucket exists."""
    result = subprocess.run(
        ["aws", "s3api", "head-bucket", "--bucket", bucket_name],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Expected bucket {bucket_name!r} to exist on Tigris, but "
        f"'aws s3api head-bucket' failed with exit code {result.returncode}: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_object_exists_and_has_correct_content(bucket_name, tmp_path):
    """Priority 1: download the uploaded object using the AWS CLI and verify
    the exact bytes match the expected literal content."""
    dest = tmp_path / "downloaded.txt"
    result = subprocess.run(
        [
            "aws",
            "s3",
            "cp",
            f"s3://{bucket_name}/hello.txt",
            str(dest),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Failed to download s3://{bucket_name}/hello.txt: "
        f"exit code {result.returncode}, stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    assert dest.exists(), (
        f"Downloaded destination {dest} does not exist after `aws s3 cp` "
        f"reported success."
    )
    data = dest.read_bytes()
    assert data == EXPECTED_CONTENT, (
        f"Expected object s3://{bucket_name}/hello.txt to contain "
        f"exactly {EXPECTED_CONTENT!r}, got {data!r}."
    )
