import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_DIR = "/home/user/seeded-fork"
INDEX_TS = os.path.join(PROJECT_DIR, "index.ts")
FORKS_JSON = os.path.join(PROJECT_DIR, "forks.json")
OUTPUT_LOG = os.path.join(PROJECT_DIR, "output.log")
SOURCE_BUCKET = "seed-corpus"
FORK_PREFIX = "eval-dispatch"
EXPECTED_KEYS = {"a.txt", "b.txt", "c.txt"}


def _tigris_cmd():
    """Return the command list for invoking the Tigris CLI."""
    if shutil.which("tigris") is not None:
        return ["tigris"]
    local = os.path.join(PROJECT_DIR, "node_modules", ".bin", "tigris")
    if os.path.isfile(local):
        return [local]
    pytest.fail(
        "Tigris CLI binary is not available on PATH or in node_modules/.bin."
    )


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
    assert "createForks" in contents, (
        "index.ts must call createForks from @tigrisdata/agent-kit."
    )
    assert "teardownForks" in contents, (
        "index.ts must call teardownForks to clean up the fork buckets."
    )
    assert "@aws-sdk/client-s3" in contents, (
        "index.ts must import from '@aws-sdk/client-s3'."
    )
    assert "PutObjectCommand" in contents, (
        "index.ts must use PutObjectCommand from @aws-sdk/client-s3 to upload."
    )
    assert SOURCE_BUCKET in contents, (
        f"index.ts must reference the source bucket '{SOURCE_BUCKET}'."
    )
    assert FORK_PREFIX in contents, (
        f"index.ts must use the fork prefix '{FORK_PREFIX}'."
    )


@pytest.fixture(scope="module")
def run_user_script():
    """Priority 1: Execute the user's script end-to-end against real Tigris."""
    # Clean any previous output/manifest so the run is fresh.
    for path in (FORKS_JSON, OUTPUT_LOG):
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    with open(OUTPUT_LOG, "w") as logf:
        result = subprocess.run(
            ["npx", "tsx", "index.ts"],
            cwd=PROJECT_DIR,
            stdout=logf,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
            timeout=300,
        )

    with open(OUTPUT_LOG) as f:
        log_contents = f.read()

    return result, log_contents


def test_script_exits_zero(run_user_script):
    result, log_contents = run_user_script
    assert result.returncode == 0, (
        f"'npx tsx index.ts' exited with {result.returncode}. "
        f"Output:\n{log_contents}"
    )


def test_forks_json_exists_and_has_two_unique_fork_names(run_user_script):
    run_user_script  # ensure script ran
    assert os.path.isfile(FORKS_JSON), (
        f"Expected fork manifest at {FORKS_JSON} after running index.ts."
    )
    with open(FORKS_JSON) as f:
        data = json.load(f)
    assert isinstance(data, dict), (
        f"{FORKS_JSON} must be a JSON object, got {type(data).__name__}."
    )
    assert "forks" in data, (
        f"{FORKS_JSON} must contain a top-level 'forks' field."
    )
    forks = data["forks"]
    assert isinstance(forks, list), (
        f"'forks' field in {FORKS_JSON} must be an array, got "
        f"{type(forks).__name__}."
    )
    assert len(forks) == 2, (
        f"Expected exactly 2 fork bucket names in {FORKS_JSON}, got "
        f"{len(forks)}: {forks}"
    )
    assert all(isinstance(n, str) for n in forks), (
        f"All fork bucket names in {FORKS_JSON} must be strings: {forks}"
    )
    assert len(set(forks)) == 2, (
        f"Fork bucket names in {FORKS_JSON} must be unique: {forks}"
    )
    for name in forks:
        assert name.startswith(FORK_PREFIX), (
            f"Fork bucket name '{name}' in {FORKS_JSON} must start with "
            f"prefix '{FORK_PREFIX}'."
        )


def test_seed_corpus_contains_expected_objects(run_user_script):
    """Priority 1: Use the Tigris CLI to confirm the seed bucket now contains
    exactly the three expected keys."""
    run_user_script  # ensure script ran
    cmd = _tigris_cmd() + ["objects", "list", SOURCE_BUCKET]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, (
        f"'tigris objects list {SOURCE_BUCKET}' failed: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    combined = result.stdout + "\n" + result.stderr
    found = set()
    for key in EXPECTED_KEYS:
        if key in combined:
            found.add(key)
    missing = EXPECTED_KEYS - found
    assert not missing, (
        f"Expected keys {sorted(EXPECTED_KEYS)} in bucket '{SOURCE_BUCKET}', "
        f"missing: {sorted(missing)}. CLI output:\n{combined}"
    )


def test_fork_buckets_were_torn_down(run_user_script):
    """Priority 1: Use the Tigris CLI to confirm neither fork bucket exists
    anymore after teardownForks ran."""
    run_user_script  # ensure script ran
    with open(FORKS_JSON) as f:
        data = json.load(f)
    forks = data["forks"]

    cmd = _tigris_cmd() + ["buckets", "list"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, (
        f"'tigris buckets list' failed: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    combined = result.stdout + "\n" + result.stderr
    listed_tokens = set()
    for line in combined.splitlines():
        for tok in line.strip().split():
            listed_tokens.add(tok)

    for fork_name in forks:
        assert fork_name not in listed_tokens, (
            f"Fork bucket '{fork_name}' still appears in 'tigris buckets "
            f"list' output — teardownForks did not delete it. Full "
            f"output:\n{combined}"
        )


def test_cleanup_seed_corpus_bucket(run_user_script):
    """Verifier cleanup: delete the source seed bucket so the task leaves no
    residue. This runs at the end of the test session."""
    run_user_script  # ensure script ran first
    cmd = _tigris_cmd() + ["buckets", "delete", SOURCE_BUCKET, "--force"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )
    # Best-effort: if the bucket doesn't exist or the flag differs, fall back
    # to the plain delete. We do not fail the test suite on cleanup errors,
    # but we do surface them in the assertion message so the operator notices.
    if result.returncode != 0:
        fallback = subprocess.run(
            _tigris_cmd() + ["buckets", "delete", SOURCE_BUCKET],
            capture_output=True,
            text=True,
            timeout=120,
            env=os.environ.copy(),
        )
        assert fallback.returncode == 0 or "not found" in (
            fallback.stderr.lower() + fallback.stdout.lower()
        ), (
            f"Failed to clean up source bucket '{SOURCE_BUCKET}'. "
            f"First attempt: stdout={result.stdout!r} stderr={result.stderr!r}. "
            f"Fallback attempt: stdout={fallback.stdout!r} "
            f"stderr={fallback.stderr!r}."
        )
