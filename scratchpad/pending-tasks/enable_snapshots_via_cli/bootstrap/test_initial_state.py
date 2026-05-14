import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/snapshot-enable"
SETUP_SCRIPT = os.path.join(PROJECT_DIR, "setup.sh")


def test_tigris_cli_available():
    """The `tigris` CLI binary must be installed and on PATH."""
    assert shutil.which("tigris") is not None, (
        "Tigris CLI binary `tigris` not found in PATH. "
        "It is required to interact with the Tigris bucket."
    )


def test_node_available():
    """Node.js must be installed to run the Tigris Agent Kit SDK."""
    assert shutil.which("node") is not None, (
        "`node` binary not found in PATH; Node.js v24 is required."
    )


def test_npm_available():
    """npm must be installed to verify globally-installed packages."""
    assert shutil.which("npm") is not None, (
        "`npm` binary not found in PATH; required to manage npm packages."
    )


def test_project_dir_exists():
    """The task's project directory must exist."""
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} does not exist; "
        "it must be created as part of the initial environment."
    )


def test_setup_script_exists():
    """The setup.sh helper script must exist in the project directory."""
    assert os.path.isfile(SETUP_SCRIPT), (
        f"Setup script {SETUP_SCRIPT} does not exist; "
        "it is required to create the pre-existing bucket at task runtime."
    )


def test_setup_script_is_executable():
    """setup.sh must be executable so the bootstrap process can run it."""
    assert os.access(SETUP_SCRIPT, os.X_OK), (
        f"Setup script {SETUP_SCRIPT} is not executable."
    )


def test_agent_kit_sdk_installed_globally():
    """`@tigrisdata/agent-kit` must be installed globally via npm."""
    result = subprocess.run(
        ["npm", "ls", "-g", "--depth=0", "--json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"`npm ls -g --depth=0 --json` failed: {result.stderr}"
    )
    assert "@tigrisdata/agent-kit" in result.stdout, (
        "`@tigrisdata/agent-kit` is not installed globally via npm."
    )


def test_tigris_cli_package_installed_globally():
    """`@tigrisdata/cli` must be installed globally via npm."""
    result = subprocess.run(
        ["npm", "ls", "-g", "--depth=0", "--json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"`npm ls -g --depth=0 --json` failed: {result.stderr}"
    )
    assert "@tigrisdata/cli" in result.stdout, (
        "`@tigrisdata/cli` is not installed globally via npm."
    )


def test_tigris_credentials_env_vars_present():
    """Task environment must expose Tigris credentials as env vars."""
    assert os.environ.get("TIGRIS_STORAGE_ACCESS_KEY_ID"), (
        "TIGRIS_STORAGE_ACCESS_KEY_ID is not set in the task environment."
    )
    assert os.environ.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY"), (
        "TIGRIS_STORAGE_SECRET_ACCESS_KEY is not set in the task environment."
    )
