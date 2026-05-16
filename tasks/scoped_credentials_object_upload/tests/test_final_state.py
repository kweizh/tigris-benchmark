import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_DIR = "/home/user/scoped-upload"
INDEX_TS = os.path.join(PROJECT_DIR, "index.ts")
OUTPUT_LOG = os.path.join(PROJECT_DIR, "output.log")
WORKSPACE_BUCKET = "scoped-upload-ws"
SUCCESS_MARKER = f"SCOPED_UPLOAD_OK {WORKSPACE_BUCKET}"


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


def test_script_runs_successfully_and_emits_success_marker():
    """Priority 1: Execute the user's script end-to-end against real Tigris."""
    # Run the script, capturing stdout/stderr to output.log so we can inspect
    # the success marker afterwards.
    with open(OUTPUT_LOG, "w") as logf:
        result = subprocess.run(
            ["npx", "tsx", "index.ts"],
            cwd=PROJECT_DIR,
            stdout=logf,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
            timeout=300,
        )
    assert os.path.isfile(OUTPUT_LOG), f"Expected log file at {OUTPUT_LOG}."
    with open(OUTPUT_LOG) as f:
        log_contents = f.read()
    assert result.returncode == 0, (
        f"'npx tsx index.ts' exited with {result.returncode}. "
        f"Output:\n{log_contents}"
    )
    assert SUCCESS_MARKER in log_contents, (
        f"Expected success marker '{SUCCESS_MARKER}' in script output. "
        f"Got:\n{log_contents}"
    )


def test_workspace_bucket_torn_down():
    """Priority 1: Use the Tigris CLI to confirm the workspace bucket no
    longer exists after the script ran."""
    cmd = _tigris_cmd() + ["bucket", "list"]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=60, env=os.environ.copy()
    )
    assert result.returncode == 0, (
        f"'tigris bucket list' failed: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    combined = result.stdout + "\n" + result.stderr
    # The workspace bucket name should be absent because teardownWorkspace
    # deleted it. We assert the exact bucket token does not appear as a
    # listed bucket.
    for line in combined.splitlines():
        # Split on whitespace and compare exact tokens to avoid spurious
        # substring matches.
        tokens = line.strip().split()
        assert WORKSPACE_BUCKET not in tokens, (
            f"Workspace bucket '{WORKSPACE_BUCKET}' still appears in "
            f"'tigris bucket list' output — teardownWorkspace did not run. "
            f"Full output:\n{combined}"
        )
