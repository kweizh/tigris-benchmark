import json
import os
import re
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/isolation"
INDEX_TS = os.path.join(PROJECT_DIR, "index.ts")
AUDIT_JSON = os.path.join(PROJECT_DIR, "audit.json")
OUTPUT_LOG = os.path.join(PROJECT_DIR, "output.log")
SEED_KEYS = ["seed1.txt", "seed2.txt"]
AGENT_KEYS = {"agent-1.out", "agent-2.out", "agent-3.out"}
TRIAL_ID_FILE = "/logs/artifacts/trial_id"


def _read_trial_id():
    assert os.path.isfile(TRIAL_ID_FILE), (
        f"Trial id file {TRIAL_ID_FILE} does not exist; cannot derive bucket name."
    )
    with open(TRIAL_ID_FILE, "r") as f:
        trial_id = f.read().strip()
    assert trial_id, f"Trial id file {TRIAL_ID_FILE} is empty."
    return trial_id


def bucket_name():
    trial_id = _read_trial_id()
    name = f"harbor-isolation-{trial_id}"
    return re.sub(r"[^a-z0-9.-]", "-", name.lower())


def fork_prefix():
    trial_id = _read_trial_id()
    name = f"audit-fork-{trial_id}"
    return re.sub(r"[^a-z0-9.-]", "-", name.lower())


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
    assert "ListObjectsV2Command" in contents, (
        "index.ts must use ListObjectsV2Command from @aws-sdk/client-s3 to "
        "audit bucket state."
    )
    source_bucket = bucket_name()
    assert source_bucket in contents or "harbor-isolation" in contents, (
        f"index.ts must reference the source bucket '{source_bucket}'."
    )
    assert "audit-fork" in contents, (
        "index.ts must use the fork prefix 'audit-fork'."
    )


@pytest.fixture(scope="module")
def run_user_script():
    """Priority 1: Execute the user's script end-to-end against real Tigris."""
    # Clean any previous audit/log so the run is fresh.
    for path in (AUDIT_JSON, OUTPUT_LOG):
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


def test_audit_json_shape_and_contents(run_user_script):
    run_user_script  # ensure script ran
    assert os.path.isfile(AUDIT_JSON), (
        f"Expected audit report at {AUDIT_JSON} after running index.ts."
    )
    with open(AUDIT_JSON) as f:
        data = json.load(f)

    assert isinstance(data, dict), (
        f"{AUDIT_JSON} must be a JSON object, got {type(data).__name__}."
    )

    # --- source_keys -------------------------------------------------------
    assert "source_keys" in data, (
        f"{AUDIT_JSON} must contain a top-level 'source_keys' field."
    )
    source_keys = data["source_keys"]
    assert isinstance(source_keys, list), (
        f"'source_keys' in {AUDIT_JSON} must be an array, got "
        f"{type(source_keys).__name__}."
    )
    assert source_keys == SEED_KEYS, (
        f"'source_keys' must equal {SEED_KEYS} (sorted), got {source_keys}."
    )

    # --- fork_results ------------------------------------------------------
    assert "fork_results" in data, (
        f"{AUDIT_JSON} must contain a top-level 'fork_results' field."
    )
    fork_results = data["fork_results"]
    assert isinstance(fork_results, list), (
        f"'fork_results' in {AUDIT_JSON} must be an array, got "
        f"{type(fork_results).__name__}."
    )
    assert len(fork_results) == 3, (
        f"Expected exactly 3 fork_results entries, got {len(fork_results)}: "
        f"{fork_results}"
    )

    buckets_seen = []
    agent_keys_seen = []
    expected_fork_prefix = fork_prefix()
    for entry in fork_results:
        assert isinstance(entry, dict), (
            f"Each fork_results entry must be an object, got "
            f"{type(entry).__name__}: {entry}"
        )
        assert "bucket" in entry and isinstance(entry["bucket"], str), (
            f"Each fork_results entry must have a string 'bucket' field: {entry}"
        )
        assert "keys" in entry and isinstance(entry["keys"], list), (
            f"Each fork_results entry must have an array 'keys' field: {entry}"
        )
        bucket = entry["bucket"]
        keys = entry["keys"]
        assert bucket.startswith(expected_fork_prefix), (
            f"Fork bucket name '{bucket}' must start with prefix "
            f"'{expected_fork_prefix}'."
        )
        assert all(isinstance(k, str) for k in keys), (
            f"All keys for fork '{bucket}' must be strings: {keys}"
        )
        assert keys == sorted(keys), (
            f"Keys for fork '{bucket}' must be sorted: {keys}"
        )
        assert len(keys) == 3, (
            f"Fork '{bucket}' must contain exactly 3 keys (2 seeds + 1 agent "
            f"output), got {len(keys)}: {keys}"
        )
        # Must contain both seed files.
        for seed in SEED_KEYS:
            assert seed in keys, (
                f"Fork '{bucket}' must contain seed file '{seed}'. Got: {keys}"
            )
        # Must contain exactly one of the agent output keys.
        agent_in_fork = [k for k in keys if k in AGENT_KEYS]
        assert len(agent_in_fork) == 1, (
            f"Fork '{bucket}' must contain exactly one agent output file "
            f"from {sorted(AGENT_KEYS)}, got: {agent_in_fork}. Full keys: {keys}"
        )
        # Must not contain other forks' agent files.
        for other in AGENT_KEYS - {agent_in_fork[0]}:
            assert other not in keys, (
                f"Fork '{bucket}' must NOT contain another fork's output "
                f"'{other}'. Keys: {keys}"
            )
        buckets_seen.append(bucket)
        agent_keys_seen.append(agent_in_fork[0])

    assert len(set(buckets_seen)) == 3, (
        f"Fork bucket names in fork_results must be pairwise distinct, "
        f"got: {buckets_seen}"
    )
    assert set(agent_keys_seen) == AGENT_KEYS, (
        f"Across fork_results, the per-fork agent output keys must cover "
        f"exactly {sorted(AGENT_KEYS)}, got: {agent_keys_seen}"
    )


def test_source_bucket_unmodified(run_user_script):
    """Priority 1: Use the Tigris CLI to confirm the source bucket still
    holds only the two seed files and none of the agent outputs."""
    run_user_script  # ensure script ran
    source_bucket = bucket_name()
    cmd = _tigris_cmd() + ["objects", "list", source_bucket]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, (
        f"'tigris objects list {source_bucket}' failed: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    combined = result.stdout + "\n" + result.stderr

    for seed in SEED_KEYS:
        assert seed in combined, (
            f"Expected seed key '{seed}' to remain in '{source_bucket}'. "
            f"CLI output:\n{combined}"
        )
    for agent_key in AGENT_KEYS:
        assert agent_key not in combined, (
            f"Source bucket '{source_bucket}' must NOT contain fork output "
            f"'{agent_key}'. CLI output:\n{combined}"
        )


def test_fork_buckets_were_torn_down(run_user_script):
    """Priority 1: Use the Tigris CLI to confirm none of the three fork
    buckets recorded in audit.json still exist."""
    run_user_script  # ensure script ran
    with open(AUDIT_JSON) as f:
        data = json.load(f)
    fork_buckets = [entry["bucket"] for entry in data["fork_results"]]

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

    for fork_name in fork_buckets:
        assert fork_name not in listed_tokens, (
            f"Fork bucket '{fork_name}' still appears in 'tigris buckets "
            f"list' output — teardownForks did not delete it. Full "
            f"output:\n{combined}"
        )


def test_cleanup_source_bucket(run_user_script):
    """Verifier cleanup: delete the source bucket so the task
    leaves no residue. This runs at the end of the test session."""
    run_user_script  # ensure script ran first
    source_bucket = bucket_name()
    cmd = _tigris_cmd() + ["buckets", "delete", source_bucket, "--force"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        fallback = subprocess.run(
            _tigris_cmd() + ["buckets", "delete", source_bucket],
            capture_output=True,
            text=True,
            timeout=120,
            env=os.environ.copy(),
        )
        assert fallback.returncode == 0 or "not found" in (
            fallback.stderr.lower() + fallback.stdout.lower()
        ), (
            f"Failed to clean up source bucket '{source_bucket}'. "
            f"First attempt: stdout={result.stdout!r} stderr={result.stderr!r}. "
            f"Fallback attempt: stdout={fallback.stdout!r} "
            f"stderr={fallback.stderr!r}."
        )
