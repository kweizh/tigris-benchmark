import json
import os
import subprocess

import pytest

PROJECT_DIR = "/home/user/safe-fork"
INDEX_TS = os.path.join(PROJECT_DIR, "index.ts")
FORKS_JSON = os.path.join(PROJECT_DIR, "forks.json")
SOURCE_BUCKET = "source-bucket"
STALE_BUCKET = "eval-prefix-stale-001"
FORK_PREFIX = "eval-prefix"


def _tigris_env():
    env = os.environ.copy()
    access = env.get("TIGRIS_STORAGE_ACCESS_KEY_ID", "")
    secret = env.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY", "")
    env["AWS_ACCESS_KEY_ID"] = access
    env["AWS_SECRET_ACCESS_KEY"] = secret
    env["AWS_REGION"] = "auto"
    env["AWS_DEFAULT_REGION"] = "auto"
    return env


def _parse_bucket_names(stdout: str):
    stdout = stdout.strip()
    if not stdout:
        return []
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    names = []
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict):
                name = entry.get("name") or entry.get("Name") or entry.get("bucket")
                if isinstance(name, str):
                    names.append(name)
            elif isinstance(entry, str):
                names.append(entry)
    elif isinstance(data, dict):
        buckets = data.get("buckets") or data.get("Buckets") or []
        for entry in buckets:
            if isinstance(entry, dict):
                name = entry.get("name") or entry.get("Name") or entry.get("bucket")
                if isinstance(name, str):
                    names.append(name)
            elif isinstance(entry, str):
                names.append(entry)
    return names


def _list_buckets(env):
    result = subprocess.run(
        ["tigris", "buckets", "list", "--format", "json"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"'tigris buckets list --format json' failed: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    return _parse_bucket_names(result.stdout)


@pytest.fixture(scope="module")
def script_run_result():
    assert os.path.isfile(INDEX_TS), (
        f"User script not found at {INDEX_TS}; the agent must create it."
    )

    env = _tigris_env()

    install = subprocess.run(
        ["npm", "install", "--no-audit", "--no-fund"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )
    assert install.returncode == 0, (
        f"'npm install' failed in {PROJECT_DIR}: "
        f"stdout={install.stdout!r} stderr={install.stderr!r}"
    )

    result = subprocess.run(
        ["npx", "tsx", "index.ts"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )

    yield result

    # Best-effort cleanup of the source bucket and any lingering eval-prefix* buckets.
    try:
        names = _list_buckets(env)
        for name in names:
            if name == SOURCE_BUCKET or name.startswith(FORK_PREFIX):
                subprocess.run(
                    ["tigris", "buckets", "delete", name, "--force"],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=120,
                )
    except Exception:
        pass


def test_user_script_runs_successfully(script_run_result):
    assert script_run_result.returncode == 0, (
        "User script 'npx tsx index.ts' did not exit 0. "
        f"stdout={script_run_result.stdout!r} stderr={script_run_result.stderr!r}"
    )


def test_forks_json_has_three_unique_prefixed_names(script_run_result):
    assert script_run_result.returncode == 0, (
        "Skipping forks.json check because the user script failed: "
        f"{script_run_result.stderr!r}"
    )
    assert os.path.isfile(FORKS_JSON), (
        f"Expected {FORKS_JSON} to exist after the script ran."
    )
    with open(FORKS_JSON) as f:
        try:
            payload = json.load(f)
        except json.JSONDecodeError as exc:
            pytest.fail(f"{FORKS_JSON} is not valid JSON: {exc}")
    assert isinstance(payload, dict), (
        f"forks.json must decode to a JSON object, got: {type(payload).__name__}"
    )
    forks = payload.get("forks")
    assert isinstance(forks, list), (
        f"forks.json must contain a 'forks' list, got: {payload!r}"
    )
    assert len(forks) == 3, (
        f"Expected exactly 3 fork names in forks.json, got: {forks!r}"
    )
    for name in forks:
        assert isinstance(name, str) and name, (
            f"Every entry in forks.json 'forks' must be a non-empty string, got: {name!r}"
        )
        assert name.startswith(FORK_PREFIX), (
            f"Fork name '{name}' does not start with required prefix '{FORK_PREFIX}'."
        )
    assert len(set(forks)) == 3, (
        f"Expected 3 unique fork names in forks.json, got duplicates: {forks!r}"
    )


def test_stale_collision_bucket_was_cleaned_up(script_run_result):
    assert script_run_result.returncode == 0, (
        "Skipping stale-bucket cleanup check because the user script failed."
    )
    env = _tigris_env()
    names = _list_buckets(env)
    assert STALE_BUCKET not in names, (
        f"Pre-existing collision bucket '{STALE_BUCKET}' was NOT cleaned up by the user script. "
        f"Current buckets: {names}"
    )


def test_new_fork_buckets_were_torn_down(script_run_result):
    assert script_run_result.returncode == 0, (
        "Skipping fork teardown check because the user script failed."
    )
    with open(FORKS_JSON) as f:
        payload = json.load(f)
    fork_names = payload["forks"]

    env = _tigris_env()
    names = _list_buckets(env)
    still_present = [n for n in fork_names if n in names]
    assert not still_present, (
        f"The following fork buckets were NOT torn down by the user script: {still_present}. "
        f"Current buckets: {names}"
    )


def test_source_bucket_still_exists(script_run_result):
    assert script_run_result.returncode == 0, (
        "Skipping source-bucket existence check because the user script failed."
    )
    env = _tigris_env()
    names = _list_buckets(env)
    assert SOURCE_BUCKET in names, (
        f"Source bucket '{SOURCE_BUCKET}' must still exist after the script runs. "
        f"Current buckets: {names}"
    )
