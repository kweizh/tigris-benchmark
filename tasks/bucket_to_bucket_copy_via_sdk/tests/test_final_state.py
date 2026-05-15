import json
import os
import subprocess

import pytest

PROJECT_DIR = "/home/user/tigris-task"
COPY_TS = os.path.join(PROJECT_DIR, "copy.ts")
TRIAL_ID_PATH = "/logs/artifacts/trial_id"

EXPECTED_KEYS = [
    "data/01.json",
    "data/02.json",
    "data/03.json",
    "data/04.json",
    "data/05.json",
]


def _expected_body(n: int) -> str:
    return '{"index": %d, "payload": "%s"}' % (n, "foo" * n)


EXPECTED_BODIES = {
    "data/0%d.json" % n: _expected_body(n) for n in range(1, 6)
}


def _read_trial_id():
    with open(TRIAL_ID_PATH, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _src_bucket():
    return "harbor-src-%s" % _read_trial_id()


def _dst_bucket():
    return "harbor-dst-%s" % _read_trial_id()


VERIFY_SCRIPT = r"""
import { list, get, remove, removeBucket } from "@tigrisdata/storage";

const srcBucket = process.argv[2];
const dstBucket = process.argv[3];

async function listAll(bucket) {
  const items = [];
  let paginationToken = undefined;
  while (true) {
    const res = await list({
      prefix: "data/",
      paginationToken,
      config: { bucket },
    });
    if (res.error) {
      return { error: String(res.error.message || res.error) };
    }
    for (const item of res.data?.items || []) {
      items.push(item.name);
    }
    if (res.data?.hasMore && res.data?.paginationToken) {
      paginationToken = res.data.paginationToken;
    } else {
      break;
    }
  }
  return { items };
}

async function fetchBodies(bucket, keys) {
  const out = {};
  for (const key of keys) {
    const res = await get(key, "string", { config: { bucket } });
    if (res.error) {
      out[key] = { error: String(res.error.message || res.error) };
    } else {
      out[key] = { body: typeof res.data === "string" ? res.data : String(res.data) };
    }
  }
  return out;
}

async function tryRemove(bucket, keys) {
  const results = {};
  for (const key of keys) {
    try {
      const r = await remove(key, { config: { bucket } });
      results[key] = r.error ? { error: String(r.error.message || r.error) } : { ok: true };
    } catch (err) {
      results[key] = { error: String(err && err.message ? err.message : err) };
    }
  }
  return results;
}

async function tryRemoveBucket(bucket) {
  try {
    const r = await removeBucket(bucket, { force: true });
    return r.error ? { error: String(r.error.message || r.error) } : { ok: true };
  } catch (err) {
    return { error: String(err && err.message ? err.message : err) };
  }
}

async function main() {
  const result = {
    dst: { listing: null, listError: null, bodies: {} },
    src: { listing: null, listError: null, bodies: {} },
    cleanup: { srcObjects: {}, dstObjects: {}, srcBucket: null, dstBucket: null },
  };

  const expectedKeys = [
    "data/01.json",
    "data/02.json",
    "data/03.json",
    "data/04.json",
    "data/05.json",
  ];

  const dstList = await listAll(dstBucket);
  if (dstList.error) {
    result.dst.listError = dstList.error;
  } else {
    result.dst.listing = dstList.items;
  }
  result.dst.bodies = await fetchBodies(dstBucket, expectedKeys);

  const srcList = await listAll(srcBucket);
  if (srcList.error) {
    result.src.listError = srcList.error;
  } else {
    result.src.listing = srcList.items;
  }
  result.src.bodies = await fetchBodies(srcBucket, expectedKeys);

  // Cleanup (best-effort)
  result.cleanup.srcObjects = await tryRemove(srcBucket, expectedKeys);
  result.cleanup.dstObjects = await tryRemove(dstBucket, expectedKeys);
  result.cleanup.srcBucket = await tryRemoveBucket(srcBucket);
  result.cleanup.dstBucket = await tryRemoveBucket(dstBucket);

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
    """Run the Node verifier once. It collects listings + bodies for both
    buckets, then cleans up both buckets. Returns the parsed JSON payload."""
    script_path = os.path.join(PROJECT_DIR, "_verify.mjs")
    with open(script_path, "w", encoding="utf-8") as handle:
        handle.write(VERIFY_SCRIPT)

    src_bucket = _src_bucket()
    dst_bucket = _dst_bucket()
    env = os.environ.copy()

    result = subprocess.run(
        ["node", script_path, src_bucket, dst_bucket],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
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


def test_copy_ts_exists_and_uses_sdk():
    assert os.path.isfile(COPY_TS), f"Expected {COPY_TS} to exist."
    with open(COPY_TS, "r", encoding="utf-8") as handle:
        content = handle.read()
    assert "@tigrisdata/storage" in content, (
        "copy.ts must import from '@tigrisdata/storage'."
    )
    for symbol in ("createBucket", "list", "get", "put"):
        assert symbol in content, (
            f"copy.ts must reference the SDK symbol '{symbol}'."
        )


def test_destination_bucket_lists_exactly_five_keys(verify_payload):
    """Destination bucket must contain EXACTLY the five expected keys under
    the data/ prefix."""
    dst = verify_payload.get("dst", {})
    assert dst.get("listError") is None, (
        f"Listing destination bucket failed: {dst.get('listError')!r}"
    )
    listing = dst.get("listing")
    assert listing is not None, "Destination listing missing in verifier output."
    listing_set = set(listing)
    expected_set = set(EXPECTED_KEYS)
    assert listing_set == expected_set, (
        f"Destination bucket data/ prefix mismatch.\n"
        f"  expected: {sorted(expected_set)}\n"
        f"  got:      {sorted(listing_set)}"
    )


def test_destination_bodies_match_expected(verify_payload):
    """Each data/0N.json in the destination must contain exactly the expected
    JSON body, byte-for-byte."""
    dst_bodies = verify_payload.get("dst", {}).get("bodies", {})
    for key, expected in EXPECTED_BODIES.items():
        entry = dst_bodies.get(key)
        assert entry is not None, (
            f"Verifier did not fetch destination object {key}."
        )
        assert "error" not in entry, (
            f"Failed to GET destination object {key}: {entry.get('error')}"
        )
        got = entry.get("body", "")
        assert got == expected, (
            f"Destination object {key} content mismatch.\n"
            f"  expected: {expected!r}\n"
            f"  got:      {got!r}"
        )


def test_source_bucket_unchanged_listing(verify_payload):
    """Source bucket must still contain the same five seeded keys."""
    src = verify_payload.get("src", {})
    assert src.get("listError") is None, (
        f"Listing source bucket failed: {src.get('listError')!r}"
    )
    listing = src.get("listing")
    assert listing is not None, "Source listing missing in verifier output."
    listing_set = set(listing)
    expected_set = set(EXPECTED_KEYS)
    assert listing_set == expected_set, (
        f"Source bucket data/ prefix mismatch (the agent must NOT modify the "
        f"source bucket).\n"
        f"  expected: {sorted(expected_set)}\n"
        f"  got:      {sorted(listing_set)}"
    )


def test_source_bodies_unchanged(verify_payload):
    """Each data/0N.json in the source must still contain the exact original
    seeded JSON body."""
    src_bodies = verify_payload.get("src", {}).get("bodies", {})
    for key, expected in EXPECTED_BODIES.items():
        entry = src_bodies.get(key)
        assert entry is not None, (
            f"Verifier did not fetch source object {key}."
        )
        assert "error" not in entry, (
            f"Failed to GET source object {key}: {entry.get('error')}"
        )
        got = entry.get("body", "")
        assert got == expected, (
            f"Source object {key} was modified.\n"
            f"  expected: {expected!r}\n"
            f"  got:      {got!r}"
        )
