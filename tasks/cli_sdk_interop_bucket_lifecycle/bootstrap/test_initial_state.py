import json
import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/tigris-task"
PACKAGE_JSON = os.path.join(PROJECT_DIR, "package.json")
NODE_MODULES = os.path.join(PROJECT_DIR, "node_modules")
TIGRIS_SDK_DIR = os.path.join(NODE_MODULES, "@tigrisdata", "storage")
TSX_BIN = os.path.join(NODE_MODULES, ".bin", "tsx")
TRIAL_ID_PATH = "/logs/artifacts/trial_id"


def _tigris_env():
    """Build an env dict that maps Tigris credentials into the AWS-compatible
    variables consumed by the `tigris` CLI."""
    env = os.environ.copy()
    access_key = os.environ.get("TIGRIS_STORAGE_ACCESS_KEY_ID")
    secret_key = os.environ.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY")
    assert access_key, "TIGRIS_STORAGE_ACCESS_KEY_ID must be set in the environment."
    assert secret_key, "TIGRIS_STORAGE_SECRET_ACCESS_KEY must be set in the environment."
    env["AWS_ACCESS_KEY_ID"] = access_key
    env["AWS_SECRET_ACCESS_KEY"] = secret_key
    env.setdefault("AWS_REGION", "auto")
    return env


def _trial_id():
    assert os.path.isfile(TRIAL_ID_PATH), (
        f"Expected trial id file at {TRIAL_ID_PATH} to exist before the task starts."
    )
    with open(TRIAL_ID_PATH, "r", encoding="utf-8") as handle:
        value = handle.read().strip()
    assert value, f"Trial id file {TRIAL_ID_PATH} is empty."
    return value


def test_tigris_cli_available():
    assert shutil.which("tigris") is not None, (
        "tigris CLI binary not found in PATH. The @tigrisdata/cli npm package "
        "must be installed globally."
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
        "tsx binary not found in PATH; it must be installed globally so the agent "
        "can run TypeScript directly."
    )


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected project directory {PROJECT_DIR} to exist before the task starts."
    )


def test_package_json_declares_required_deps():
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


def test_node_modules_pre_installed():
    assert os.path.isdir(NODE_MODULES), (
        f"Expected {NODE_MODULES} to exist (run `npm install` during image build)."
    )
    assert os.path.isdir(TIGRIS_SDK_DIR), (
        f"Expected @tigrisdata/storage to be installed at {TIGRIS_SDK_DIR}."
    )
    assert os.path.isfile(TSX_BIN) or os.path.islink(TSX_BIN), (
        f"Expected local tsx binary at {TSX_BIN}."
    )


def test_tigris_credentials_env_vars_present():
    for var in ("TIGRIS_STORAGE_ACCESS_KEY_ID", "TIGRIS_STORAGE_SECRET_ACCESS_KEY"):
        assert os.environ.get(var), (
            f"Environment variable {var} must be provided by Harbor so both "
            "the CLI and the SDK can authenticate against Tigris."
        )


def test_trial_id_artifact_present():
    trial_id = _trial_id()
    assert trial_id, "Trial id artifact must contain a non-empty value."


def test_tigris_cli_can_list_buckets():
    """The CLI must be functional and authenticated before the agent runs."""
    result = subprocess.run(
        ["tigris", "buckets", "list", "--format", "json"],
        capture_output=True,
        text=True,
        env=_tigris_env(),
        cwd=PROJECT_DIR,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"'tigris buckets list --format json' failed with returncode "
        f"{result.returncode}. stderr={result.stderr!r} stdout={result.stdout!r}"
    )
    try:
        json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"'tigris buckets list --format json' did not return valid JSON: {exc}. "
            f"stdout={result.stdout!r}"
        )


def test_target_bucket_does_not_yet_exist():
    """The bucket the agent must create must NOT already exist in the org."""
    bucket_name = f"harbor-interop-{_trial_id()}"
    import re
    bucket_name = re.sub(r"[^a-z0-9.-]", "-", bucket_name.lower())
    result = subprocess.run(
        ["tigris", "buckets", "list", "--format", "json"],
        capture_output=True,
        text=True,
        env=_tigris_env(),
        cwd=PROJECT_DIR,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"'tigris buckets list --format json' failed: stderr={result.stderr!r}"
    )
    payload = json.loads(result.stdout)
    if isinstance(payload, dict):
        buckets = payload.get("items", []) or payload.get("buckets", [])
    else:
        buckets = payload
    bucket_names = [b.get("name") for b in buckets if isinstance(b, dict)]
    assert bucket_name not in bucket_names, (
        f"Bucket {bucket_name!r} unexpectedly already exists in the Tigris "
        f"organization before the task begins. Existing buckets: {bucket_names}"
    )


def test_index_ts_and_listing_not_created_yet():
    assert not os.path.exists(os.path.join(PROJECT_DIR, "index.ts")), (
        "index.ts must not exist before the agent writes it."
    )
    assert not os.path.exists(os.path.join(PROJECT_DIR, "bucket-listing.txt")), (
        "bucket-listing.txt must not exist before the agent generates it."
    )
