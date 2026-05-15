import json
import os
import subprocess

import pytest

PROJECT_DIR = "/home/user/tigris-task"
RUN_TS = os.path.join(PROJECT_DIR, "run.ts")
TRIAL_ID_PATH = "/logs/artifacts/trial_id"

EXPECTED_FORK_KEYS = sorted(["data/v1.txt", "data/v2.txt"])
EXPECTED_FORK_BODIES = {
    "data/v1.txt": "version1",
    "data/v2.txt": "version2",
}
EXPECTED_BASE_KEYS = sorted(["data/v1.txt", "data/v2.txt", "data/v3.txt"])
EXPECTED_V3_BODY = "version3"


def _read_trial_id():
    with open(TRIAL_ID_PATH, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _bucket_names():
    trial = _read_trial_id()
    return f"harbor-base-{trial}", f"harbor-restore-{trial}"


VERIFY_SCRIPT = r"""
import {
  get,
  list,
  removeBucket,
} from "@tigrisdata/storage";

const baseBucket = process.argv[2];
const forkBucket = process.argv[3];

async function safeList(bucket) {
  const res = await list({ prefix: "data/", config: { bucket } });
  if (res.error) {
    return { error: String(res.error.message || res.error) };
  }
  return { names: (res.data.items || []).map((i) => i.name).sort() };
}

async function safeGet(bucket, key) {
  const res = await get(key, "string", { config: { bucket } });
  if (res.error) {
    return { error: String(res.error.message || res.error) };
  }
  return { body: res.data };
}

async function main() {
  const out = {
    base: { listing: null, objects: {} },
    fork: { listing: null, objects: {} },
    cleanup: {},
    errors: [],
  };

  // List & fetch fork bucket
  const forkList = await safeList(forkBucket);
  if (forkList.error) {
    out.errors.push({ where: "list-fork", message: forkList.error });
  } else {
    out.fork.listing = forkList.names;
    for (const key of ["data/v1.txt", "data/v2.txt", "data/v3.txt"]) {
      out.fork.objects[key] = await safeGet(forkBucket, key);
    }
  }

  // List & fetch base bucket
  const baseList = await safeList(baseBucket);
  if (baseList.error) {
    out.errors.push({ where: "list-base", message: baseList.error });
  } else {
    out.base.listing = baseList.names;
    for (const key of ["data/v1.txt", "data/v2.txt", "data/v3.txt"]) {
      out.base.objects[key] = await safeGet(baseBucket, key);
    }
  }

  process.stdout.write(JSON.stringify(out));
}

main().catch((err) => {
  process.stdout.write(
    JSON.stringify({ fatal: String(err && err.message ? err.message : err) }),
  );
  process.exit(2);
});
"""


CLEANUP_SCRIPT = r"""
import { removeBucket } from "@tigrisdata/storage";

const baseBucket = process.argv[2];
const forkBucket = process.argv[3];

async function dropBucket(bucket) {
  const res = await removeBucket(bucket, { force: true });
  if (res.error) {
    return { bucket, error: String(res.error.message || res.error) };
  }
  return { bucket, ok: true };
}

async function main() {
  const results = [];
  for (const b of [forkBucket, baseBucket]) {
    results.push(await dropBucket(b));
  }
  process.stdout.write(JSON.stringify(results));
}

main().catch((err) => {
  process.stdout.write(
    JSON.stringify({ fatal: String(err && err.message ? err.message : err) }),
  );
});
"""


@pytest.fixture(scope="module")
def verify_payload():
    """Run the Node verifier once and return parsed JSON payload."""
    script_path = os.path.join(PROJECT_DIR, "_verify.mjs")
    with open(script_path, "w", encoding="utf-8") as handle:
        handle.write(VERIFY_SCRIPT)

    base_bucket, fork_bucket = _bucket_names()

    try:
        result = subprocess.run(
            ["node", script_path, base_bucket, fork_bucket],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            timeout=180,
        )
    finally:
        try:
            os.remove(script_path)
        except OSError:
            pass

    assert result.returncode == 0, (
        f"Verifier Node script failed (code={result.returncode}).\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    last_line = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    try:
        payload = json.loads(last_line)
    except (ValueError, IndexError) as exc:
        pytest.fail(
            f"Could not parse verifier output as JSON: {exc}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    assert "fatal" not in payload, (
        f"Verifier reported fatal error: {payload.get('fatal')}"
    )
    return payload


@pytest.fixture(scope="module", autouse=True)
def cleanup_buckets_after_tests():
    """Force-delete both buckets after assertions, regardless of pass/fail."""
    yield
    try:
        base_bucket, fork_bucket = _bucket_names()
    except (FileNotFoundError, AssertionError):
        return
    script_path = os.path.join(PROJECT_DIR, "_cleanup.mjs")
    try:
        with open(script_path, "w", encoding="utf-8") as handle:
            handle.write(CLEANUP_SCRIPT)
        subprocess.run(
            ["node", script_path, base_bucket, fork_bucket],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            timeout=180,
        )
    except Exception:
        pass
    finally:
        try:
            os.remove(script_path)
        except OSError:
            pass


def test_run_ts_exists_and_uses_required_symbols():
    assert os.path.isfile(RUN_TS), f"Expected {RUN_TS} to exist."
    with open(RUN_TS, "r", encoding="utf-8") as handle:
        content = handle.read()
    assert "@tigrisdata/agent-kit" in content, (
        "run.ts must import from '@tigrisdata/agent-kit'."
    )
    assert "@tigrisdata/storage" in content, (
        "run.ts must import from '@tigrisdata/storage'."
    )
    for symbol in ("checkpoint", "restore", "put"):
        assert symbol in content, (
            f"run.ts must reference the SDK symbol '{symbol}'."
        )


def test_fork_bucket_contains_exactly_two_seeded_objects(verify_payload):
    fork = verify_payload.get("fork", {})
    listing = fork.get("listing")
    assert listing is not None, (
        f"Verifier could not list fork bucket. Errors: {verify_payload.get('errors')}"
    )
    assert listing == EXPECTED_FORK_KEYS, (
        f"Fork bucket must contain EXACTLY {EXPECTED_FORK_KEYS} (the two "
        f"pre-checkpoint objects). Got: {listing}. If 'data/v3.txt' is in this "
        "list, the agent took the checkpoint AFTER uploading v3.txt; the "
        "checkpoint must be taken FIRST, before the v3 upload."
    )


def test_fork_bucket_does_not_contain_v3(verify_payload):
    fork = verify_payload.get("fork", {})
    listing = fork.get("listing") or []
    assert "data/v3.txt" not in listing, (
        "Fork bucket must NOT contain 'data/v3.txt': the checkpoint was supposed "
        f"to be taken before that upload, but the fork listing was: {listing}"
    )
    v3_entry = fork.get("objects", {}).get("data/v3.txt", {})
    # Trying to GET v3 from the fork should fail (NoSuchKey or similar).
    assert "error" in v3_entry, (
        "Fork bucket appears to contain 'data/v3.txt' (the GET succeeded). "
        f"The fork must reflect the pre-v3 state. Got: {v3_entry}"
    )


def test_fork_bucket_object_contents_match_pre_checkpoint(verify_payload):
    fork_objects = verify_payload.get("fork", {}).get("objects", {})
    for key, expected_body in EXPECTED_FORK_BODIES.items():
        entry = fork_objects.get(key)
        assert entry is not None, f"Verifier did not fetch {key} from fork bucket."
        assert "error" not in entry, (
            f"Failed to GET {key} from fork bucket: {entry.get('error')}"
        )
        body = entry.get("body", "")
        assert body == expected_body, (
            f"Fork bucket object {key} content mismatch: expected "
            f"{expected_body!r}, got {body!r}"
        )


def test_base_bucket_still_contains_all_three_objects(verify_payload):
    base = verify_payload.get("base", {})
    listing = base.get("listing")
    assert listing is not None, (
        f"Verifier could not list base bucket. Errors: {verify_payload.get('errors')}"
    )
    for key in EXPECTED_BASE_KEYS:
        assert key in listing, (
            f"Base bucket must still contain {key!r} (v3.txt was uploaded after "
            f"the checkpoint and must remain). Got listing: {listing}"
        )


def test_base_bucket_v3_object_has_expected_content(verify_payload):
    base_objects = verify_payload.get("base", {}).get("objects", {})
    entry = base_objects.get("data/v3.txt")
    assert entry is not None, "Verifier did not fetch data/v3.txt from base bucket."
    assert "error" not in entry, (
        f"Failed to GET data/v3.txt from base bucket: {entry.get('error')}. "
        "The agent must have uploaded v3.txt to the base bucket after the "
        "checkpoint."
    )
    body = entry.get("body", "")
    assert body == EXPECTED_V3_BODY, (
        f"Expected base bucket data/v3.txt content to be {EXPECTED_V3_BODY!r}, "
        f"got {body!r}"
    )
