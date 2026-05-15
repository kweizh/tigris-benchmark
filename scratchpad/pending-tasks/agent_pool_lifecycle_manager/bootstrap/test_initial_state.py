import json
import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/pool"


def test_node_binary_available():
    assert shutil.which("node") is not None, "node binary not found in PATH."


def test_node_version_is_v24():
    result = subprocess.run(
        ["node", "--version"], capture_output=True, text=True
    )
    assert result.returncode == 0, f"`node --version` failed: {result.stderr}"
    version = result.stdout.strip()
    assert version.startswith("v24."), (
        f"Expected Node.js v24.x, got: {version!r}"
    )


def test_npm_binary_available():
    assert shutil.which("npm") is not None, "npm binary not found in PATH."


def test_npx_binary_available():
    assert shutil.which("npx") is not None, "npx binary not found in PATH."


def test_tigris_cli_available():
    assert shutil.which("tigris") is not None, (
        "tigris CLI binary not found in PATH; @tigrisdata/cli must be installed globally."
    )


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} does not exist."
    )


def test_package_json_exists():
    pkg_path = os.path.join(PROJECT_DIR, "package.json")
    assert os.path.isfile(pkg_path), (
        f"Expected package.json at {pkg_path}."
    )


def test_tsconfig_json_exists():
    cfg_path = os.path.join(PROJECT_DIR, "tsconfig.json")
    assert os.path.isfile(cfg_path), (
        f"Expected tsconfig.json at {cfg_path}."
    )


def test_agent_kit_installed_locally():
    pkg_path = os.path.join(
        PROJECT_DIR, "node_modules", "@tigrisdata", "agent-kit", "package.json"
    )
    assert os.path.isfile(pkg_path), (
        f"@tigrisdata/agent-kit is not installed at {pkg_path}."
    )


def test_aws_s3_client_installed_locally():
    pkg_path = os.path.join(
        PROJECT_DIR, "node_modules", "@aws-sdk", "client-s3", "package.json"
    )
    assert os.path.isfile(pkg_path), (
        f"@aws-sdk/client-s3 is not installed at {pkg_path}."
    )


def test_tsx_installed_locally():
    tsx_bin = os.path.join(PROJECT_DIR, "node_modules", ".bin", "tsx")
    assert os.path.isfile(tsx_bin) or os.path.islink(tsx_bin), (
        f"tsx binary not found at {tsx_bin}; it must be installed locally for `npx tsx`."
    )


def test_typescript_installed_locally():
    tsc_bin = os.path.join(PROJECT_DIR, "node_modules", ".bin", "tsc")
    assert os.path.isfile(tsc_bin) or os.path.islink(tsc_bin), (
        f"typescript (tsc) not found at {tsc_bin}."
    )


def test_package_json_declares_required_dependencies():
    pkg_path = os.path.join(PROJECT_DIR, "package.json")
    with open(pkg_path) as f:
        data = json.load(f)
    deps = {}
    deps.update(data.get("dependencies", {}))
    deps.update(data.get("devDependencies", {}))
    assert "@tigrisdata/agent-kit" in deps, (
        "Expected @tigrisdata/agent-kit to be declared in package.json dependencies."
    )
    assert "@aws-sdk/client-s3" in deps, (
        "Expected @aws-sdk/client-s3 to be declared in package.json dependencies."
    )


def test_manager_ts_not_yet_created():
    p = os.path.join(PROJECT_DIR, "manager.ts")
    assert not os.path.exists(p), (
        f"manager.ts should not exist before the task runs (found at {p})."
    )


def test_cli_ts_not_yet_created():
    p = os.path.join(PROJECT_DIR, "cli.ts")
    assert not os.path.exists(p), (
        f"cli.ts should not exist before the task runs (found at {p})."
    )


def test_pool_state_not_yet_created():
    p = os.path.join(PROJECT_DIR, "pool-state.json")
    assert not os.path.exists(p), (
        f"pool-state.json should not exist before the task runs (found at {p})."
    )


def test_scenario_log_not_yet_created():
    p = os.path.join(PROJECT_DIR, "scenario.log")
    assert not os.path.exists(p), (
        f"scenario.log should not exist before the task runs (found at {p})."
    )
