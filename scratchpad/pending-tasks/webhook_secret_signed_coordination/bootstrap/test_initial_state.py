import json
import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/signed-coord"
NODE_MODULES = os.path.join(PROJECT_DIR, "node_modules")
SETUP_SH = os.path.join(PROJECT_DIR, "setup.sh")
EXPECTED_TOKEN_FILE = os.path.join(PROJECT_DIR, "expected_token.txt")


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
    # Tigris CLI is installed locally inside node_modules and may also be
    # exposed on PATH via a symlink. Either is acceptable.
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


def test_tsconfig_json_exists():
    tsc = os.path.join(PROJECT_DIR, "tsconfig.json")
    assert os.path.isfile(tsc), f"tsconfig.json not found at {tsc}."


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


def test_tigris_cli_package_installed():
    pkg_dir = os.path.join(NODE_MODULES, "@tigrisdata", "cli")
    assert os.path.isdir(pkg_dir), (
        f"@tigrisdata/cli is not installed in {pkg_dir}."
    )


def test_tsx_installed():
    pkg_dir = os.path.join(NODE_MODULES, "tsx")
    assert os.path.isdir(pkg_dir), f"tsx is not installed in {pkg_dir}."


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
        "tsx",
    ):
        assert required in deps, (
            f"package.json must declare '{required}' in dependencies "
            f"or devDependencies."
        )


def test_setup_sh_exists_and_is_executable():
    assert os.path.isfile(SETUP_SH), (
        f"Task setup script {SETUP_SH} does not exist."
    )
    assert os.access(SETUP_SH, os.X_OK), (
        f"Task setup script {SETUP_SH} must be executable."
    )


def test_expected_token_file_exists_after_setup():
    """setup.sh runs at container start and writes the canonical secret value
    (the orchestrator-injected WEBHOOK_SECRET) to expected_token.txt. This
    file must therefore be present BEFORE the agent begins work, so the agent
    can validate that its env-var matches the orchestrator's expectation."""
    assert os.path.isfile(EXPECTED_TOKEN_FILE), (
        f"Expected token file {EXPECTED_TOKEN_FILE} does not exist. "
        f"It should have been written by /home/user/signed-coord/setup.sh "
        f"at container start."
    )
    with open(EXPECTED_TOKEN_FILE) as f:
        contents = f.read()
    assert contents.strip(), (
        f"{EXPECTED_TOKEN_FILE} must be non-empty (it holds the canonical "
        f"WEBHOOK_SECRET value)."
    )


def test_index_ts_does_not_exist_yet():
    index_ts = os.path.join(PROJECT_DIR, "index.ts")
    assert not os.path.exists(index_ts), (
        f"{index_ts} must NOT exist at the start of the task; the user is "
        f"expected to create it."
    )


def test_result_json_does_not_exist_yet():
    result_json = os.path.join(PROJECT_DIR, "result.json")
    assert not os.path.exists(result_json), (
        f"{result_json} must NOT exist at the start of the task; it is "
        f"produced by the user's run."
    )
