import json
import os
import re
import subprocess

import pytest

PROJECT_DIR = "/home/user/tigris-task"
INDEX_TS = os.path.join(PROJECT_DIR, "index.ts")
LISTING_TXT = os.path.join(PROJECT_DIR, "bucket-listing.txt")
TRIAL_ID_PATH = "/logs/artifacts/trial_id"


def _tigris_env():
    env = os.environ.copy()
    access_key = os.environ.get("TIGRIS_STORAGE_ACCESS_KEY_ID")
    secret_key = os.environ.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY")
    assert access_key, "TIGRIS_STORAGE_ACCESS_KEY_ID is not set in the verifier environment."
    assert secret_key, "TIGRIS_STORAGE_SECRET_ACCESS_KEY is not set in the verifier environment."
    env["AWS_ACCESS_KEY_ID"] = access_key
    env["AWS_SECRET_ACCESS_KEY"] = secret_key
    env.setdefault("AWS_REGION", "auto")
    return env


def _read_trial_id():
    assert os.path.isfile(TRIAL_ID_PATH), (
        f"trial_id file {TRIAL_ID_PATH} is missing; cannot derive bucket name."
    )
    with open(TRIAL_ID_PATH, "r", encoding="utf-8") as handle:
        value = handle.read().strip()
    assert value, f"trial_id file {TRIAL_ID_PATH} is empty."
    return value


def _bucket_name():
    import re
    name = f"harbor-interop-{_read_trial_id()}"
    name = re.sub(r"[^a-z0-9.-]", "-", name.lower())
    return name


def _expected_manifest_body(trial_id: str) -> str:
    return (
        '{"created_by":"cli","modified_by":"sdk","trial":"' + trial_id + '"}'
    )


def _run_tigris(args, timeout=120):
    return subprocess.run(
        ["tigris", *args],
        capture_output=True,
        text=True,
        env=_tigris_env(),
        cwd=PROJECT_DIR,
        timeout=timeout,
    )


VERIFY_SCRIPT = r"""
import { get, remove } from "@tigrisdata/storage";

const bucket = process.argv[2];

async function main() {
  const result = { manifest: null, cleanup: {}, errors: [] };

  const getRes = await get("manifest.json", "string", { config: { bucket } });
  if (getRes.error) {
    result.errors.push({
      where: "get_manifest",
      message: String(getRes.error.message || getRes.error),
    });
  } else {
    result.manifest = getRes.data;
  }

  // Best-effort cleanup of the manifest object so the bucket can be deleted.
  const rmRes = await remove("manifest.json", { config: { bucket } });
  result.cleanup["manifest.json"] = rmRes.error
    ? { error: String(rmRes.error.message || rmRes.error) }
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
def manifest_payload():
    """Use the @tigrisdata/storage SDK from a Node helper to fetch the
    manifest object and also delete it so the bucket can be cleaned up."""
    script_path = os.path.join(PROJECT_DIR, "_verify.mjs")
    with open(script_path, "w", encoding="utf-8") as handle:
        handle.write(VERIFY_SCRIPT)

    bucket = _bucket_name()
    result = subprocess.run(
        ["node", script_path, bucket],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
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
        f"Verifier reported a fatal error: {payload.get('fatal')}"
    )
    return payload


@pytest.fixture(scope="module", autouse=True)
def cleanup_bucket_after_tests():
    """Yield to the tests, then delete the bucket so subsequent runs are clean."""
    yield
    bucket_name = _bucket_name()
    # Best-effort: try to remove the manifest first via the SDK helper (if not
    # already removed by manifest_payload), then delete the bucket.
    rm_script = os.path.join(PROJECT_DIR, "_cleanup.mjs")
    try:
        with open(rm_script, "w", encoding="utf-8") as handle:
            handle.write(
                "import { remove } from \"@tigrisdata/storage\";\n"
                "const bucket = process.argv[2];\n"
                "try { await remove(\"manifest.json\", { config: { bucket } }); }\n"
                "catch (_e) {}\n"
            )
        subprocess.run(
            ["node", rm_script, bucket_name],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            timeout=60,
        )
    except Exception:
        pass
    finally:
        try:
            os.remove(rm_script)
        except OSError:
            pass

    _run_tigris(["buckets", "delete", bucket_name, "--yes"], timeout=120)


def test_index_ts_exists_and_uses_sdk():
    assert os.path.isfile(INDEX_TS), f"Expected {INDEX_TS} to exist."
    with open(INDEX_TS, "r", encoding="utf-8") as handle:
        content = handle.read()
    assert "@tigrisdata/storage" in content, (
        "index.ts must import from '@tigrisdata/storage'."
    )
    assert "put" in content, "index.ts must reference the SDK symbol 'put'."


def test_bucket_appears_in_list():
    """Priority 1: confirm via Tigris CLI that the new bucket exists."""
    bucket_name = _bucket_name()
    result = _run_tigris(["buckets", "list", "--format", "json"])
    assert result.returncode == 0, (
        f"'tigris buckets list --format json' failed: returncode="
        f"{result.returncode}, stderr={result.stderr!r}"
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"'tigris buckets list --format json' returned invalid JSON: {exc}. "
            f"stdout={result.stdout!r}"
        )

    def _collect_names(node):
        names = []
        if isinstance(node, list):
            for item in node:
                names.extend(_collect_names(item))
        elif isinstance(node, dict):
            for key, value in node.items():
                if key.lower() in {"name", "bucket", "bucketname"} and isinstance(value, str):
                    names.append(value)
                else:
                    names.extend(_collect_names(value))
        return names

    names = _collect_names(payload)
    assert bucket_name in names, (
        f"Expected bucket {bucket_name!r} to appear in `tigris buckets list --format json`, "
        f"but it was not found. Collected names: {names}"
    )


def _flatten_for_search(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                yield from _flatten_for_search(value)
            else:
                yield str(key), value
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                yield from _flatten_for_search(item)
            else:
                yield "", item


def test_bucket_has_snapshots_enabled_and_seven_day_ttl():
    """Priority 1: parse `tigris buckets get --format json` and assert both
    snapshots-enabled and 7-day TTL are reflected in the bucket configuration."""
    bucket_name = _bucket_name()
    result = _run_tigris(["buckets", "get", bucket_name, "--format", "json"])
    assert result.returncode == 0, (
        f"'tigris buckets get {bucket_name} --format json' failed: returncode="
        f"{result.returncode}, stderr={result.stderr!r}"
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"'tigris buckets get {bucket_name} --format json' returned invalid JSON: "
            f"{exc}. stdout={result.stdout!r}"
        )

    snapshot_keywords = ("snapshot", "version")
    ttl_keywords = ("ttl", "expir")
    seven_day_pattern = re.compile(r"\b7\s*day", re.IGNORECASE)
    enabled_pattern = re.compile(r"\benable", re.IGNORECASE)

    rows = []
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        # Some `tigris buckets get` outputs are property/value row lists nested
        # under a key; others are a structured object.
        for value in payload.values():
            if isinstance(value, list):
                rows.extend(value)

    snapshot_ok = False
    ttl_ok = False

    # Shape 1: list of {property, value} rows.
    for row in rows:
        if not isinstance(row, dict):
            continue
        prop = str(row.get("property", "")).lower()
        value = row.get("value")
        value_str = "" if value is None else str(value)
        if not snapshot_ok and any(kw in prop for kw in snapshot_keywords):
            if enabled_pattern.search(value_str) or value_str.strip().lower() in {
                "true",
                "yes",
                "on",
            }:
                snapshot_ok = True
        if not ttl_ok and any(kw in prop for kw in ttl_keywords):
            if seven_day_pattern.search(value_str):
                ttl_ok = True
            elif "day" in prop and value_str.strip() == "7":
                ttl_ok = True

    # Shape 2: structured object. Walk all keys looking for snapshot/TTL fields.
    if not (snapshot_ok and ttl_ok) and isinstance(payload, dict):
        for key, value in _flatten_for_search(payload):
            key_lower = key.lower()
            value_str = "" if value is None else str(value)
            if not snapshot_ok and any(kw in key_lower for kw in snapshot_keywords):
                if isinstance(value, bool) and value:
                    snapshot_ok = True
                elif value_str.lower() in {"true", "yes", "on", "enabled"}:
                    snapshot_ok = True
                elif enabled_pattern.search(value_str):
                    snapshot_ok = True
            if not ttl_ok and any(kw in key_lower for kw in ttl_keywords):
                if seven_day_pattern.search(value_str):
                    ttl_ok = True
                elif "day" in key_lower and value_str.strip() == "7":
                    ttl_ok = True
                elif isinstance(value, (int, float)) and "day" in key_lower and int(value) == 7:
                    ttl_ok = True

    assert snapshot_ok, (
        "Expected `tigris buckets get` output to indicate that snapshots are enabled on "
        f"{bucket_name!r}, but no snapshot/version-related field reflected an enabled "
        f"state. Payload: {payload!r}"
    )
    assert ttl_ok, (
        "Expected `tigris buckets get` output to indicate a 7-day object expiration TTL on "
        f"{bucket_name!r}, but no TTL/expiration-related field reflected a 7-day window. "
        f"Payload: {payload!r}"
    )


def test_snapshots_list_succeeds_for_bucket():
    """Backstop: `tigris snapshots list <bucket>` only succeeds for snapshot-enabled buckets."""
    bucket_name = _bucket_name()
    result = _run_tigris(["snapshots", "list", bucket_name])
    assert result.returncode == 0, (
        f"Expected `tigris snapshots list {bucket_name}` to succeed (which indicates "
        "snapshots are enabled), but it exited with code "
        f"{result.returncode}.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_manifest_object_body_matches_expected(manifest_payload):
    body = manifest_payload.get("manifest")
    errors = manifest_payload.get("errors", [])
    assert body is not None, (
        "Verifier could not fetch manifest.json via the @tigrisdata/storage SDK. "
        f"Errors: {errors}"
    )
    trial_id = _read_trial_id()
    expected = _expected_manifest_body(trial_id)
    # Some SDK responses may not preserve exact bytes if Content-Type differs;
    # accept both raw match and JSON-equivalence match.
    if body != expected:
        try:
            assert json.loads(body) == json.loads(expected), (
                f"manifest.json content mismatch. Expected exactly {expected!r}, "
                f"got {body!r}."
            )
        except (ValueError, AssertionError) as exc:
            pytest.fail(
                f"manifest.json content mismatch. Expected {expected!r}, got {body!r}. "
                f"Details: {exc}"
            )


def test_bucket_listing_file_mentions_manifest():
    assert os.path.isfile(LISTING_TXT), (
        f"Expected listing file {LISTING_TXT} to exist."
    )
    with open(LISTING_TXT, "r", encoding="utf-8") as handle:
        content = handle.read()
    assert "manifest.json" in content, (
        f"Expected {LISTING_TXT} to mention 'manifest.json'. Got contents: {content!r}"
    )
