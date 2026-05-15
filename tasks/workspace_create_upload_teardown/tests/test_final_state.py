import json
import os
import subprocess

import pytest

PROJECT_DIR = "/home/user/tigris-task"
RUN_TS = os.path.join(PROJECT_DIR, "run.ts")
OUTPUT_LOG = os.path.join(PROJECT_DIR, "output.log")
TRIAL_ID_PATH = "/logs/artifacts/trial_id"


def _read_trial_id():
    with open(TRIAL_ID_PATH, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _workspace_name():
    name = f"harbor-ws-{_read_trial_id()}"
    import re
    name = re.sub(r"[^a-z0-9.-]", "-", name.lower())
    return name


def _expected_body():
    return '{"status":"ok","run":"' + _read_trial_id() + '"}'


VERIFY_SCRIPT = r"""
import { teardownWorkspace } from "@tigrisdata/agent-kit";
import { get, list, removeBucket } from "@tigrisdata/storage";

const bucket = process.argv[2];

async function main() {
  const result = { listing: null, object: null, cleanup: {}, errors: [] };

  // List the workspace bucket using ROOT credentials.
  const listRes = await list({ prefix: "", config: { bucket } });
  if (listRes.error) {
    result.errors.push({ where: "list", message: String(listRes.error.message || listRes.error) });
  } else {
    result.listing = (listRes.data?.items || []).map((item) => item.name);
  }

  // GET state.json using ROOT credentials.
  const getRes = await get("state.json", "string", { config: { bucket } });
  if (getRes.error) {
    result.object = { error: String(getRes.error.message || getRes.error) };
  } else {
    result.object = { body: getRes.data };
  }

  // ALWAYS attempt teardown: first via agent-kit's teardownWorkspace, then a defensive removeBucket.
  try {
    const tdRes = await teardownWorkspace({ bucket });
    result.cleanup.teardownWorkspace = tdRes.error
      ? { error: String(tdRes.error.message || tdRes.error) }
      : { ok: true };
  } catch (err) {
    result.cleanup.teardownWorkspace = { error: String(err && err.message ? err.message : err) };
  }

  try {
    const rmRes = await removeBucket(bucket, { force: true });
    result.cleanup.removeBucket = rmRes.error
      ? { error: String(rmRes.error.message || rmRes.error) }
      : { ok: true };
  } catch (err) {
    result.cleanup.removeBucket = { error: String(err && err.message ? err.message : err) };
  }

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
    """Run the Node verifier once and return the parsed JSON payload."""
    script_path = os.path.join(PROJECT_DIR, "_verify.mjs")
    with open(script_path, "w", encoding="utf-8") as handle:
        handle.write(VERIFY_SCRIPT)

    bucket = _workspace_name()
    env = os.environ.copy()

    result = subprocess.run(
        ["node", script_path, bucket],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
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


def test_run_ts_exists_and_uses_agent_kit_and_storage():
    assert os.path.isfile(RUN_TS), f"Expected {RUN_TS} to exist."
    with open(RUN_TS, "r", encoding="utf-8") as handle:
        content = handle.read()
    assert "@tigrisdata/agent-kit" in content, (
        "run.ts must import from '@tigrisdata/agent-kit'."
    )
    assert "createWorkspace" in content, (
        "run.ts must reference the 'createWorkspace' symbol."
    )
    assert "@tigrisdata/storage" in content, (
        "run.ts must import from '@tigrisdata/storage' to perform the upload."
    )
    assert "put" in content, (
        "run.ts must reference a 'put' call from @tigrisdata/storage."
    )


def test_output_log_contains_scoped_access_key():
    assert os.path.isfile(OUTPUT_LOG), f"Expected {OUTPUT_LOG} to exist."
    with open(OUTPUT_LOG, "r", encoding="utf-8") as handle:
        raw = handle.read().strip()
    assert raw, f"{OUTPUT_LOG} must contain the scoped access key id printed by run.ts."
    # The log may contain a single line; pick the line that looks like a Tigris access key.
    candidates = [
        line.strip()
        for line in raw.splitlines()
        if line.strip().startswith("tid_")
    ]
    assert candidates, (
        f"Expected {OUTPUT_LOG} to contain an access key id starting with 'tid_', got: {raw!r}"
    )
    scoped_key = candidates[-1]
    root_key = os.environ.get("TIGRIS_STORAGE_ACCESS_KEY_ID", "")
    assert root_key, (
        "TIGRIS_STORAGE_ACCESS_KEY_ID must be set in the verifier env for this check."
    )
    assert scoped_key != root_key, (
        "The access key id in output.log is identical to the root TIGRIS_STORAGE_ACCESS_KEY_ID — "
        "the agent appears to have used root credentials instead of the scoped credentials returned "
        "by createWorkspace."
    )


def test_state_json_listed_in_workspace_bucket(verify_payload):
    listing = verify_payload.get("listing")
    assert listing is not None, (
        f"Verifier failed to list the workspace bucket. Errors: {verify_payload.get('errors')}"
    )
    assert "state.json" in listing, (
        f"Expected 'state.json' in the workspace bucket listing, got: {listing}"
    )


def test_state_json_body_matches_expected(verify_payload):
    entry = verify_payload.get("object")
    assert entry is not None, "Verifier did not attempt to GET state.json."
    assert "error" not in entry, (
        f"Failed to GET state.json from the workspace bucket: {entry.get('error')}"
    )
    body = entry.get("body", "")
    expected = _expected_body()
    assert body == expected, (
        f"state.json body mismatch.\nExpected (exact): {expected!r}\nActual:           {body!r}"
    )
    try:
        parsed = json.loads(body)
    except ValueError as exc:
        pytest.fail(f"state.json did not contain valid JSON: {body!r} ({exc})")
    assert parsed == {"status": "ok", "run": _read_trial_id()}, (
        f"state.json JSON content mismatch: got {parsed}"
    )
