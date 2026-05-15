import os
import pathlib
import subprocess
from urllib.parse import urlparse, parse_qs

import pytest

PROJECT_DIR = "/home/user/tigris-task"
PRESIGNED_URL_PATH = os.path.join(PROJECT_DIR, "presigned.url")
DOWNLOAD_PATH = os.path.join(PROJECT_DIR, "downloaded.txt")
TRIAL_ID_PATH = "/logs/artifacts/trial_id"
OBJECT_KEY = "share/secret.txt"
EXPECTED_BODY = b"shareable content"


def _trial_id():
    return pathlib.Path(TRIAL_ID_PATH).read_text().strip()


def _bucket_name():
    import re
    name = f"harbor-presign-{_trial_id()}"
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


def _read_presigned_url():
    assert os.path.isfile(PRESIGNED_URL_PATH), (
        f"Expected agent to write the presigned URL to {PRESIGNED_URL_PATH}, "
        "but the file is missing."
    )
    with open(PRESIGNED_URL_PATH, "r") as fh:
        url = fh.read().strip()
    assert url, f"{PRESIGNED_URL_PATH} exists but is empty."
    return url


@pytest.fixture(scope="module", autouse=True)
def cleanup_bucket_after_tests():
    """Best-effort teardown: remove every object then delete the bucket."""
    yield
    try:
        client = _s3_client()
        bucket = _bucket_name()
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


def test_presigned_url_file_exists_and_nonempty():
    url = _read_presigned_url()
    assert url.startswith(("http://", "https://")), (
        f"Expected {PRESIGNED_URL_PATH} to contain a single HTTP(S) URL, "
        f"got: {url!r}"
    )


def test_presigned_url_targets_tigris_host():
    url = _read_presigned_url()
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    assert "t3.storage.dev" in host, (
        f"Expected the presigned URL host to be a Tigris virtual-hosted-style "
        f"hostname containing 't3.storage.dev', got host={host!r} url={url!r}"
    )


def test_presigned_url_has_sigv4_signature_query_param():
    url = _read_presigned_url()
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    assert "X-Amz-Signature" in query_params, (
        f"Expected the presigned URL's query string to contain the SigV4 "
        f"parameter 'X-Amz-Signature'. Got query params: {sorted(query_params)!r} "
        f"url={url!r}"
    )
    signature = query_params["X-Amz-Signature"][0]
    assert signature, (
        f"X-Amz-Signature query parameter is present but empty. url={url!r}"
    )


def test_presigned_url_downloads_with_curl_unauthenticated(tmp_path):
    """Priority 1: re-fetch the presigned URL with curl, with every Tigris/AWS
    credential env var unset, and confirm the body equals 'shareable content'."""
    url = _read_presigned_url()
    out_file = tmp_path / "verifier-download.bin"
    env = {
        k: v
        for k, v in os.environ.items()
        if k
        not in {
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "TIGRIS_STORAGE_ACCESS_KEY_ID",
            "TIGRIS_STORAGE_SECRET_ACCESS_KEY",
        }
    }
    # Defensive: also make sure those keys are not present at all.
    for forbidden in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "TIGRIS_STORAGE_ACCESS_KEY_ID",
        "TIGRIS_STORAGE_SECRET_ACCESS_KEY",
    ):
        env.pop(forbidden, None)
    result = subprocess.run(
        ["curl", "-fsSL", "--output", str(out_file), url],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"`curl -fsSL` against the presigned URL failed with returncode "
        f"{result.returncode}. stderr={result.stderr!r} stdout={result.stdout!r} "
        f"url={url!r}"
    )
    body = out_file.read_bytes()
    assert body == EXPECTED_BODY, (
        f"Body fetched via the presigned URL with no credentials does not "
        f"match. expected={EXPECTED_BODY!r} got={body!r}"
    )


def test_local_downloaded_file_matches():
    """Priority 3: confirm the agent's curl write produced the expected bytes."""
    assert os.path.isfile(DOWNLOAD_PATH), (
        f"Expected agent to write the curl-downloaded payload to "
        f"{DOWNLOAD_PATH}, but the file is missing."
    )
    with open(DOWNLOAD_PATH, "rb") as fh:
        local_bytes = fh.read()
    assert local_bytes == EXPECTED_BODY, (
        f"Local file {DOWNLOAD_PATH} does not contain the exact expected "
        f"bytes. expected={EXPECTED_BODY!r} got={local_bytes!r}"
    )


def test_object_body_matches_remote_via_boto3():
    """Priority 1: independently fetch the object via boto3 to prove it
    actually exists in the Tigris bucket the agent claimed to populate."""
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
