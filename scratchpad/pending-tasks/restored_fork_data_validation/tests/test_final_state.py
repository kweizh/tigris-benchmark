import hashlib
import json
import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/restore-validate"
INDEX_TS = os.path.join(PROJECT_DIR, "index.ts")
SETUP_SCRIPT = os.path.join(PROJECT_DIR, "setup.sh")
OUTPUT_LOG = os.path.join(PROJECT_DIR, "output.log")
RESULT_JSON = os.path.join(PROJECT_DIR, "result.json")
SNAPSHOT_ID_FILE = os.path.join(PROJECT_DIR, "snapshot_id.txt")
EXPECTED_SHA_FILE = os.path.join(PROJECT_DIR, "expected_sha256.txt")
MANIFEST_FILE = os.path.join(PROJECT_DIR, "manifest.json")

SOURCE_BUCKET = "archive-bucket"
FORK_PREFIX = "validation-fork"
OBJECT_KEY = "manifest.json"


def _tigris_cmd():
    if shutil.which("tigris") is not None:
        return ["tigris"]
    local = os.path.join(PROJECT_DIR, "node_modules", ".bin", "tigris")
    if os.path.isfile(local):
        return [local]
    pytest.fail(
        "Tigris CLI binary is not available on PATH or in node_modules/.bin."
    )


def _delete_bucket(bucket):
    cmd = _tigris_cmd() + ["buckets", "delete", bucket, "--yes"]
    subprocess.run(
        cmd, capture_output=True, text=True, timeout=120,
        env=os.environ.copy(),
    )


def _bucket_exists(bucket):
    cmd = _tigris_cmd() + ["bucket", "list"]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=60,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        return False
    combined = result.stdout + "\n" + result.stderr
    for line in combined.splitlines():
        tokens = line.strip().split()
        if bucket in tokens:
            return True
    return False


@pytest.fixture(scope="module")
def restored_bucket():
    """Prepare the source bucket, run the user's script, then clean up.

    Yields the restored fork bucket name reported by result.json.
    """
    assert os.path.isfile(INDEX_TS), (
        f"User must create the TypeScript script at {INDEX_TS}."
    )
    assert os.path.isfile(SETUP_SCRIPT), (
        f"setup.sh missing at {SETUP_SCRIPT}."
    )

    # 1. Re-run setup.sh to deterministically prepare archive-bucket and
    #    refresh snapshot_id.txt / expected_sha256.txt.
    setup_result = subprocess.run(
        ["bash", SETUP_SCRIPT],
        capture_output=True, text=True, timeout=300,
        cwd=PROJECT_DIR, env=os.environ.copy(),
    )
    assert setup_result.returncode == 0, (
        f"setup.sh failed: stdout={setup_result.stdout!r} "
        f"stderr={setup_result.stderr!r}"
    )
    assert os.path.isfile(SNAPSHOT_ID_FILE), (
        f"setup.sh did not produce {SNAPSHOT_ID_FILE}."
    )
    assert os.path.isfile(EXPECTED_SHA_FILE), (
        f"setup.sh did not produce {EXPECTED_SHA_FILE}."
    )

    # 2. Best-effort delete of any leftover fork from a previous run.
    _delete_bucket(FORK_PREFIX)
    # Give Tigris a moment to converge before the restore call.
    import time
    time.sleep(3)

    # 3. Remove any stale result.json or log so the script starts clean.
    for stale in (RESULT_JSON, OUTPUT_LOG):
        if os.path.exists(stale):
            os.remove(stale)

    # 4. Execute the user's script end-to-end.
    with open(OUTPUT_LOG, "w") as logf:
        run_result = subprocess.run(
            ["npx", "tsx", "index.ts"],
            cwd=PROJECT_DIR,
            stdout=logf,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
            timeout=300,
        )
    with open(OUTPUT_LOG) as f:
        log_contents = f.read()
    assert run_result.returncode == 0, (
        f"'npx tsx index.ts' exited with {run_result.returncode}. "
        f"Output:\n{log_contents}"
    )
    assert os.path.isfile(RESULT_JSON), (
        f"Expected user script to produce {RESULT_JSON}. "
        f"Log:\n{log_contents}"
    )

    with open(RESULT_JSON) as f:
        result = json.load(f)
    bucket = result.get("bucket")
    assert isinstance(bucket, str) and bucket, (
        f"result.json must include a non-empty string 'bucket'. Got: {result!r}"
    )

    yield {"result": result, "bucket": bucket, "log": log_contents}

    # Cleanup: delete the restored fork and the source archive-bucket.
    _delete_bucket(bucket)
    _delete_bucket(SOURCE_BUCKET)


def test_index_ts_uses_required_apis():
    assert os.path.isfile(INDEX_TS), (
        f"User must create the TypeScript script at {INDEX_TS}."
    )
    with open(INDEX_TS) as f:
        contents = f.read()
    assert "@tigrisdata/agent-kit" in contents, (
        "index.ts must import from '@tigrisdata/agent-kit'."
    )
    assert "restore" in contents, (
        "index.ts must call 'restore' from @tigrisdata/agent-kit."
    )
    assert "@aws-sdk/client-s3" in contents, (
        "index.ts must import from '@aws-sdk/client-s3'."
    )
    assert "GetObjectCommand" in contents, (
        "index.ts must use GetObjectCommand from @aws-sdk/client-s3 to "
        "download manifest.json from the restored fork."
    )
    assert "validation-fork" in contents, (
        "index.ts must reference the fork name 'validation-fork'."
    )


def test_result_json_reports_validation_fork_bucket(restored_bucket):
    result = restored_bucket["result"]
    bucket = result["bucket"]
    assert bucket.startswith(FORK_PREFIX), (
        f"result.json 'bucket' must start with '{FORK_PREFIX}', got: {bucket!r}"
    )


def test_result_json_reports_sha256_match(restored_bucket):
    result = restored_bucket["result"]
    assert result.get("sha256_match") is True, (
        f"result.json must contain 'sha256_match': true, got: {result!r}"
    )
    sha = result.get("sha256")
    expected = result.get("expected_sha256")
    assert isinstance(sha, str) and isinstance(expected, str), (
        f"result.json must contain string 'sha256' and 'expected_sha256' "
        f"fields, got: {result!r}"
    )
    assert sha.lower() == expected.lower(), (
        f"result.json 'sha256' ({sha!r}) must equal 'expected_sha256' "
        f"({expected!r})."
    )


def test_restored_bucket_listed_via_tigris_cli(restored_bucket):
    """Priority 1: Use the Tigris CLI to confirm the fork bucket exists."""
    bucket = restored_bucket["bucket"]
    cmd = _tigris_cmd() + ["bucket", "list"]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=60,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, (
        f"'tigris bucket list' failed: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    combined = result.stdout + "\n" + result.stderr
    found = False
    for line in combined.splitlines():
        tokens = line.strip().split()
        if bucket in tokens:
            found = True
            break
    assert found, (
        f"Restored fork bucket '{bucket}' was not listed by "
        f"'tigris bucket list'. Output:\n{combined}"
    )


def test_independent_download_matches_expected_sha256(restored_bucket, tmp_path):
    """Priority 1: independently download the object via the AWS CLI and
    re-verify the SHA256 matches expected_sha256.txt."""
    bucket = restored_bucket["bucket"]
    endpoint = os.environ.get("TIGRIS_STORAGE_ENDPOINT", "https://t3.storage.dev")

    aws_env = os.environ.copy()
    aws_env["AWS_ACCESS_KEY_ID"] = os.environ["TIGRIS_STORAGE_ACCESS_KEY_ID"]
    aws_env["AWS_SECRET_ACCESS_KEY"] = os.environ["TIGRIS_STORAGE_SECRET_ACCESS_KEY"]
    aws_env["AWS_REGION"] = "auto"
    aws_env["AWS_DEFAULT_REGION"] = "auto"

    download_path = tmp_path / "manifest.json"
    cmd = [
        "aws", "s3", "cp",
        f"s3://{bucket}/{OBJECT_KEY}",
        str(download_path),
        "--endpoint-url", endpoint,
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=120, env=aws_env,
    )
    assert result.returncode == 0, (
        f"'aws s3 cp' from restored fork failed: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    assert download_path.is_file(), (
        f"Independent download did not produce a file at {download_path}."
    )

    actual = hashlib.sha256(download_path.read_bytes()).hexdigest()
    with open(EXPECTED_SHA_FILE) as f:
        expected = f.read().strip().lower()
    assert actual.lower() == expected, (
        f"Independent SHA256 of downloaded manifest.json ({actual}) does "
        f"not match expected_sha256.txt ({expected})."
    )
