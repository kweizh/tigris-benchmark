import os
import pathlib
import subprocess

import pytest

PROJECT_DIR = "/home/user/tigris-task"
SCRIPT_PATH = os.path.join(PROJECT_DIR, "roundtrip.py")
DOWNLOAD_PATH = os.path.join(PROJECT_DIR, "downloaded.json")
TRIAL_ID_PATH = "/logs/artifacts/trial_id"
OBJECT_KEY = "data/payload.json"
EXPECTED_BODY = b'{"hello":"tigris"}'


def _trial_id():
    return pathlib.Path(TRIAL_ID_PATH).read_text().strip()


def _bucket_name():
    import re
    name = f"harbor-boto3-{_trial_id()}"
    name = re.sub(r"[^a-z0-9.-]", "-", name.lower())
    return name


def _s3_client():
    """Build a boto3 S3 client targeting Tigris using the verifier's env."""
    import boto3
    from botocore.client import Config

    endpoint = os.environ.get("AWS_ENDPOINT_URL_S3")
    assert endpoint, "AWS_ENDPOINT_URL_S3 must be set in the verifier environment."
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        config=Config(s3={"addressing_style": "virtual"}),
    )


@pytest.fixture(scope="module", autouse=True)
def cleanup_bucket_after_tests():
    """Best-effort teardown: remove every object then delete the bucket."""
    yield
    try:
        client = _s3_client()
        bucket = _bucket_name()
        # Delete objects in batches; ignore "no such bucket" type errors.
        paginator = client.get_paginator("list_objects_v2")
        try:
            for page in paginator.paginate(Bucket=bucket):
                contents = page.get("Contents") or []
                if not contents:
                    continue
                client.delete_objects(
                    Bucket=bucket,
                    Delete={"Objects": [{"Key": obj["Key"]} for obj in contents]},
                )
        except Exception:
            pass
        try:
            client.delete_bucket(Bucket=bucket)
        except Exception:
            pass
    except Exception:
        # Cleanup is best-effort; never let it mask the real test result.
        pass


def test_boto3_installed_in_verifier():
    """The verifier itself relies on boto3 — make sure the import works."""
    result = subprocess.run(
        ["python3", "-c", "import boto3; print(boto3.__version__)"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"boto3 must be importable in the verifier env. stderr={result.stderr!r}"
    )


def test_roundtrip_script_exists():
    assert os.path.isfile(SCRIPT_PATH), (
        f"Expected agent to create the boto3 roundtrip script at {SCRIPT_PATH}, "
        "but it is missing."
    )


def test_object_listed_in_bucket():
    """Priority 1: use boto3 list_objects_v2 to confirm the object was uploaded."""
    client = _s3_client()
    bucket = _bucket_name()
    try:
        response = client.list_objects_v2(Bucket=bucket)
    except Exception as exc:
        pytest.fail(
            f"list_objects_v2 on bucket {bucket!r} failed: {exc!r}. "
            "The agent's script was expected to create this bucket via boto3."
        )
    contents = response.get("Contents") or []
    keys = [obj.get("Key") for obj in contents]
    assert OBJECT_KEY in keys, (
        f"Expected object key {OBJECT_KEY!r} to be present in bucket "
        f"{bucket!r}, but listing returned: {keys!r}"
    )


def test_object_body_matches_remote():
    """Priority 1: download the object via boto3 and check the exact bytes."""
    client = _s3_client()
    bucket = _bucket_name()
    try:
        response = client.get_object(Bucket=bucket, Key=OBJECT_KEY)
    except Exception as exc:
        pytest.fail(
            f"get_object on s3://{bucket}/{OBJECT_KEY} failed: {exc!r}. "
            "The agent's script must have uploaded this object."
        )
    body = response["Body"].read()
    assert body == EXPECTED_BODY, (
        f"Object body for s3://{bucket}/{OBJECT_KEY} does not match expected "
        f"payload. expected={EXPECTED_BODY!r} got={body!r}"
    )


def test_local_downloaded_file_matches():
    """Priority 3: confirm the local downloaded.json exactly matches the payload."""
    assert os.path.isfile(DOWNLOAD_PATH), (
        f"Expected agent's script to write the downloaded payload to "
        f"{DOWNLOAD_PATH}, but the file is missing."
    )
    with open(DOWNLOAD_PATH, "rb") as fh:
        local_bytes = fh.read()
    assert local_bytes == EXPECTED_BODY, (
        f"Local file {DOWNLOAD_PATH} does not contain the exact downloaded "
        f"bytes. expected={EXPECTED_BODY!r} got={local_bytes!r}"
    )
