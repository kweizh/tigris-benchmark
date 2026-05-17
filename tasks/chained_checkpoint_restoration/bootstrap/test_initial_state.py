import json
import os
import re
import shutil
import subprocess
import time

import pytest

PROJECT_DIR = "/home/user/chained-ckpt"
PACKAGE_JSON = os.path.join(PROJECT_DIR, "package.json")
TRIAL_ID_FILE = "/logs/artifacts/trial_id"


def _read_trial_id():
    assert os.path.isfile(TRIAL_ID_FILE), (
        f"Trial id file {TRIAL_ID_FILE} does not exist; cannot derive bucket name."
    )
    with open(TRIAL_ID_FILE, "r") as f:
        trial_id = f.read().strip()
    assert trial_id, f"Trial id file {TRIAL_ID_FILE} is empty."
    return trial_id


def bucket_name():
    trial_id = _read_trial_id()
    name = f"harbor-awscli-{trial_id}"
    return re.sub(r"[^a-z0-9.-]", "-", name.lower())


def _tigris_env():
    env = os.environ.copy()
    access = env.get("TIGRIS_STORAGE_ACCESS_KEY_ID", "")
    secret = env.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY", "")
    env["AWS_ACCESS_KEY_ID"] = access
    env["AWS_SECRET_ACCESS_KEY"] = secret
    env["AWS_REGION"] = "auto"
    env["AWS_DEFAULT_REGION"] = "auto"
    return env


def test_pre_create_bucket():
    """Pre-create the bucket using the dynamically constructed name with snapshots enabled."""
    name = bucket_name()
    env = _tigris_env()
    
    # Configure tigris CLI first
    subprocess.run(
        [
            "tigris", "configure", 
            "--access-key", env.get("TIGRIS_STORAGE_ACCESS_KEY_ID", ""), 
            "--access-secret", env.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY", ""), 
            "--endpoint", "https://t3.storage.dev"
        ],
        capture_output=True,
        text=True,
    )

    # Create the bucket with snapshots enabled if it does not already exist
    check = subprocess.run(
        ["tigris", "buckets", "get", name],
        capture_output=True,
        text=True,
        env=env,
    )
    if check.returncode == 0:
        # Ensure snapshots are enabled
        subprocess.run(
            ["tigris", "buckets", "set", name, "--enable-snapshots"],
            capture_output=True,
            text=True,
            env=env,
        )
    else:
        create = subprocess.run(
            ["tigris", "buckets", "create", name, "--enable-snapshots"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert create.returncode == 0, (
            f"Failed to create bucket {name}: {create.stderr}"
        )


def test_node_binary_available():
    assert shutil.which("node") is not None, "node binary not found in PATH."


def test_node_major_version_is_24():
    result = subprocess.run(
        ["node", "--version"], capture_output=True, text=True
    )
    assert result.returncode == 0, (
        f"'node --version' failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    version = result.stdout.strip().lstrip("v")
    major = version.split(".")[0]
    assert major == "24", (
        f"Expected Node.js major version 24, got '{version}' from 'node --version'."
    )


def test_npm_binary_available():
    assert shutil.which("npm") is not None, "npm binary not found in PATH."


def test_npx_binary_available():
    assert shutil.which("npx") is not None, "npx binary not found in PATH."


def test_tigris_cli_available():
    assert shutil.which("tigris") is not None, (
        "tigris CLI binary not found in PATH; @tigrisdata/cli must be globally installed."
    )


def test_agent_kit_installed_globally():
    result = subprocess.run(
        ["npm", "ls", "-g", "--depth=0", "--json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"'npm ls -g --depth=0 --json' failed: {result.stderr}"
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Could not parse 'npm ls -g --json' output: {exc}")
    deps = data.get("dependencies", {})
    assert "@tigrisdata/agent-kit" in deps, (
        f"@tigrisdata/agent-kit must be installed globally, got: {list(deps.keys())}"
    )
    assert "@tigrisdata/cli" in deps, (
        f"@tigrisdata/cli must be installed globally, got: {list(deps.keys())}"
    )


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} does not exist."
    )


def test_package_json_exists():
    assert os.path.isfile(PACKAGE_JSON), (
        f"package.json not found at {PACKAGE_JSON}."
    )


def test_package_json_declares_agent_kit_dependency():
    with open(PACKAGE_JSON) as f:
        manifest = json.load(f)
    deps = {}
    deps.update(manifest.get("dependencies", {}))
    deps.update(manifest.get("devDependencies", {}))
    assert "@tigrisdata/agent-kit" in deps, (
        f"package.json must declare '@tigrisdata/agent-kit'. Got: {list(deps.keys())}"
    )
