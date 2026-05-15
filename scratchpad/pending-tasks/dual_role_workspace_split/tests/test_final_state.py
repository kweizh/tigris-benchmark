import json
import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/dual-role"
INDEX_TS = os.path.join(PROJECT_DIR, "index.ts")
RESULT_JSON = os.path.join(PROJECT_DIR, "result.json")
WRITER_BUCKET = "writer-ws"
READER_BUCKET = "reader-ws"


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
        "index.ts must call teardownWorkspace to clean up the workspaces."
    )
    assert "@aws-sdk/client-s3" in contents, (
        "index.ts must import from '@aws-sdk/client-s3'."
    )
    assert "PutObjectCommand" in contents, (
        "index.ts must use PutObjectCommand from @aws-sdk/client-s3."
    )
    assert "Promise.all" in contents, (
        "index.ts must issue the two createWorkspace calls concurrently "
        "via Promise.all (the task requires parallel provisioning)."
    )


def test_script_runs_successfully():
    """Priority 1: Execute the user's script end-to-end against real Tigris."""
    result = subprocess.run(
        ["npx", "tsx", "index.ts"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        timeout=300,
    )
    assert result.returncode == 0, (
        f"'npx tsx index.ts' exited with {result.returncode}. "
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_result_json_has_expected_flags():
    """Priority 3: parse the result.json summary the script produced."""
    assert os.path.isfile(RESULT_JSON), (
        f"Expected the user's script to produce {RESULT_JSON}."
    )
    with open(RESULT_JSON) as f:
        data = json.load(f)
    assert data.get("writer_bucket") == WRITER_BUCKET, (
        f"Expected result.json.writer_bucket == '{WRITER_BUCKET}', "
        f"got {data.get('writer_bucket')!r}."
    )
    assert data.get("reader_bucket") == READER_BUCKET, (
        f"Expected result.json.reader_bucket == '{READER_BUCKET}', "
        f"got {data.get('reader_bucket')!r}."
    )
    assert data.get("writer_put_ok") is True, (
        f"Expected result.json.writer_put_ok == true (Editor key uploaded "
        f"successfully). Got {data.get('writer_put_ok')!r}. Full result: {data}"
    )
    assert data.get("readonly_put_blocked") is True, (
        f"Expected result.json.readonly_put_blocked == true (ReadOnly key "
        f"must have been rejected). Got {data.get('readonly_put_blocked')!r}. "
        f"Full result: {data}"
    )


def test_workspaces_torn_down():
    """Priority 1: Use the Tigris CLI to confirm both workspace buckets no
    longer exist after the script ran."""
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
        assert WRITER_BUCKET not in tokens, (
            f"Workspace bucket '{WRITER_BUCKET}' still appears in "
            f"'tigris bucket list' output — teardownWorkspace did not run "
            f"for the writer. Full output:\n{combined}"
        )
        assert READER_BUCKET not in tokens, (
            f"Workspace bucket '{READER_BUCKET}' still appears in "
            f"'tigris bucket list' output — teardownWorkspace did not run "
            f"for the reader. Full output:\n{combined}"
        )
