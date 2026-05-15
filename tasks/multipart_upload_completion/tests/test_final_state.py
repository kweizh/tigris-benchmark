import hashlib
import json
import os
import re
import subprocess
import pytest

TRIAL_ID_FILE = "/logs/artifacts/trial_id"
PROJECT_DIR = "/home/user/tigris-task"
LARGE_FILE = os.path.join(PROJECT_DIR, "large.bin")
LOCAL_MD5_FILE = os.path.join(PROJECT_DIR, "local.md5")
OBJECT_KEY = "archives/large.bin"
EXPECTED_SIZE = 16 * 1024 * 1024  # 16 MiB


def _read_trial_id():
    assert os.path.isfile(TRIAL_ID_FILE), (
        f"Trial id file {TRIAL_ID_FILE} does not exist; cannot derive bucket name."
    )
    with open(TRIAL_ID_FILE, "r") as f:
        trial_id = f.read().strip()
    assert trial_id, f"Trial id file {TRIAL_ID_FILE} is empty."
    return trial_id


def _sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _md5_of_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture(scope="module")
def bucket_name():
    trial_id = _read_trial_id()
    name = f"harbor-mpu-{trial_id}"
    yield name
    # Cleanup: forcefully remove the bucket and any objects it contains,
    # regardless of whether the assertions above passed or failed.
    subprocess.run(
        ["aws", "s3", "rb", f"s3://{name}", "--force"],
        capture_output=True,
        text=True,
    )


def test_local_md5_file_exists_and_matches():
    """The agent must produce local.md5 containing the MD5 of large.bin."""
    assert os.path.isfile(LOCAL_MD5_FILE), (
        f"Expected MD5 fingerprint file at {LOCAL_MD5_FILE}, but it does not exist."
    )
    with open(LOCAL_MD5_FILE, "r") as f:
        content = f.read().strip()
    assert re.fullmatch(r"[0-9a-f]{32}", content), (
        f"Expected {LOCAL_MD5_FILE} to contain exactly 32 lowercase hex chars "
        f"(the MD5 digest), got {content!r}."
    )
    expected_md5 = _md5_of_file(LARGE_FILE)
    assert content == expected_md5, (
        f"Expected {LOCAL_MD5_FILE} to contain the MD5 of {LARGE_FILE} "
        f"({expected_md5}), got {content}."
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


def test_object_head_reports_correct_size_and_multipart_etag(bucket_name):
    """Priority 1: head-object must report ContentLength=16777216 and a
    multipart-style ETag (hex-<partcount>) with part count >= 2, which proves
    the upload was performed via S3 multipart upload."""
    result = subprocess.run(
        [
            "aws",
            "s3api",
            "head-object",
            "--bucket",
            bucket_name,
            "--key",
            OBJECT_KEY,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"'aws s3api head-object' for s3://{bucket_name}/{OBJECT_KEY} failed: "
        f"exit code {result.returncode}, stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    head = json.loads(result.stdout)
    content_length = head.get("ContentLength")
    assert content_length == EXPECTED_SIZE, (
        f"Expected ContentLength={EXPECTED_SIZE} for "
        f"s3://{bucket_name}/{OBJECT_KEY}, got {content_length}."
    )
    etag = head.get("ETag", "").strip('"')
    multipart_match = re.fullmatch(r"([0-9a-f]{32})-(\d+)", etag)
    assert multipart_match is not None, (
        f"Expected ETag in multipart format '<hex32>-<partcount>' for "
        f"s3://{bucket_name}/{OBJECT_KEY}, got {etag!r}. This usually means "
        f"the upload was NOT performed as a multipart upload."
    )
    part_count = int(multipart_match.group(2))
    assert part_count >= 2, (
        f"Expected multipart upload with at least 2 parts (multipart_chunksize "
        f"should be 5 MB so a 16 MiB upload produces 4 parts), got "
        f"part_count={part_count} (ETag={etag!r})."
    )


def test_downloaded_object_matches_local_sha256(bucket_name, tmp_path):
    """Priority 1: download the uploaded object and verify SHA256 equals the
    SHA256 of the local source file."""
    dest = tmp_path / "downloaded.bin"
    result = subprocess.run(
        [
            "aws",
            "s3",
            "cp",
            f"s3://{bucket_name}/{OBJECT_KEY}",
            str(dest),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Failed to download s3://{bucket_name}/{OBJECT_KEY}: "
        f"exit code {result.returncode}, stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    assert dest.exists(), (
        f"Downloaded destination {dest} does not exist after `aws s3 cp` "
        f"reported success."
    )
    size = dest.stat().st_size
    assert size == EXPECTED_SIZE, (
        f"Expected downloaded object size to be {EXPECTED_SIZE} bytes, "
        f"got {size}."
    )
    downloaded_sha = _sha256_of_file(str(dest))
    local_sha = _sha256_of_file(LARGE_FILE)
    assert downloaded_sha == local_sha, (
        f"Expected SHA256 of downloaded object ({downloaded_sha}) to equal "
        f"SHA256 of local source file ({local_sha})."
    )
