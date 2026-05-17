import json
import os
import re
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/inv"
INDEX_JS = os.path.join(PROJECT_DIR, "index.js")
INVENTORY_FILE = os.path.join(PROJECT_DIR, "inventory.json")
TRIAL_ID_FILE = "/logs/artifacts/trial_id"

def _read_trial_id():
    assert os.path.isfile(TRIAL_ID_FILE), (
        f"Trial id file {TRIAL_ID_FILE} does not exist; cannot derive bucket names."
    )
    with open(TRIAL_ID_FILE, "r") as f:
        trial_id = f.read().strip()
    assert trial_id, f"Trial id file {TRIAL_ID_FILE} is empty."
    return trial_id

def _prefix():
    trial_id = _read_trial_id()
    name = f"harbor-inv-{trial_id}-"
    return re.sub(r"[^a-z0-9.-]", "-", name.lower())

def _bench_buckets():
    prefix = _prefix()
    return [f"{prefix}a", f"{prefix}b", f"{prefix}c"]

def _other_buckets():
    trial_id = _read_trial_id()
    return [
        f"harbor-other-{trial_id}-x",
        f"harbor-other-{trial_id}-y",
        f"harbor-other-{trial_id}-z",
    ]

def _expected_counts():
    prefix = _prefix()
    return {
        f"{prefix}a": 2,
        f"{prefix}b": 1,
        f"{prefix}c": 3,
    }

EXPECTED_TOTAL = 6
EXPECTED_BUCKET_COUNT = 3


def _tigris_env():
    """Map Harbor's TIGRIS_STORAGE_* credentials onto the AWS-compatible
    variables consumed by the `tigris` CLI."""
    env = os.environ.copy()
    access_key = os.environ.get("TIGRIS_STORAGE_ACCESS_KEY_ID")
    secret_key = os.environ.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY")
    assert access_key, (
        "TIGRIS_STORAGE_ACCESS_KEY_ID is not set in the verifier environment."
    )
    assert secret_key, (
        "TIGRIS_STORAGE_SECRET_ACCESS_KEY is not set in the verifier environment."
    )
    env["AWS_ACCESS_KEY_ID"] = access_key
    env["AWS_SECRET_ACCESS_KEY"] = secret_key
    env.setdefault("AWS_REGION", "auto")
    return env


def _run_tigris(args, timeout=120):
    return subprocess.run(
        ["tigris", *args],
        capture_output=True,
        text=True,
        env=_tigris_env(),
        cwd=PROJECT_DIR,
        timeout=timeout,
    )


def _list_snapshot_versions(bucket):
    """Return the set of snapshot version strings for `bucket` as reported by
    `tigris snapshots list <bucket> --format json`."""
    result = _run_tigris(
        ["snapshots", "list", bucket, "--format", "json"], timeout=120
    )
    assert result.returncode == 0, (
        f"'tigris snapshots list {bucket} --format json' failed: "
        f"returncode={result.returncode}, stdout={result.stdout!r}, "
        f"stderr={result.stderr!r}"
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"'tigris snapshots list {bucket} --format json' did not emit "
            f"valid JSON: {exc!s}; stdout={result.stdout!r}"
        )
    snaps = payload.get("snapshots") if isinstance(payload, dict) else None
    assert isinstance(snaps, list), (
        f"Expected a 'snapshots' list in the CLI output for bucket "
        f"{bucket}, got: {payload!r}"
    )
    versions = []
    for entry in snaps:
        assert isinstance(entry, dict), (
            f"Snapshot entry must be an object, got: {entry!r}"
        )
        version = entry.get("version")
        assert isinstance(version, str) and version, (
            f"Snapshot entry for bucket {bucket} must have a non-empty "
            f"string 'version'. Got: {entry!r}"
        )
        versions.append(version)
    return set(versions)


@pytest.fixture(scope="module", autouse=True)
def _cleanup_buckets_after_tests():
    """Run the test module, then tear down every bucket created by setup.sh
    so subsequent runs of this evaluation start from a clean Tigris account."""
    yield
    # Best-effort cleanup; do not fail the suite if a bucket is already gone.
    for bucket in _bench_buckets() + _other_buckets():
        _run_tigris(["buckets", "delete", bucket, "--yes"], timeout=120)


def test_tigris_cli_available():
    """Sanity check that we can find the Tigris CLI we use throughout the
    verifier."""
    assert shutil.which("tigris") is not None, (
        "tigris CLI binary not found in PATH; cannot verify final state."
    )


def test_index_js_authored_by_user():
    """The user must have authored /home/user/inv/index.js."""
    assert os.path.isfile(INDEX_JS), (
        f"Expected user-authored script at {INDEX_JS}, but it does not exist."
    )


def test_node_script_runs_and_prints_summary():
    """Priority 1: Re-run the user's script and assert exit code + stdout
    summary line. This also (re)produces /home/user/inv/inventory.json."""
    assert os.path.isfile(INDEX_JS), (
        f"Expected user-authored script at {INDEX_JS}; run cannot proceed."
    )
    result = subprocess.run(
        ["node", "index.js"],
        capture_output=True,
        text=True,
        cwd=PROJECT_DIR,
        env=_tigris_env(),
        timeout=180,
    )
    assert result.returncode == 0, (
        f"'node index.js' failed with returncode {result.returncode}. "
        f"stdout={result.stdout!r}, stderr={result.stderr!r}"
    )
    expected = f"{EXPECTED_BUCKET_COUNT} buckets, {EXPECTED_TOTAL} snapshots"
    assert expected in result.stdout, (
        f"Expected stdout of 'node index.js' to contain {expected!r}, "
        f"but it did not. Full stdout: {result.stdout!r}"
    )


def test_inventory_file_exists_after_run():
    assert os.path.isfile(INVENTORY_FILE), (
        f"Expected {INVENTORY_FILE} to exist after running index.js."
    )


def test_inventory_file_has_correct_keys_and_counts():
    """The aggregated inventory must list exactly the three harbor-inv-*
    buckets with the expected snapshot counts."""
    with open(INVENTORY_FILE) as f:
        try:
            inventory = json.load(f)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"{INVENTORY_FILE} is not valid JSON: {exc!s}."
            )
    assert isinstance(inventory, dict), (
        f"{INVENTORY_FILE} must be a JSON object keyed by bucket name. "
        f"Got: {type(inventory).__name__}"
    )
    actual_keys = set(inventory.keys())
    expected_counts = _expected_counts()
    expected_keys = set(expected_counts.keys())
    assert actual_keys == expected_keys, (
        f"{INVENTORY_FILE} must have exactly the keys {sorted(expected_keys)}, "
        f"but it has {sorted(actual_keys)}. Distractor buckets (harbor-other-*) "
        "must be filtered out."
    )
    total = 0
    for bucket, expected_count in expected_counts.items():
        value = inventory[bucket]
        assert isinstance(value, list), (
            f"inventory.json[{bucket!r}] must be a list of snapshot version "
            f"strings, got: {type(value).__name__}"
        )
        for v in value:
            assert isinstance(v, str) and v, (
                f"Each snapshot version under inventory.json[{bucket!r}] "
                f"must be a non-empty string, got: {v!r}"
            )
        assert len(value) == expected_count, (
            f"inventory.json[{bucket!r}] must list {expected_count} "
            f"snapshot version(s); got {len(value)}: {value!r}"
        )
        total += len(value)
    assert total == EXPECTED_TOTAL, (
        f"Total number of snapshot version IDs across inventory.json must "
        f"be {EXPECTED_TOTAL}; got {total}."
    )


def test_inventory_versions_match_cli_truth():
    """Priority 1: For every harbor-inv-* bucket, the snapshot version IDs
    recorded in inventory.json must equal the version IDs reported by the
    live Tigris CLI for that bucket."""
    with open(INVENTORY_FILE) as f:
        inventory = json.load(f)
    for bucket in _expected_counts():
        recorded = set(inventory.get(bucket) or [])
        truth = _list_snapshot_versions(bucket)
        assert recorded == truth, (
            f"Snapshot version IDs in inventory.json[{bucket!r}] do not "
            f"match the live Tigris CLI output. inventory.json reports "
            f"{sorted(recorded)}; tigris CLI reports {sorted(truth)}."
        )
