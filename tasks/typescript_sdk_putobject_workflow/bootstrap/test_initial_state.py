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
    path = "/logs/artifacts/trial_id"
    assert os.path.isfile(path), (
        f"Expected trial id artifact at {path} (Harbor must mount it before the agent runs)."
    )
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read().strip()
    assert content, f"{path} must contain a non-empty trial id."


def test_index_ts_not_created_yet():
    # The agent is the one that must create index.ts. It should not exist yet.
    assert not os.path.exists(os.path.join(PROJECT_DIR, "index.ts")), (
        "index.ts must not exist before the agent writes it."
    )
    assert not os.path.exists(os.path.join(PROJECT_DIR, "listing.txt")), (
        "listing.txt must not exist before the agent generates it."
    )
