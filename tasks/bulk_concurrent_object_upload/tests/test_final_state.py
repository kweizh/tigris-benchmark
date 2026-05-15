import json
import os
import subprocess

import pytest

PROJECT_DIR = "/home/user/tigris-task"
BULK_SCRIPT = os.path.join(PROJECT_DIR, "bulk.py")
TIMING_FILE = os.path.join(PROJECT_DIR, "timing.txt")
TRIAL_ID_PATH = "/logs/artifacts/trial_id"

EXPECTED_KEYS = [f"events/event-{n:03d}.json" for n in range(1, 21)]


def _read_trial_id():
    assert os.path.isfile(TRIAL_ID_PATH), (
        f"Expected trial id file at {TRIAL_ID_PATH} to exist."
    )
    with open(TRIAL_ID_PATH) as f:
        trial_id = f.read().strip()
    assert trial_id, f"{TRIAL_ID_PATH} must contain a non-empty trial id."
    return trial_id


def _bucket_name():
    import re
    name = f"harbor-bulk-{_read_trial_id()}"
    name = re.sub(r"[^a-z0-9.-]", "-", name.lower())
    return name


def _make_client():
    """Build a boto3 S3 client wired to Tigris using the verifier's env vars."""
    try:
        import boto3
        from botocore.client import Config
    except ImportError as exc:  # pragma: no cover - environment misconfig
        pytest.fail(f"boto3/botocore must be importable in the verifier env: {exc}")

    access_key = os.environ.get("TIGRIS_STORAGE_ACCESS_KEY_ID")
    secret_key = os.environ.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY")
    assert access_key, "TIGRIS_STORAGE_ACCESS_KEY_ID must be set in the verifier env."
    assert secret_key, "TIGRIS_STORAGE_SECRET_ACCESS_KEY must be set in the verifier env."

    endpoint_url = os.environ.get("AWS_ENDPOINT_URL_S3", "https://t3.storage.dev")
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=os.environ.get("AWS_REGION", "auto"),
        config=Config(s3={"addressing_style": "virtual"}),
    )


@pytest.fixture(scope="module")
def s3_client():
    return _make_client()


@pytest.fixture(scope="module", autouse=True)
def cleanup_bucket_after_tests(s3_client):
    """Yield to the tests, then delete every object in the bucket and the bucket
    itself so the trial leaves no residue on Tigris. Best-effort: ignore
    failures if the bucket is already gone."""
    yield
    try:
        bucket = _bucket_name()
    except AssertionError:
        return
    try:
        # List & delete all objects under any prefix in the bucket.
        paginator = s3_client.get_paginator("list_objects_v2")
        to_delete = []
        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []) or []:
                to_delete.append({"Key": obj["Key"]})
                if len(to_delete) == 1000:
                    s3_client.delete_objects(
                        Bucket=bucket, Delete={"Objects": to_delete}
                    )
                    to_delete = []
        if to_delete:
            s3_client.delete_objects(Bucket=bucket, Delete={"Objects": to_delete})
    except Exception:
        pass
    try:
        s3_client.delete_bucket(Bucket=bucket)
    except Exception:
        pass


def test_bulk_script_exists():
    assert os.path.isfile(BULK_SCRIPT), (
        f"Expected the agent to have created the bulk upload script at "
        f"{BULK_SCRIPT}, but the file does not exist."
    )


def test_timing_file_is_positive_integer_ms():
    assert os.path.isfile(TIMING_FILE), (
        f"Expected the agent to have written a timing file at {TIMING_FILE}, "
        "but the file does not exist."
    )
    with open(TIMING_FILE) as f:
        raw = f.read().strip()
    assert raw, f"{TIMING_FILE} exists but is empty; expected a positive integer of milliseconds."
    try:
        value = int(raw, 10)
    except ValueError:
        pytest.fail(
            f"Expected {TIMING_FILE} to contain a single base-10 integer of "
            f"milliseconds, got: {raw!r}"
        )
    assert value >= 1, (
        f"Expected {TIMING_FILE} to contain a positive integer (>= 1) of "
        f"milliseconds, got: {value}"
    )


def test_exactly_20_objects_under_events_prefix(s3_client):
    """Priority 1 (SDK): list_objects_v2 must return exactly the 20 expected keys."""
    bucket = _bucket_name()
    keys = []
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix="events/"):
        for obj in page.get("Contents", []) or []:
            keys.append(obj["Key"])

    assert len(keys) == 20, (
        f"Expected exactly 20 objects under prefix events/ in bucket {bucket}, "
        f"got {len(keys)}: {sorted(keys)}"
    )
    assert sorted(keys) == EXPECTED_KEYS, (
        f"Expected the 20 keys to be exactly {EXPECTED_KEYS}, got {sorted(keys)}."
    )


def test_each_object_body_matches_expected_json(s3_client):
    """Priority 1 (SDK): for each N in 1..20 the object body must equal
    {"id": "<NNN>", "ts": "2024-01-01"} where <NNN> is the key's zero-padded
    index."""
    bucket = _bucket_name()
    mismatches = []
    for n in range(1, 21):
        n_str = f"{n:03d}"
        key = f"events/event-{n_str}.json"
        try:
            resp = s3_client.get_object(Bucket=bucket, Key=key)
            body = resp["Body"].read()
        except Exception as exc:  # NoSuchKey, NoSuchBucket, network, etc.
            mismatches.append(f"{key}: get_object failed: {exc!r}")
            continue
        try:
            doc = json.loads(body)
        except json.JSONDecodeError as exc:
            mismatches.append(f"{key}: body is not valid JSON ({exc}); raw={body!r}")
            continue
        expected = {"id": n_str, "ts": "2024-01-01"}
        if doc != expected:
            mismatches.append(f"{key}: expected {expected}, got {doc}")
    assert not mismatches, (
        "One or more uploaded objects had unexpected contents:\n  - "
        + "\n  - ".join(mismatches)
    )
