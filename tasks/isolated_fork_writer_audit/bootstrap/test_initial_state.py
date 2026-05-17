import json
import os
import re
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/isolation"
NODE_MODULES = os.path.join(PROJECT_DIR, "node_modules")
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
    name = f"harbor-isolation-{trial_id}"
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


def test_aws_sdk_s3_installed():
    pkg_dir = os.path.join(NODE_MODULES, "@aws-sdk", "client-s3")
    assert os.path.isdir(pkg_dir), (
        f"@aws-sdk/client-s3 is not installed in {pkg_dir}."
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
        "@aws-sdk/client-s3",
        "tsx",
    ):
        assert required in deps, (
            f"package.json must declare '{required}' in dependencies "
            f"or devDependencies."
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


def test_pre_create_bucket():
    """Pre-create the bucket using the dynamically constructed name with snapshots enabled and seed files."""
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

    import tempfile
    with tempfile.TemporaryDirectory() as seed_dir:
        seed1 = os.path.join(seed_dir, "seed1.txt")
        seed2 = os.path.join(seed_dir, "seed2.txt")
        with open(seed1, "w") as f:
            f.write("gold-source seed object number one.\n")
        with open(seed2, "w") as f:
            f.write("gold-source seed object number two.\n")

        subprocess.run(
            ["tigris", "objects", "upload", seed1, f"{name}/seed1.txt"],
            capture_output=True,
            text=True,
            env=env,
        )
        subprocess.run(
            ["tigris", "objects", "upload", seed2, f"{name}/seed2.txt"],
            capture_output=True,
            text=True,
            env=env,
        )


def test_index_ts_does_not_exist_yet():
    index_ts = os.path.join(PROJECT_DIR, "index.ts")
    assert not os.path.exists(index_ts), (
        f"{index_ts} must NOT exist at the start of the task; the user is "
        f"expected to create it."
    )


def test_audit_json_does_not_exist_yet():
    audit_json = os.path.join(PROJECT_DIR, "audit.json")
    assert not os.path.exists(audit_json), (
        f"{audit_json} must NOT exist at the start of the task; it is "
        f"produced by the user's run."
    )
