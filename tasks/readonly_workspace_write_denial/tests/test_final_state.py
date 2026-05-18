import json
import os
import re
import subprocess

import pytest

PROJECT_DIR = "/home/user/tigris-task"
RUN_TS = os.path.join(PROJECT_DIR, "run.ts")
WRITE_DENIAL_LOG = os.path.join(PROJECT_DIR, "write-denial.log")
READBACK_TXT = os.path.join(PROJECT_DIR, "readback.txt")
TRIAL_ID_PATH = "/logs/artifacts/trial_id"

EXPECTED_BODY = "hello readonly"
DENIAL_REGEX = re.compile(
    r"(access[\s_-]?denied|forbidden|not allowed|permission|\b403\b)",
    re.IGNORECASE,
)


def _read_trial_id():
    with open(TRIAL_ID_PATH, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _workspace_bucket():
    name = f"harbor-ro-{_read_trial_id()}"
    import re
    name = re.sub(r"[^a-z0-9.-]", "-", name.lower())
    return name


def _fork_bucket():
    name = f"harbor-ro-{_read_trial_id()}-readonly-0"
    import re
    name = re.sub(r"[^a-z0-9.-]", "-", name.lower())
    return name


VERIFY_SCRIPT = r"""
import { get, head, removeBucket } from "@tigrisdata/storage";

const workspaceBucket = process.argv[2];
const forkBucket = process.argv[3];

async function safeGet(bucket, key) {
  const res = await get(key, "string", { config: { bucket } });
  if (res.error) {
    return { error: String(res.error.message || res.error), code: res.error.name || res.error.Code || res.error.code || null };
  }
  return { body: res.data };
}

async function safeHead(bucket, key) {
  if (typeof head !== "function") {
    // Fall back to get if head is not exported by this version
    const res = await get(key, "string", { config: { bucket } });
    if (res.error) {
      return {
        error: String(res.error.message || res.error),
        code: res.error.name || res.error.Code || res.error.code || null,
        status: res.error.$metadata?.httpStatusCode ?? null,
      };
    }
    if (res.data === undefined) {
      return {
        error: "NotFound",
        code: "NotFound",
        status: 404,
      };
    }
    return { exists: true };
  }
  const res = await head(key, { config: { bucket } });
  if (res.error) {
    return {
      error: String(res.error.message || res.error),
      code: res.error.name || res.error.Code || res.error.code || null,
      status: res.error.$metadata?.httpStatusCode ?? null,
    };
  }
  if (res.data === undefined) {
    return {
      error: "NotFound",
      code: "NotFound",
      status: 404,
    };
  }
  return { exists: true };
}

async function safeRemoveBucket(bucket) {
  const res = await removeBucket(bucket, { force: true });
  if (res.error) {
    return { error: String(res.error.message || res.error) };
  }
  return { ok: true };
}

async function main() {
  const result = {
    workspace_welcome: await safeGet(workspaceBucket, "notes/welcome.txt"),
    fork_forbidden: await safeHead(forkBucket, "notes/forbidden.txt"),
    cleanup: {},
  };
  // Best-effort teardown (fork first, then workspace). Failures are reported
  // but do not throw.
  result.cleanup[forkBucket] = await safeRemoveBucket(forkBucket);
  result.cleanup[workspaceBucket] = await safeRemoveBucket(workspaceBucket);

  process.stdout.write(JSON.stringify(result));
}

main().catch((err) => {
  process.stdout.write(
    JSON.stringify({ fatal: String(err && err.message ? err.message : err) }),
  );
  process.exit(2);
});
"""


@pytest.fixture(scope="module")
def verify_payload():
    """Run the Node verifier once and return parsed JSON payload."""
    script_path = os.path.join(PROJECT_DIR, "_verify.mjs")
    with open(script_path, "w", encoding="utf-8") as handle:
        handle.write(VERIFY_SCRIPT)

    env = os.environ.copy()
    result = subprocess.run(
        ["node", script_path, _workspace_bucket(), _fork_bucket()],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        env=env,
        timeout=240,
    )

    try:
        os.remove(script_path)
    except OSError:
        pass

    assert result.returncode == 0, (
        f"Verifier Node script failed (code={result.returncode}).\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        pytest.fail(
            f"Could not parse verifier output as JSON: {exc}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    assert "fatal" not in payload, (
        f"Verifier reported fatal error: {payload.get('fatal')}"
    )
    return payload


def test_run_ts_exists_and_uses_required_sdks():
    assert os.path.isfile(RUN_TS), f"Expected {RUN_TS} to exist."
    with open(RUN_TS, "r", encoding="utf-8") as handle:
        content = handle.read()
    assert "@tigrisdata/agent-kit" in content, (
        "run.ts must import from '@tigrisdata/agent-kit'."
    )
    assert "@tigrisdata/storage" in content, (
        "run.ts must import from '@tigrisdata/storage'."
    )
    for symbol in ("createWorkspace", "createForks"):
        assert symbol in content, (
            f"run.ts must reference the Agent Kit symbol '{symbol}'."
        )


def test_write_denial_log_contains_access_keyword():
    assert os.path.isfile(WRITE_DENIAL_LOG), (
        f"Expected {WRITE_DENIAL_LOG} to exist after the agent attempts the forbidden write."
    )
    with open(WRITE_DENIAL_LOG, "r", encoding="utf-8") as handle:
        content = handle.read()
    assert content.strip(), (
        f"{WRITE_DENIAL_LOG} must be non-empty; it must contain the captured access-denial error."
    )
    assert DENIAL_REGEX.search(content), (
        f"{WRITE_DENIAL_LOG} must contain an access-denial keyword "
        f"(AccessDenied/Forbidden/not allowed/permission/403). Got: {content!r}"
    )


def test_readback_txt_matches_expected_body():
    assert os.path.isfile(READBACK_TXT), f"Expected {READBACK_TXT} to exist."
    with open(READBACK_TXT, "r", encoding="utf-8") as handle:
        content = handle.read()
    assert content == EXPECTED_BODY, (
        f"Expected {READBACK_TXT} to contain exactly {EXPECTED_BODY!r}, got: {content!r}"
    )


def test_workspace_welcome_object_present_with_expected_body(verify_payload):
    entry = verify_payload.get("workspace_welcome", {})
    assert "error" not in entry, (
        f"Failed to GET notes/welcome.txt from the editor workspace bucket "
        f"{_workspace_bucket()}: {entry.get('error')}"
    )
    body = entry.get("body")
    assert body == EXPECTED_BODY, (
        f"Expected notes/welcome.txt body in {_workspace_bucket()} to be {EXPECTED_BODY!r}, "
        f"got: {body!r}"
    )


def test_fork_forbidden_object_does_not_exist(verify_payload):
    entry = verify_payload.get("fork_forbidden", {})
    # The verifier expects an error (object missing). If it reports `exists: true`,
    # the forbidden write actually succeeded — that's a verification failure.
    assert entry.get("exists") is not True, (
        f"notes/forbidden.txt unexpectedly exists in fork bucket {_fork_bucket()}; "
        f"the readonly credentials must have been able to write."
    )
    assert "error" in entry, (
        f"Verifier did not record either presence or absence for notes/forbidden.txt "
        f"in fork bucket {_fork_bucket()}: {entry!r}"
    )
