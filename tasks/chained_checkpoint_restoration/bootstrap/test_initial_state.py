import json
import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/chained-ckpt"
SETUP_SCRIPT = os.path.join(PROJECT_DIR, "setup.sh")
PACKAGE_JSON = os.path.join(PROJECT_DIR, "package.json")


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


def test_setup_script_exists():
    assert os.path.isfile(SETUP_SCRIPT), (
        f"setup.sh not found at {SETUP_SCRIPT}; the pre-task setup script is missing."
    )
    assert os.access(SETUP_SCRIPT, os.X_OK), (
        f"setup.sh at {SETUP_SCRIPT} must be executable."
    )
