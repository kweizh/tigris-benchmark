import json
import os
import subprocess

import pytest

PROJECT_DIR = "/home/user/tigris-task"
RUN_TS = os.path.join(PROJECT_DIR, "run.ts")
RUN_LOG = os.path.join(PROJECT_DIR, "run.log")
RECEIVED_JSONL = os.path.join(PROJECT_DIR, "received.jsonl")
TRIAL_ID_PATH = "/logs/artifacts/trial_id"

EXPECTED_TRIGGER_KEY = "runs/run1.finished"
NON_TRIGGER_KEYS = ("runs/run1.tmp", "other/run2.finished")
ALL_UPLOADED_KEYS = ("runs/run1.tmp", "runs/run1.finished", "other/run2.finished")


def _read_trial_id():
    with open(TRIAL_ID_PATH, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _bucket_name():
    import re
    name = f"harbor-coord-{_read_trial_id()}"
    name = re.sub(r"[^a-z0-9.-]", "-", name.lower())
    return name


def _load_received_payloads():
    if not os.path.isfile(RECEIVED_JSONL):
        return []
    payloads = []
    with open(RECEIVED_JSONL, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payloads.append(json.loads(line))
            except ValueError:
                pytest.fail(
                    f"received.jsonl contains a non-JSON line: {line!r}"
                )
    return payloads


def _extract_keys_from_payloads(payloads):
    """Collect every object key referenced by any payload.

    The Tigris notification schema is
    `{ events: [{ object: { key: ... } }] }`. We tolerate at-least-once
    duplicates by deduping keys per payload, but the verifier still inspects
    every payload.
    """
    keys = []
    for payload in payloads:
        events = payload.get("events") or []
        if not events:
            # Unknown shape — flag with full body so failures are diagnosable.
            keys.append(json.dumps(payload))
            continue
        for event in events:
            obj = event.get("object") or {}
            key = obj.get("key")
            keys.append(key)
    return keys


VERIFY_SCRIPT = r"""
import { list, remove, removeBucket } from "@tigrisdata/storage";
import { teardownCoordination } from "@tigrisdata/agent-kit";

const bucket = process.argv[2];

async function main() {
  const result = { listing: null, cleanup: {}, errors: [] };

  const listRes = await list({ config: { bucket } });
  if (listRes.error) {
    result.errors.push({ where: "list", message: String(listRes.error.message || listRes.error) });
  } else {
    result.listing = (listRes.data.items || []).map((item) => item.name);
  }

  // Tear down coordination first so future events stop firing on cleanup deletes.
  const tdc = await teardownCoordination(bucket);
  result.cleanup["__coordination__"] = tdc.error
    ? { error: String(tdc.error.message || tdc.error) }
    : { ok: true };

  for (const key of ["runs/run1.tmp", "runs/run1.finished", "other/run2.finished"]) {
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
    """Run the Node verifier once: list the bucket and clean it up."""
    script_path = os.path.join(PROJECT_DIR, "_verify.mts")
    with open(script_path, "w", encoding="utf-8") as handle:
        handle.write(VERIFY_SCRIPT)

    bucket = _bucket_name()
    env = os.environ.copy()

    result = subprocess.run(
        ["tsx", script_path, bucket],
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


def test_run_ts_exists_and_uses_both_sdks():
    assert os.path.isfile(RUN_TS), f"Expected {RUN_TS} to exist."
    with open(RUN_TS, "r", encoding="utf-8") as handle:
        content = handle.read()
    assert "@tigrisdata/storage" in content, (
        "run.ts must import from '@tigrisdata/storage'."
    )
    assert "@tigrisdata/agent-kit" in content, (
        "run.ts must import from '@tigrisdata/agent-kit'."
    )
    assert "setupCoordination" in content, (
        "run.ts must reference the SDK symbol 'setupCoordination'."
    )


def test_run_log_records_bucket_and_webhook():
    assert os.path.isfile(RUN_LOG), f"Expected {RUN_LOG} to exist."
    with open(RUN_LOG, "r", encoding="utf-8") as handle:
        content = handle.read()
    bucket = _bucket_name()
    assert f"bucket={bucket}" in content, (
        f"Expected run.log to contain 'bucket={bucket}', got:\n{content}"
    )
    assert "webhookUrl=" in content, (
        f"Expected run.log to contain a 'webhookUrl=' line, got:\n{content}"
    )
    assert "trycloudflare.com" in content, (
        "Expected run.log webhookUrl to reference the cloudflare quick-tunnel "
        f"(trycloudflare.com), got:\n{content}"
    )


def test_received_jsonl_exists():
    assert os.path.isfile(RECEIVED_JSONL), (
        f"Expected {RECEIVED_JSONL} to be present (pre-created by the entrypoint, "
        "appended to by the receiver)."
    )


def test_exactly_one_notification_for_finished_key():
    payloads = _load_received_payloads()
    keys = _extract_keys_from_payloads(payloads)

    assert keys, (
        "Expected at least one notification in received.jsonl, but the file is empty. "
        "Did setupCoordination run with the correct webhookUrl and filter?"
    )

    finished_count = sum(1 for k in keys if k == EXPECTED_TRIGGER_KEY)
    assert finished_count >= 1, (
        f"Expected at least one notification for {EXPECTED_TRIGGER_KEY!r}, "
        f"got keys: {keys}"
    )

    # Every observed key must be the target key. Anything else means the
    # filter (prefix `runs/` AND suffix `.finished`) was wrong.
    unexpected = [k for k in keys if k != EXPECTED_TRIGGER_KEY]
    assert not unexpected, (
        f"Notifications fired for unexpected keys: {unexpected!r}. "
        f"Only {EXPECTED_TRIGGER_KEY!r} should match the coordination filter."
    )


def test_no_notification_for_non_matching_keys():
    payloads = _load_received_payloads()
    keys = _extract_keys_from_payloads(payloads)
    for bad_key in NON_TRIGGER_KEYS:
        assert bad_key not in keys, (
            f"Notification fired for {bad_key!r}, which should have been filtered out "
            "by the coordination rule."
        )


def test_bucket_contains_all_three_uploaded_objects(verify_payload):
    listing = verify_payload.get("listing")
    assert listing is not None, (
        f"Verifier failed to list the bucket. Errors: {verify_payload.get('errors')}"
    )
    for key in ALL_UPLOADED_KEYS:
        assert key in listing, (
            f"Expected key {key!r} in remote bucket listing, got: {listing}"
        )
