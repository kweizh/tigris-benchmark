import json
import os
import re
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/resilient"
INDEX_TS = os.path.join(PROJECT_DIR, "index.ts")
RESULT_JSON = os.path.join(PROJECT_DIR, "result.json")
RUN_LOG = os.path.join(PROJECT_DIR, "run.log")
WORKSPACE_BUCKET = "resilient-ws"


def _tigris_cmd():
    """Return the command list for invoking the Tigris CLI."""
    if shutil.which("tigris") is not None:
        return ["tigris"]
    local = os.path.join(PROJECT_DIR, "node_modules", ".bin", "tigris")
    if os.path.isfile(local):
        return [local]
    pytest.fail("Tigris CLI binary is not available on PATH or in node_modules/.bin.")


def test_index_ts_created():
    assert os.path.isfile(INDEX_TS), (
        f"User must create the TypeScript script at {INDEX_TS}."
    )


def test_index_ts_uses_required_apis():
    with open(INDEX_TS) as f:
        contents = f.read()
    assert "@tigrisdata/agent-kit" in contents, (
        "index.ts must import from '@tigrisdata/agent-kit'."
    )
    assert "createWorkspace" in contents, (
        "index.ts must call createWorkspace from @tigrisdata/agent-kit."
    )
    assert "teardownWorkspace" in contents, (
        "index.ts must call teardownWorkspace to clean up the workspace."
    )
    assert "@aws-sdk/client-s3" in contents, (
        "index.ts must import from '@aws-sdk/client-s3'."
    )
    assert "PutObjectCommand" in contents, (
        "index.ts must use PutObjectCommand from @aws-sdk/client-s3 to upload."
    )


def test_index_ts_contains_retry_loop():
    """Static check: index.ts must contain a retry loop with exponential
    backoff sleeps implemented via `await new Promise(... setTimeout ...)`."""
    with open(INDEX_TS) as f:
        contents = f.read()
    # Strip line comments and block comments to avoid false positives where
    # the user just talks about "for" or "while" in a comment.
    no_block_comments = re.sub(r"/\*.*?\*/", "", contents, flags=re.DOTALL)
    no_comments = re.sub(r"//[^\n]*", "", no_block_comments)

    has_for = re.search(r"\bfor\s*\(", no_comments) is not None
    has_while = re.search(r"\bwhile\s*\(", no_comments) is not None
    assert has_for or has_while, (
        "index.ts must implement a retry loop using `for` or `while`. "
        "Neither construct was found in the source."
    )

    # Count `await new Promise` occurrences; we need at least two distinct
    # sleeps for an exponential backoff schedule (1000 ms, 2000 ms, 4000 ms).
    await_new_promise_count = len(
        re.findall(r"await\s+new\s+Promise", no_comments)
    )
    assert await_new_promise_count >= 2, (
        f"index.ts must contain at least two `await new Promise(...)` "
        f"expressions for the exponential backoff sleeps. "
        f"Found {await_new_promise_count}."
    )

    # And it must use setTimeout to actually delay execution.
    set_timeout_count = len(re.findall(r"\bsetTimeout\s*\(", no_comments))
    assert set_timeout_count >= 1, (
        "index.ts must use `setTimeout` inside `await new Promise(...)` to "
        "implement the backoff sleeps."
    )


def test_script_runs_and_exits_zero():
    """Priority 1: execute the user's script end-to-end against real Tigris.
    The script must exit with status 0 in both the success and the
    exhausted-retry failure cases."""
    with open(RUN_LOG, "w") as logf:
        result = subprocess.run(
            ["npx", "tsx", "index.ts"],
            cwd=PROJECT_DIR,
            stdout=logf,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
            timeout=300,
        )
    assert os.path.isfile(RUN_LOG), f"Expected run log at {RUN_LOG}."
    with open(RUN_LOG) as f:
        log_contents = f.read()
    assert result.returncode == 0, (
        f"'npx tsx index.ts' exited with {result.returncode}. "
        f"Output:\n{log_contents}"
    )


def test_result_json_shape():
    assert os.path.isfile(RESULT_JSON), (
        f"User script must produce {RESULT_JSON}."
    )
    with open(RESULT_JSON) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            pytest.fail(
                f"{RESULT_JSON} is not valid JSON: {e}. "
                f"Contents:\n{open(RESULT_JSON).read()}"
            )
    assert isinstance(data, dict), (
        f"{RESULT_JSON} must contain a JSON object, got {type(data).__name__}."
    )
    assert "status" in data, f"{RESULT_JSON} must include a 'status' field."
    assert data["status"] in ("ok", "failed"), (
        f"'status' in {RESULT_JSON} must be 'ok' or 'failed', "
        f"got {data['status']!r}."
    )
    assert "attempts" in data, f"{RESULT_JSON} must include an 'attempts' field."
    assert isinstance(data["attempts"], int), (
        f"'attempts' in {RESULT_JSON} must be an integer, "
        f"got {type(data['attempts']).__name__}."
    )
    assert 1 <= data["attempts"] <= 3, (
        f"'attempts' in {RESULT_JSON} must be between 1 and 3 inclusive, "
        f"got {data['attempts']}."
    )
    if data["status"] == "ok":
        assert "bucket" in data, (
            f"When status is 'ok', {RESULT_JSON} must include a 'bucket' field."
        )
        assert data["bucket"] == WORKSPACE_BUCKET, (
            f"When status is 'ok', 'bucket' must equal {WORKSPACE_BUCKET!r}, "
            f"got {data['bucket']!r}."
        )
    elif data["status"] == "failed":
        assert data["attempts"] == 3, (
            f"When status is 'failed', 'attempts' must equal 3 "
            f"(retry exhaustion); got {data['attempts']}."
        )


def test_workspace_bucket_torn_down():
    """Priority 1: use the Tigris CLI to confirm the workspace bucket no
    longer exists after the script ran. This holds for both the success path
    (final teardownWorkspace call) and the failure path (orphan teardown
    inside the retry loop)."""
    cmd = _tigris_cmd() + ["bucket", "list"]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=60, env=os.environ.copy()
    )
    assert result.returncode == 0, (
        f"'tigris bucket list' failed: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    combined = result.stdout + "\n" + result.stderr
    for line in combined.splitlines():
        tokens = line.strip().split()
        assert WORKSPACE_BUCKET not in tokens, (
            f"Workspace bucket '{WORKSPACE_BUCKET}' still appears in "
            f"'tigris bucket list' output — teardown did not run. "
            f"Full output:\n{combined}"
        )
