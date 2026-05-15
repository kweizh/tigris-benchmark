import json
import os
import shutil
import subprocess

import pytest

PROJECT_DIR = "/home/user/tigris-task"
PACKAGE_JSON = os.path.join(PROJECT_DIR, "package.json")
NODE_MODULES = os.path.join(PROJECT_DIR, "node_modules")
AGENT_KIT_DIR = os.path.join(NODE_MODULES, "@tigrisdata", "agent-kit")
STORAGE_SDK_DIR = os.path.join(NODE_MODULES, "@tigrisdata", "storage")
TSX_LOCAL_BIN = os.path.join(NODE_MODULES, ".bin", "tsx")
TRIAL_ID_PATH = "/logs/artifacts/trial_id"


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
        "tsx binary not found in PATH; it must be installed globally so the "
        "agent can run TypeScript directly with `tsx run.ts`."
    )


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected project directory {PROJECT_DIR} to exist."
    )


def test_package_json_declares_required_deps():
    assert os.path.isfile(PACKAGE_JSON), (
        f"Expected {PACKAGE_JSON} to exist with the Tigris dependencies pre-declared."
    )
    with open(PACKAGE_JSON, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    deps = {}
    deps.update(manifest.get("dependencies", {}) or {})
    deps.update(manifest.get("devDependencies", {}) or {})
    for required in ("@tigrisdata/agent-kit", "@tigrisdata/storage", "tsx"):
        assert required in deps, (
            f"package.json must declare {required!r} as a dependency. Got deps: {deps}"
        )


def test_node_modules_installed():
    assert os.path.isdir(NODE_MODULES), (
        f"Expected {NODE_MODULES} to exist (run `npm install` during image build)."
    )
    assert os.path.isdir(AGENT_KIT_DIR), (
        f"Expected @tigrisdata/agent-kit to be installed at {AGENT_KIT_DIR}."
    )
    assert os.path.isdir(STORAGE_SDK_DIR), (
        f"Expected @tigrisdata/storage to be installed at {STORAGE_SDK_DIR}."
    )
    assert os.path.isfile(TSX_LOCAL_BIN) or os.path.islink(TSX_LOCAL_BIN), (
        f"Expected local tsx binary at {TSX_LOCAL_BIN}."
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
    assert os.path.isfile(TRIAL_ID_PATH), (
        f"Expected trial id artifact at {TRIAL_ID_PATH} (Harbor must mount it before the agent runs)."
    )
    with open(TRIAL_ID_PATH, "r", encoding="utf-8") as handle:
        content = handle.read().strip()
    assert content, f"{TRIAL_ID_PATH} must contain a non-empty trial id."


def test_source_bucket_seeded_with_dataset():
    """The container entrypoint script must have created the source bucket
    `harbor-source-${trial_id}` with snapshots enabled and uploaded
    `seed/dataset.txt` containing the bytes `initial` BEFORE the agent runs.
    Verify this end-to-end via the Tigris CLI."""
    with open(TRIAL_ID_PATH, "r", encoding="utf-8") as handle:
        trial_id = handle.read().strip()
    bucket = f"harbor-source-{trial_id}"
    import re
    bucket = re.sub(r"[^a-z0-9.-]", "-", bucket.lower())

    env = os.environ.copy()
    env["AWS_ACCESS_KEY_ID"] = os.environ["TIGRIS_STORAGE_ACCESS_KEY_ID"]
    env["AWS_SECRET_ACCESS_KEY"] = os.environ["TIGRIS_STORAGE_SECRET_ACCESS_KEY"]
    env.setdefault("AWS_REGION", "auto")

    ls = subprocess.run(
        ["tigris", "ls", f"t3://{bucket}/seed/dataset.txt"],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert ls.returncode == 0, (
        f"Expected source bucket {bucket} to contain seed/dataset.txt before the agent starts. "
        f"`tigris ls` failed: stdout={ls.stdout!r}, stderr={ls.stderr!r}"
    )
    assert "seed/dataset.txt" in ls.stdout, (
        f"Expected `tigris ls t3://{bucket}/seed/dataset.txt` output to reference the seed object. "
        f"Got: {ls.stdout!r}"
    )


def test_run_ts_not_created_yet():
    # The agent is the one who must create run.ts.
    assert not os.path.exists(os.path.join(PROJECT_DIR, "run.ts")), (
        "run.ts must not exist before the agent writes it."
    )
