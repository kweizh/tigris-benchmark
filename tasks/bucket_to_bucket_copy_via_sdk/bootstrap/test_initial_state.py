import json
import os
import shutil
import subprocess
import time

import pytest

PROJECT_DIR = "/home/user/tigris-task"
PACKAGE_JSON = os.path.join(PROJECT_DIR, "package.json")
NODE_MODULES = os.path.join(PROJECT_DIR, "node_modules")
TIGRIS_SDK_DIR = os.path.join(NODE_MODULES, "@tigrisdata", "storage")
TSX_BIN = os.path.join(NODE_MODULES, ".bin", "tsx")
TRIAL_ID_PATH = "/logs/artifacts/trial_id"
SEED_DONE_SENTINEL = "/tmp/tigris-seed.done"
SEED_LOG = "/var/log/tigris-seed.log"

EXPECTED_KEYS = [
    "data/01.json",
    "data/02.json",
    "data/03.json",
    "data/04.json",
    "data/05.json",
]


def _read_trial_id():
    assert os.path.isfile(TRIAL_ID_PATH), (
        f"Expected trial id file at {TRIAL_ID_PATH} to exist before the task starts."
    )
    with open(TRIAL_ID_PATH) as f:
        trial_id = f.read().strip()
    assert trial_id, f"{TRIAL_ID_PATH} must contain a non-empty trial id."
    return trial_id


def _src_bucket_name():
    return f"harbor-src-{_read_trial_id()}"


def _dst_bucket_name():
    return f"harbor-dst-{_read_trial_id()}"


def _tigris_cli_env():
    """Map TIGRIS_STORAGE_* credentials to the AWS-compatible variables that
    the `tigris` CLI consumes."""
    env = os.environ.copy()
    access_key = os.environ.get("TIGRIS_STORAGE_ACCESS_KEY_ID")
    secret_key = os.environ.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY")
    assert access_key, "TIGRIS_STORAGE_ACCESS_KEY_ID is not set in the environment."
    assert secret_key, "TIGRIS_STORAGE_SECRET_ACCESS_KEY is not set in the environment."
    env["AWS_ACCESS_KEY_ID"] = access_key
    env["AWS_SECRET_ACCESS_KEY"] = secret_key
    env.setdefault("AWS_REGION", "auto")
    return env


def _wait_for_seed_sentinel(timeout_sec=240):
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if os.path.exists(SEED_DONE_SENTINEL):
            return
        time.sleep(2)
    log_tail = ""
    if os.path.isfile(SEED_LOG):
        try:
            with open(SEED_LOG) as f:
                log_tail = f.read()[-4000:]
        except OSError:
            log_tail = "<unable to read seed log>"
    pytest.fail(
        f"Entrypoint seed sentinel {SEED_DONE_SENTINEL} did not appear within "
        f"{timeout_sec}s. Seed log tail:\n{log_tail}"
    )


def test_node_binary_available():
    assert shutil.which("node") is not None, "node binary not found in PATH."


def test_npm_binary_available():
    assert shutil.which("npm") is not None, "npm binary not found in PATH."


def test_node_major_version_is_24():
    result = subprocess.run(
        ["node", "--version"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, f"'node --version' failed: {result.stderr}"
    version = result.stdout.strip()
    assert version.startswith("v24."), (
        f"Expected Node.js v24.x to be installed, got: {version}"
    )


def test_global_tsx_available():
    assert shutil.which("tsx") is not None, (
        "tsx binary not found in PATH; it must be installed globally so the agent can run TypeScript directly."
    )


def test_tigris_cli_available():
    assert shutil.which("tigris") is not None, (
        "tigris CLI binary not found in PATH; required by the container entrypoint to seed the source bucket."
    )


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected project directory {PROJECT_DIR} to exist."
    )


def test_package_json_exists_with_required_deps():
    assert os.path.isfile(PACKAGE_JSON), (
        f"Expected {PACKAGE_JSON} to exist with @tigrisdata/storage and tsx dependencies."
    )
    with open(PACKAGE_JSON, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    deps = {}
    deps.update(manifest.get("dependencies", {}) or {})
    deps.update(manifest.get("devDependencies", {}) or {})
    assert "@tigrisdata/storage" in deps, (
        "package.json must declare @tigrisdata/storage as a dependency."
    )
    assert "tsx" in deps, "package.json must declare tsx as a dependency."


def test_node_modules_installed():
    assert os.path.isdir(NODE_MODULES), (
        f"Expected {NODE_MODULES} to exist (run `npm install` during image build)."
    )
    assert os.path.isdir(TIGRIS_SDK_DIR), (
        f"Expected @tigrisdata/storage to be installed at {TIGRIS_SDK_DIR}."
    )
    assert os.path.isfile(TSX_BIN) or os.path.islink(TSX_BIN), (
        f"Expected local tsx binary at {TSX_BIN}."
    )


def test_tigris_credentials_present_in_env():
    for var in (
        "TIGRIS_STORAGE_ACCESS_KEY_ID",
        "TIGRIS_STORAGE_SECRET_ACCESS_KEY",
        "TIGRIS_STORAGE_ENDPOINT",
    ):
        assert os.environ.get(var), (
            f"Environment variable {var} must be set so the SDK can authenticate against Tigris."
        )


def test_trial_id_artifact_present():
    trial_id = _read_trial_id()
    assert trial_id, f"{TRIAL_ID_PATH} must contain a non-empty trial id."


def test_copy_ts_not_created_yet():
    """The agent is the one that must create copy.ts. It should not exist yet."""
    assert not os.path.exists(os.path.join(PROJECT_DIR, "copy.ts")), (
        "copy.ts must not exist before the agent writes it."
    )


def test_entrypoint_seed_completed():
    """The container entrypoint must have created the source bucket and
    uploaded the five seed objects before the agent runs."""
    _wait_for_seed_sentinel()
    assert os.path.isfile(SEED_DONE_SENTINEL), (
        f"Entrypoint sentinel {SEED_DONE_SENTINEL} missing after wait."
    )


def test_seeded_source_bucket_exists_in_tigris():
    """The pre-seeded source bucket must be visible to the Tigris CLI."""
    _wait_for_seed_sentinel()
    bucket_name = _src_bucket_name()
    result = subprocess.run(
        ["tigris", "buckets", "list", "--format", "json"],
        capture_output=True,
        text=True,
        env=_tigris_cli_env(),
        cwd=PROJECT_DIR,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"'tigris buckets list --format json' failed with returncode "
        f"{result.returncode}. stderr={result.stderr!r} stdout={result.stdout!r}"
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"'tigris buckets list --format json' did not return valid JSON: "
            f"{exc}. stdout={result.stdout!r}"
        )
    if isinstance(payload, dict):
        buckets = payload.get("items", []) or payload.get("buckets", []) or []
    else:
        buckets = payload
    names = [b.get("name") for b in buckets if isinstance(b, dict)]
    assert bucket_name in names, (
        f"Expected pre-seeded source bucket {bucket_name!r} in Tigris, but it "
        f"was not in the bucket list. Got: {names}"
    )


def test_seeded_objects_listed_under_data_prefix():
    """All five `data/0N.json` objects must already be in the source bucket."""
    _wait_for_seed_sentinel()
    bucket_name = _src_bucket_name()
    result = subprocess.run(
        ["tigris", "ls", f"t3://{bucket_name}/data/"],
        capture_output=True,
        text=True,
        env=_tigris_cli_env(),
        cwd=PROJECT_DIR,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"'tigris ls t3://{bucket_name}/data/' failed: returncode="
        f"{result.returncode} stderr={result.stderr!r} stdout={result.stdout!r}"
    )
    for key in EXPECTED_KEYS:
        leaf = key.split("/", 1)[1]
        assert leaf in result.stdout, (
            f"Expected pre-seeded object {key!r} (leaf {leaf!r}) to be listed "
            f"under t3://{bucket_name}/data/, but it was not in the listing. "
            f"Got stdout:\n{result.stdout}"
        )


def test_destination_bucket_not_yet_present():
    """The destination bucket must NOT exist before the agent runs."""
    _wait_for_seed_sentinel()
    dst_bucket = _dst_bucket_name()
    result = subprocess.run(
        ["tigris", "buckets", "list", "--format", "json"],
        capture_output=True,
        text=True,
        env=_tigris_cli_env(),
        cwd=PROJECT_DIR,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"'tigris buckets list --format json' failed: returncode="
        f"{result.returncode} stderr={result.stderr!r}"
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = []
    if isinstance(payload, dict):
        buckets = payload.get("items", []) or payload.get("buckets", []) or []
    else:
        buckets = payload
    names = [b.get("name") for b in buckets if isinstance(b, dict)]
    assert dst_bucket not in names, (
        f"Destination bucket {dst_bucket!r} must not exist before the agent "
        f"runs; the agent is responsible for creating it. Got: {names}"
    )
