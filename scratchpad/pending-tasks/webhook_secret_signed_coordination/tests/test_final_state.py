import json
import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/signed-coord"
INDEX_TS = os.path.join(PROJECT_DIR, "index.ts")
RESULT_JSON = os.path.join(PROJECT_DIR, "result.json")
OUTPUT_LOG = os.path.join(PROJECT_DIR, "output.log")
EXPECTED_TOKEN_FILE = os.path.join(PROJECT_DIR, "expected_token.txt")
BUCKET_NAME = "analytics-out"
EXPECTED_WEBHOOK_URL = "https://hooks.example.com/ingest"
EXPECTED_FILTER = 'WHERE `key` REGEXP "^reports/"'


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


def test_expected_token_file_present_for_verifier():
    """Sanity-check the setup.sh-created handoff file. The verifier needs
    it to compare against its own WEBHOOK_SECRET env var below."""
    assert os.path.isfile(EXPECTED_TOKEN_FILE), (
        f"{EXPECTED_TOKEN_FILE} must exist; setup.sh should have written it "
        f"at container start."
    )
    with open(EXPECTED_TOKEN_FILE) as f:
        contents = f.read().strip()
    assert contents, (
        f"{EXPECTED_TOKEN_FILE} must contain a non-empty secret value."
    )
    env_secret = os.environ.get("WEBHOOK_SECRET", "")
    assert env_secret, (
        "The verifier's own WEBHOOK_SECRET env var is unset; the verifier "
        "needs it to assert the agent forwarded the env-injected secret."
    )
    assert contents == env_secret, (
        "The trimmed contents of expected_token.txt must equal the "
        "verifier's WEBHOOK_SECRET env var (both originate from the same "
        "orchestrator-injected value)."
    )


def test_index_ts_exists():
    assert os.path.isfile(INDEX_TS), (
        f"User must create the TypeScript script at {INDEX_TS}."
    )


def test_index_ts_uses_required_apis():
    with open(INDEX_TS) as f:
        contents = f.read()
    assert "@tigrisdata/agent-kit" in contents, (
        "index.ts must import from '@tigrisdata/agent-kit'."
    )
    assert "setupCoordination" in contents, (
        "index.ts must call setupCoordination from @tigrisdata/agent-kit."
    )
    assert BUCKET_NAME in contents, (
        f"index.ts must reference the bucket '{BUCKET_NAME}'."
    )
    assert EXPECTED_WEBHOOK_URL in contents, (
        f"index.ts must reference the webhook URL '{EXPECTED_WEBHOOK_URL}'."
    )
    assert EXPECTED_FILTER in contents, (
        f"index.ts must contain the exact filter string {EXPECTED_FILTER!r}."
    )
    assert "process.env.WEBHOOK_SECRET" in contents, (
        "index.ts must read the bearer token from "
        "'process.env.WEBHOOK_SECRET' rather than hard-coding it."
    )


def test_index_ts_does_not_hardcode_the_secret():
    """The verifier reads its own WEBHOOK_SECRET env var and asserts that
    the exact string does not appear anywhere in index.ts."""
    env_secret = os.environ.get("WEBHOOK_SECRET", "")
    assert env_secret, (
        "The verifier needs its own WEBHOOK_SECRET env var to perform "
        "the hard-coded-secret check."
    )
    with open(INDEX_TS) as f:
        contents = f.read()
    assert env_secret not in contents, (
        f"index.ts must NOT hard-code the literal WEBHOOK_SECRET value. "
        f"The script must read it from process.env.WEBHOOK_SECRET at "
        f"runtime."
    )


@pytest.fixture(scope="module")
def run_user_script():
    """Priority 1: Execute the user's script end-to-end against real Tigris."""
    # Clean any previous result/log so the run is fresh.
    for path in (RESULT_JSON, OUTPUT_LOG):
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


def test_result_json_shape_and_contents(run_user_script):
    run_user_script  # ensure script ran first
    assert os.path.isfile(RESULT_JSON), (
        f"Expected result file at {RESULT_JSON} after running index.ts."
    )
    with open(RESULT_JSON) as f:
        data = json.load(f)

    assert isinstance(data, dict), (
        f"{RESULT_JSON} must be a JSON object, got {type(data).__name__}."
    )

    assert "ok" in data, f"{RESULT_JSON} must contain an 'ok' field."
    assert data["ok"] is True, (
        f"'ok' in {RESULT_JSON} must be the boolean true, got {data['ok']!r}."
    )

    assert "bucket" in data, f"{RESULT_JSON} must contain a 'bucket' field."
    assert data["bucket"] == BUCKET_NAME, (
        f"'bucket' in {RESULT_JSON} must equal {BUCKET_NAME!r}, got "
        f"{data['bucket']!r}."
    )

    assert "filter" in data, f"{RESULT_JSON} must contain a 'filter' field."
    assert data["filter"] == EXPECTED_FILTER, (
        f"'filter' in {RESULT_JSON} must equal {EXPECTED_FILTER!r}, got "
        f"{data['filter']!r}."
    )


def test_tigris_cli_confirms_bucket_exists(run_user_script):
    """Priority 1: Use the Tigris CLI to confirm the target bucket exists
    in the Tigris account under the admin credentials."""
    run_user_script  # ensure script ran first
    cmd = _tigris_cmd() + ["buckets", "get", BUCKET_NAME]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, (
        f"'tigris buckets get {BUCKET_NAME}' failed: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    combined = result.stdout + "\n" + result.stderr
    assert BUCKET_NAME in combined, (
        f"Expected bucket '{BUCKET_NAME}' in 'tigris buckets get' output. "
        f"Full output:\n{combined}"
    )


def test_tigris_cli_confirms_webhook_config_exists(run_user_script):
    """Priority 1: Use `tigris buckets set-notifications --disable` to
    confirm a notification config has been wired to the bucket. The
    `--disable` flag preserves the existing webhook/filter/auth config
    while flipping its enabled bit; it requires an existing config and
    therefore acts as a positive existence check for what the agent
    configured via `setupCoordination`."""
    run_user_script  # ensure script ran first
    cmd = _tigris_cmd() + [
        "buckets",
        "set-notifications",
        BUCKET_NAME,
        "--disable",
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, (
        f"'tigris buckets set-notifications {BUCKET_NAME} --disable' failed: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}. This typically "
        f"means no webhook notification config exists on the bucket — i.e. "
        f"the agent's setupCoordination call did not actually wire up the "
        f"webhook."
    )


def test_cleanup_analytics_out_bucket(run_user_script):
    """Verifier cleanup: delete the `analytics-out` bucket so the task
    leaves no residue in the Tigris account. This runs after all
    assertions complete."""
    run_user_script  # ensure script ran first
    # First reset any remaining notification config so the bucket-delete
    # call below is unblocked by lingering webhook state.
    subprocess.run(
        _tigris_cmd()
        + ["buckets", "set-notifications", BUCKET_NAME, "--reset"],
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )
    cmd = _tigris_cmd() + ["buckets", "delete", BUCKET_NAME, "--force"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        fallback = subprocess.run(
            _tigris_cmd() + ["buckets", "delete", BUCKET_NAME],
            capture_output=True,
            text=True,
            timeout=120,
            env=os.environ.copy(),
        )
        assert fallback.returncode == 0 or "not found" in (
            fallback.stderr.lower() + fallback.stdout.lower()
        ), (
            f"Failed to clean up bucket '{BUCKET_NAME}'. "
            f"First attempt: stdout={result.stdout!r} stderr={result.stderr!r}. "
            f"Fallback attempt: stdout={fallback.stdout!r} "
            f"stderr={fallback.stderr!r}."
        )
