import json
import os
import re
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/inv"
PACKAGE_JSON = os.path.join(PROJECT_DIR, "package.json")
NODE_MODULES = os.path.join(PROJECT_DIR, "node_modules")
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


def test_node_binary_available():
    assert shutil.which("node") is not None, "node binary not found in PATH."


def test_node_major_version_is_24():
    result = subprocess.run(
        ["node", "--version"], capture_output=True, text=True
    )
    assert result.returncode == 0, f"'node --version' failed: {result.stderr}"
    version = result.stdout.strip()
    assert version.startswith("v24."), (
        f"Expected Node.js v24.x, got '{version}'."
    )


def test_npx_binary_available():
    assert shutil.which("npx") is not None, "npx binary not found in PATH."


def test_tigris_cli_available():
    """The Tigris CLI must be reachable from PATH."""
    assert shutil.which("tigris") is not None, (
        "tigris CLI binary not found in PATH. The container must install "
        "@tigrisdata/cli globally."
    )


def test_tigris_cli_runs():
    """tigris --version should succeed even without credentials."""
    result = subprocess.run(
        ["tigris", "--version"], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, (
        f"'tigris --version' failed: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} does not exist."
    )


def test_package_json_exists_and_declares_agent_kit():
    assert os.path.isfile(PACKAGE_JSON), (
        f"package.json not found at {PACKAGE_JSON}."
    )
    with open(PACKAGE_JSON) as f:
        data = json.load(f)
    deps = {}
    deps.update(data.get("dependencies", {}) or {})
    deps.update(data.get("devDependencies", {}) or {})
    assert "@tigrisdata/agent-kit" in deps, (
        "package.json must declare '@tigrisdata/agent-kit' in dependencies "
        "or devDependencies."
    )


def test_node_modules_directory_exists():
    assert os.path.isdir(NODE_MODULES), (
        f"node_modules directory not found at {NODE_MODULES}. "
        "The project must be pre-installed."
    )


def test_agent_kit_installed():
    pkg_dir = os.path.join(NODE_MODULES, "@tigrisdata", "agent-kit")
    assert os.path.isdir(pkg_dir), (
        f"@tigrisdata/agent-kit is not installed in {pkg_dir}."
    )
    pkg_json = os.path.join(pkg_dir, "package.json")
    assert os.path.isfile(pkg_json), (
        f"package.json for @tigrisdata/agent-kit missing at {pkg_json}."
    )


def _tigris_env():
    env = os.environ.copy()
    access = env.get("TIGRIS_STORAGE_ACCESS_KEY_ID", "")
    secret = env.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY", "")
    env["AWS_ACCESS_KEY_ID"] = access
    env["AWS_SECRET_ACCESS_KEY"] = secret
    env["AWS_REGION"] = "auto"
    env["AWS_DEFAULT_REGION"] = "auto"
    return env


def test_pre_create_buckets():
    prefix = _prefix()
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

    all_buckets = [
        f"{prefix}a",
        f"{prefix}b",
        f"{prefix}c",
        f"harbor-other-{_read_trial_id()}-x",
        f"harbor-other-{_read_trial_id()}-y",
        f"harbor-other-{_read_trial_id()}-z",
    ]

    for bucket in all_buckets:
        subprocess.run(["tigris", "buckets", "delete", bucket, "--yes"], capture_output=True, text=True, env=env)

    import time
    time.sleep(3)

    # inv-bench-a (2 snapshots)
    subprocess.run(["tigris", "buckets", "create", f"{prefix}a", "--enable-snapshots"], capture_output=True, text=True, env=env)
    subprocess.run(["tigris", "snapshots", "take", f"{prefix}a", f"{prefix}a-s1"], capture_output=True, text=True, env=env)
    time.sleep(1)
    subprocess.run(["tigris", "snapshots", "take", f"{prefix}a", f"{prefix}a-s2"], capture_output=True, text=True, env=env)
    time.sleep(1)

    # inv-bench-b (1 snapshot)
    subprocess.run(["tigris", "buckets", "create", f"{prefix}b", "--enable-snapshots"], capture_output=True, text=True, env=env)
    subprocess.run(["tigris", "snapshots", "take", f"{prefix}b", f"{prefix}b-s1"], capture_output=True, text=True, env=env)
    time.sleep(1)

    # inv-bench-c (3 snapshots)
    subprocess.run(["tigris", "buckets", "create", f"{prefix}c", "--enable-snapshots"], capture_output=True, text=True, env=env)
    subprocess.run(["tigris", "snapshots", "take", f"{prefix}c", f"{prefix}c-s1"], capture_output=True, text=True, env=env)
    time.sleep(1)
    subprocess.run(["tigris", "snapshots", "take", f"{prefix}c", f"{prefix}c-s2"], capture_output=True, text=True, env=env)
    time.sleep(1)
    subprocess.run(["tigris", "snapshots", "take", f"{prefix}c", f"{prefix}c-s3"], capture_output=True, text=True, env=env)
    time.sleep(1)

    # inv-other-x (2 snapshots)
    x = f"harbor-other-{_read_trial_id()}-x"
    subprocess.run(["tigris", "buckets", "create", x, "--enable-snapshots"], capture_output=True, text=True, env=env)
    subprocess.run(["tigris", "snapshots", "take", x, f"{x}-s1"], capture_output=True, text=True, env=env)
    time.sleep(1)
    subprocess.run(["tigris", "snapshots", "take", x, f"{x}-s2"], capture_output=True, text=True, env=env)
    time.sleep(1)

    # inv-other-y (0 snapshots)
    y = f"harbor-other-{_read_trial_id()}-y"
    subprocess.run(["tigris", "buckets", "create", y], capture_output=True, text=True, env=env)

    # inv-other-z (0 snapshots)
    z = f"harbor-other-{_read_trial_id()}-z"
    subprocess.run(["tigris", "buckets", "create", z], capture_output=True, text=True, env=env)


def test_index_js_does_not_exist_yet():
    assert not os.path.exists(INDEX_JS), (
        f"{INDEX_JS} must NOT exist at the start of the task; the user is "
        "expected to author it."
    )


def test_inventory_file_does_not_exist_yet():
    assert not os.path.exists(INVENTORY_FILE), (
        f"{INVENTORY_FILE} must NOT exist at the start of the task; the "
        "user's script is expected to write it."
    )
