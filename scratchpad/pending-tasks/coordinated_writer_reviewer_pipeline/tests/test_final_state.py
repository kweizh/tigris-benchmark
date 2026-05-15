import json
import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/pipeline"
ORCHESTRATE_TS = os.path.join(PROJECT_DIR, "orchestrate.ts")
COORDINATION_JSON = os.path.join(PROJECT_DIR, "coordination.json")
OUTPUT_LOG = os.path.join(PROJECT_DIR, "output.log")

TARGET_BUCKET = "pipeline-out"
EXPECTED_WEBHOOK_URL = "https://hook.example.com/agents/reviewer"
EXPECTED_FILTER = 'WHERE `key` REGEXP "^drafts/"'
EXPECTED_UPLOAD_KEY = "drafts/article-1.md"


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


def test_webhook_secret_provided_to_verifier():
    """Sanity check: the verifier needs WEBHOOK_SECRET to assert it does
    not leak into coordination.json."""
    secret = os.environ.get("WEBHOOK_SECRET", "")
    assert secret, (
        "WEBHOOK_SECRET must be supplied to the verifier so it can assert "
        "the agent did not embed the raw token value in coordination.json."
    )


def test_orchestrate_ts_created():
    assert os.path.isfile(ORCHESTRATE_TS), (
        f"User must create the TypeScript orchestrator at {ORCHESTRATE_TS}."
    )


def test_orchestrate_ts_uses_required_apis():
    with open(ORCHESTRATE_TS) as f:
        contents = f.read()
    assert "@tigrisdata/agent-kit" in contents, (
        "orchestrate.ts must import from '@tigrisdata/agent-kit'."
    )
    assert "setupCoordination" in contents, (
        "orchestrate.ts must call setupCoordination from "
        "@tigrisdata/agent-kit."
    )
    assert "@aws-sdk/client-s3" in contents, (
        "orchestrate.ts must import from '@aws-sdk/client-s3'."
    )
    assert "PutObjectCommand" in contents, (
        "orchestrate.ts must use PutObjectCommand from @aws-sdk/client-s3 "
        "to upload drafts/article-1.md."
    )
    assert TARGET_BUCKET in contents, (
        f"orchestrate.ts must reference the target bucket '{TARGET_BUCKET}'."
    )
    assert EXPECTED_WEBHOOK_URL in contents, (
        f"orchestrate.ts must use the exact webhook URL "
        f"'{EXPECTED_WEBHOOK_URL}'."
    )
    assert "^drafts/" in contents, (
        "orchestrate.ts must include the regex prefix '^drafts/' inside its "
        "filter expression."
    )
    assert EXPECTED_UPLOAD_KEY in contents, (
        f"orchestrate.ts must upload key '{EXPECTED_UPLOAD_KEY}'."
    )
    assert "process.env.WEBHOOK_SECRET" in contents, (
        "orchestrate.ts must read the bearer token from "
        "process.env.WEBHOOK_SECRET — it MUST NOT hard-code the secret."
    )


@pytest.fixture(scope="module")
def run_user_script():
    """Priority 1: Execute the user's orchestrator end-to-end against real
    Tigris."""
    # Clean any previous output so the run is fresh.
    for path in (COORDINATION_JSON, OUTPUT_LOG):
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    with open(OUTPUT_LOG, "w") as logf:
        result = subprocess.run(
            ["npx", "tsx", "orchestrate.ts"],
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
        f"'npx tsx orchestrate.ts' exited with {result.returncode}. "
        f"Output:\n{log_contents}"
    )


def test_coordination_json_shape_and_contents(run_user_script):
    run_user_script  # ensure script ran
    assert os.path.isfile(COORDINATION_JSON), (
        f"Expected coordination summary at {COORDINATION_JSON} after "
        f"running orchestrate.ts."
    )
    with open(COORDINATION_JSON) as f:
        raw = f.read()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"{COORDINATION_JSON} is not valid JSON: {exc}. "
            f"Contents:\n{raw}"
        )

    assert isinstance(data, dict), (
        f"{COORDINATION_JSON} must be a JSON object, got "
        f"{type(data).__name__}."
    )

    assert data.get("bucket") == TARGET_BUCKET, (
        f"'bucket' in {COORDINATION_JSON} must equal '{TARGET_BUCKET}', "
        f"got {data.get('bucket')!r}."
    )
    assert data.get("webhookUrl") == EXPECTED_WEBHOOK_URL, (
        f"'webhookUrl' in {COORDINATION_JSON} must equal "
        f"'{EXPECTED_WEBHOOK_URL}', got {data.get('webhookUrl')!r}."
    )
    assert data.get("filter") == EXPECTED_FILTER, (
        f"'filter' in {COORDINATION_JSON} must equal exactly "
        f"{EXPECTED_FILTER!r}, got {data.get('filter')!r}."
    )
    assert data.get("authTokenConfigured") is True, (
        f"'authTokenConfigured' in {COORDINATION_JSON} must be the boolean "
        f"true, got {data.get('authTokenConfigured')!r}."
    )
    assert data.get("uploadedKey") == EXPECTED_UPLOAD_KEY, (
        f"'uploadedKey' in {COORDINATION_JSON} must equal "
        f"'{EXPECTED_UPLOAD_KEY}', got {data.get('uploadedKey')!r}."
    )


def test_coordination_json_does_not_leak_secret(run_user_script):
    """The raw WEBHOOK_SECRET value must never appear in coordination.json."""
    run_user_script  # ensure script ran
    secret = os.environ.get("WEBHOOK_SECRET", "")
    assert secret, (
        "WEBHOOK_SECRET must be set in the verifier environment for this "
        "check."
    )
    with open(COORDINATION_JSON) as f:
        raw = f.read()
    assert secret not in raw, (
        f"{COORDINATION_JSON} must not contain the raw WEBHOOK_SECRET "
        f"value. The orchestrator should record only that an auth token "
        f"was configured (authTokenConfigured: true), not the token itself."
    )


def test_upload_visible_via_tigris_cli(run_user_script):
    """Priority 1: Use the Tigris CLI to confirm the draft was uploaded."""
    run_user_script  # ensure script ran
    cmd = _tigris_cmd() + ["objects", "list", TARGET_BUCKET]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, (
        f"'tigris objects list {TARGET_BUCKET}' failed: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    combined = result.stdout + "\n" + result.stderr
    assert EXPECTED_UPLOAD_KEY in combined, (
        f"Expected uploaded key '{EXPECTED_UPLOAD_KEY}' to be listed in "
        f"'tigris objects list {TARGET_BUCKET}' output:\n{combined}"
    )


def test_bucket_still_exists_after_coordination(run_user_script):
    """Priority 1: Use the Tigris CLI to confirm the bucket is still
    inspectable after coordination was configured. The orchestrator MUST
    NOT have torn down the bucket or notification config."""
    run_user_script  # ensure script ran
    cmd = _tigris_cmd() + ["buckets", "get", TARGET_BUCKET]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, (
        f"'tigris buckets get {TARGET_BUCKET}' failed: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    combined = result.stdout + "\n" + result.stderr
    assert TARGET_BUCKET in combined, (
        f"'tigris buckets get {TARGET_BUCKET}' output must reference the "
        f"bucket name '{TARGET_BUCKET}'. Output:\n{combined}"
    )


def test_cleanup_target_bucket(run_user_script):
    """Verifier cleanup: delete the `pipeline-out` bucket so the task
    leaves no residue."""
    run_user_script  # ensure script ran first
    cmd = _tigris_cmd() + ["buckets", "delete", TARGET_BUCKET, "--force"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        fallback = subprocess.run(
            _tigris_cmd() + ["buckets", "delete", TARGET_BUCKET],
            capture_output=True,
            text=True,
            timeout=120,
            env=os.environ.copy(),
        )
        assert fallback.returncode == 0 or "not found" in (
            fallback.stderr.lower() + fallback.stdout.lower()
        ), (
            f"Failed to clean up target bucket '{TARGET_BUCKET}'. "
            f"First attempt: stdout={result.stdout!r} stderr={result.stderr!r}. "
            f"Fallback attempt: stdout={fallback.stdout!r} "
            f"stderr={fallback.stderr!r}."
        )
