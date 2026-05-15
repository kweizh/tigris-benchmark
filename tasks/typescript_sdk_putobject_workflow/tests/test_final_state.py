import json
import os
import subprocess
import tempfile

import pytest

PROJECT_DIR = "/home/user/tigris-task"
INDEX_TS = os.path.join(PROJECT_DIR, "index.ts")
LISTING_TXT = os.path.join(PROJECT_DIR, "listing.txt")
TRIAL_ID_PATH = "/logs/artifacts/trial_id"

EXPECTED_KEYS = [
    "inbox/msg-1.json",
    "inbox/msg-2.json",
    "inbox/msg-3.json",
]
EXPECTED_BODIES = {
    "inbox/msg-1.json": {"id": 1},
    "inbox/msg-2.json": {"id": 2},
    "inbox/msg-3.json": {"id": 3},
}


def _read_trial_id():
    with open(TRIAL_ID_PATH, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _bucket_name():
    import re
    name = f"harbor-tssdk-{_read_trial_id()}"
    name = re.sub(r"[^a-z0-9.-]", "-", name.lower())
    return name


VERIFY_SCRIPT = r"""
import { createBucket, get, list, remove, removeBucket } from "@tigrisdata/storage";

const bucket = process.argv[2];

async function main() {
  const result = { listing: null, objects: {}, cleanup: {}, errors: [] };

  const listRes = await list({ prefix: "inbox/", config: { bucket } });
  if (listRes.error) {
    result.errors.push({ where: "list", message: String(listRes.error.message || listRes.error) });
  } else {
    result.listing = (listRes.data.items || []).map((item) => item.name);
  }

  for (const key of ["inbox/msg-1.json", "inbox/msg-2.json", "inbox/msg-3.json"]) {
    const getRes = await get(key, "string", { config: { bucket } });
    if (getRes.error) {
      result.objects[key] = { error: String(getRes.error.message || getRes.error) };
    } else {
      result.objects[key] = { body: getRes.data };
    }
  }

  // Cleanup
  for (const key of ["inbox/msg-1.json", "inbox/msg-2.json", "inbox/msg-3.json"]) {
    const rmRes = await remove(key, { config: { bucket } });
    result.cleanup[key] = rmRes.error
      ? { error: String(rmRes.error.message || rmRes.error) }
      : { ok: true };
  }
  const rmBucket = await removeBucket(bucket, { force: true });
  result.cleanup["__bucket__"] = rmBucket.error
    ? { error: String(rmBucket.error.message || rmBucket.error) }
    : { ok: true };

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

    bucket = _bucket_name()
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
    assert "fatal" not in payload, f"Verifier reported fatal error: {payload.get('fatal')}"
    return payload


def test_index_ts_exists_and_uses_sdk():
    assert os.path.isfile(INDEX_TS), f"Expected {INDEX_TS} to exist."
    with open(INDEX_TS, "r", encoding="utf-8") as handle:
        content = handle.read()
    assert "@tigrisdata/storage" in content, (
        "index.ts must import from '@tigrisdata/storage'."
    )
    for symbol in ("createBucket", "put", "list"):
        assert symbol in content, (
            f"index.ts must reference the SDK symbol '{symbol}'."
        )


def test_listing_txt_contains_all_keys():
    assert os.path.isfile(LISTING_TXT), f"Expected {LISTING_TXT} to exist."
    with open(LISTING_TXT, "r", encoding="utf-8") as handle:
        listed = [line.strip() for line in handle.read().splitlines() if line.strip()]
    for key in EXPECTED_KEYS:
        assert key in listed, (
            f"Expected key {key!r} to appear in {LISTING_TXT}, got: {listed}"
        )


def test_bucket_listing_contains_expected_keys(verify_payload):
    listing = verify_payload.get("listing")
    assert listing is not None, (
        f"Verifier failed to list the bucket. Errors: {verify_payload.get('errors')}"
    )
    for key in EXPECTED_KEYS:
        assert key in listing, (
            f"Expected key {key!r} in remote bucket listing, got: {listing}"
        )


def test_object_contents_match_expected(verify_payload):
    objects = verify_payload.get("objects", {})
    for key, expected_body in EXPECTED_BODIES.items():
        entry = objects.get(key)
        assert entry is not None, f"Verifier did not fetch object {key}."
        assert "error" not in entry, (
            f"Failed to GET {key}: {entry.get('error')}"
        )
        body = entry.get("body", "")
        try:
            parsed = json.loads(body)
        except ValueError as exc:
            pytest.fail(f"Object {key} did not contain valid JSON: {body!r} ({exc})")
        assert parsed == expected_body, (
            f"Object {key} content mismatch: expected {expected_body}, got {parsed}"
        )
