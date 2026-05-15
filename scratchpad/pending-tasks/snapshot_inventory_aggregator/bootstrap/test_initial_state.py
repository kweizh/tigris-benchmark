import json
import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/inv"
PACKAGE_JSON = os.path.join(PROJECT_DIR, "package.json")
NODE_MODULES = os.path.join(PROJECT_DIR, "node_modules")
SETUP_SCRIPT = os.path.join(PROJECT_DIR, "setup.sh")
INDEX_JS = os.path.join(PROJECT_DIR, "index.js")
INVENTORY_FILE = os.path.join(PROJECT_DIR, "inventory.json")


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


def test_setup_script_exists():
    assert os.path.isfile(SETUP_SCRIPT), (
        f"Setup script {SETUP_SCRIPT} does not exist. The container must "
        "ship the setup script that prepares the buckets at task start."
    )


def test_setup_script_is_executable():
    assert os.access(SETUP_SCRIPT, os.X_OK), (
        f"Setup script {SETUP_SCRIPT} is not executable."
    )


def test_setup_script_references_required_buckets():
    """The setup script must mention every bucket it is supposed to provision
    so that running it produces the expected starting state."""
    with open(SETUP_SCRIPT) as f:
        content = f.read()
    for bucket in [
        "inv-bench-a",
        "inv-bench-b",
        "inv-bench-c",
        "inv-other-x",
        "inv-other-y",
        "inv-other-z",
    ]:
        assert bucket in content, (
            f"setup.sh must reference the bucket '{bucket}' so that "
            "the initial state can be provisioned."
        )
    assert "tigris" in content, (
        "setup.sh must invoke the tigris CLI to prepare the buckets."
    )
    assert "snapshots take" in content, (
        "setup.sh must call 'tigris snapshots take' to pre-populate snapshots."
    )


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
