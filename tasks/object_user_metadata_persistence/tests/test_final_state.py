import json
import os
import subprocess
import pytest

TRIAL_ID_FILE = "/logs/artifacts/trial_id"
OBJECT_KEY = "reports/q1.txt"


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
    name = f"harbor-meta-{trial_id}"
    import re
    name = re.sub(r"[^a-z0-9.-]", "-", name.lower())
    yield name
    # Cleanup: forcefully remove the bucket and any objects it contains,
    # regardless of whether the assertions above passed or failed.
    subprocess.run(
        ["aws", "s3", "rb", f"s3://{name}", "--force"],
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="module")
def head_object_json(bucket_name):
    """Priority 1: use the AWS CLI against Tigris to fetch the object's
    metadata via `aws s3api head-object` and return the parsed JSON."""
    result = subprocess.run(
        [
            "aws",
            "s3api",
            "head-object",
            "--bucket",
            bucket_name,
            "--key",
            OBJECT_KEY,
            "--output",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"'aws s3api head-object --bucket {bucket_name} --key {OBJECT_KEY}' "
        f"failed with exit code {result.returncode}: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"head-object output was not valid JSON: {exc}; "
            f"stdout={result.stdout!r}"
        )
    return parsed


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


def test_user_metadata_owner_is_alice(head_object_json, bucket_name):
    metadata = head_object_json.get("Metadata", {})
    assert isinstance(metadata, dict), (
        f"Expected 'Metadata' field in head-object response to be a dict, "
        f"got {type(metadata).__name__}: {metadata!r}"
    )
    owner = metadata.get("owner")
    assert owner == "alice", (
        f"Expected user metadata 'owner' to be 'alice' on "
        f"s3://{bucket_name}/{OBJECT_KEY}, got {owner!r}. "
        f"Full Metadata: {metadata!r}"
    )


def test_user_metadata_team_is_research(head_object_json, bucket_name):
    metadata = head_object_json.get("Metadata", {})
    assert isinstance(metadata, dict), (
        f"Expected 'Metadata' field in head-object response to be a dict, "
        f"got {type(metadata).__name__}: {metadata!r}"
    )
    team = metadata.get("team")
    assert team == "research", (
        f"Expected user metadata 'team' to be 'research' on "
        f"s3://{bucket_name}/{OBJECT_KEY}, got {team!r}. "
        f"Full Metadata: {metadata!r}"
    )


def test_object_content_type_is_text_markdown(head_object_json, bucket_name):
    content_type = head_object_json.get("ContentType")
    assert content_type == "text/markdown", (
        f"Expected ContentType 'text/markdown' on "
        f"s3://{bucket_name}/{OBJECT_KEY}, got {content_type!r}."
    )
