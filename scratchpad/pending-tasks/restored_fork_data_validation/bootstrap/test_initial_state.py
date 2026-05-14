import json
import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/restore-validate"
NODE_MODULES = os.path.join(PROJECT_DIR, "node_modules")
SETUP_SCRIPT = os.path.join(PROJECT_DIR, "setup.sh")


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
    """The Tigris CLI must be reachable from PATH or via node_modules/.bin."""
    if shutil.which("tigris") is not None:
        return
    local_bin = os.path.join(NODE_MODULES, ".bin", "tigris")
    assert os.path.isfile(local_bin), (
        f"Tigris CLI not found in PATH and not at {local_bin}."
    )


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} does not exist."
    )


def test_package_json_exists():
    pkg = os.path.join(PROJECT_DIR, "package.json")
    assert os.path.isfile(pkg), f"package.json not found at {pkg}."


def test_package_json_declares_required_dependencies():
    pkg = os.path.join(PROJECT_DIR, "package.json")
    with open(pkg) as f:
        data = json.load(f)
    deps = {}
    deps.update(data.get("dependencies", {}) or {})
    deps.update(data.get("devDependencies", {}) or {})
    for required in (
        "@tigrisdata/agent-kit",
        "@tigrisdata/cli",
        "@aws-sdk/client-s3",
        "tsx",
    ):
        assert required in deps, (
            f"package.json must declare '{required}' in dependencies "
            f"or devDependencies."
        )


def test_setup_script_exists():
    assert os.path.isfile(SETUP_SCRIPT), (
        f"Setup script {SETUP_SCRIPT} does not exist. The container must "
        "ship the setup script that prepares archive-bucket at task start."
    )


def test_setup_script_is_executable():
    assert os.access(SETUP_SCRIPT, os.X_OK), (
        f"Setup script {SETUP_SCRIPT} is not executable."
    )


def test_setup_script_references_archive_bucket():
    with open(SETUP_SCRIPT) as f:
        content = f.read()
    assert "archive-bucket" in content, (
        "setup.sh must reference the bucket name 'archive-bucket'."
    )
    assert "snapshot_id.txt" in content, (
        "setup.sh must write the snapshot id to 'snapshot_id.txt'."
    )
    assert "expected_sha256.txt" in content, (
        "setup.sh must write the manifest sha256 to 'expected_sha256.txt'."
    )


def test_node_modules_directory_exists():
    assert os.path.isdir(NODE_MODULES), (
        f"node_modules directory not found at {NODE_MODULES}."
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


def test_aws_sdk_s3_installed():
    pkg_dir = os.path.join(NODE_MODULES, "@aws-sdk", "client-s3")
    assert os.path.isdir(pkg_dir), (
        f"@aws-sdk/client-s3 is not installed in {pkg_dir}."
    )


def test_tsx_installed():
    pkg_dir = os.path.join(NODE_MODULES, "tsx")
    assert os.path.isdir(pkg_dir), f"tsx is not installed in {pkg_dir}."


def test_index_ts_does_not_exist_yet():
    index_ts = os.path.join(PROJECT_DIR, "index.ts")
    assert not os.path.exists(index_ts), (
        f"{index_ts} must NOT exist at the start of the task; the user is "
        "expected to create it."
    )


def test_result_json_does_not_exist_yet():
    result_json = os.path.join(PROJECT_DIR, "result.json")
    assert not os.path.exists(result_json), (
        f"{result_json} must NOT exist at the start of the task; it is "
        "produced by the user's run."
    )
