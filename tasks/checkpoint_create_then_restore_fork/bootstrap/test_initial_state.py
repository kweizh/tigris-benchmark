import json
import os
import shutil
import subprocess
import time

import pytest

PROJECT_DIR = "/home/user/tigris-task"
PACKAGE_JSON = os.path.join(PROJECT_DIR, "package.json")
NODE_MODULES = os.path.join(PROJECT_DIR, "node_modules")
TIGRIS_AGENT_KIT_DIR = os.path.join(NODE_MODULES, "@tigrisdata", "agent-kit")
TIGRIS_STORAGE_DIR = os.path.join(NODE_MODULES, "@tigrisdata", "storage")
TSX_BIN = os.path.join(NODE_MODULES, ".bin", "tsx")

TRIAL_ID_PATH = "/logs/artifacts/trial_id"
SEED_DONE_SENTINEL = "/tmp/tigris-seed.done"
SEED_LOG = "/var/log/tigris-seed.log"


def _read_trial_id():
    assert os.path.isfile(TRIAL_ID_PATH), (
        f"Expected trial id file at {TRIAL_ID_PATH} to exist before the task starts."
    )
    with open(TRIAL_ID_PATH, "r", encoding="utf-8") as handle:
        trial_id = handle.read().strip()
    assert trial_id, f"{TRIAL_ID_PATH} must contain a non-empty trial id."
    return trial_id


def _wait_for_seed_sentinel(timeout_sec=180):
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if os.path.exists(SEED_DONE_SENTINEL):
            return
        time.sleep(2)
    log_tail = ""
    if os.path.isfile(SEED_LOG):
        try:
            with open(SEED_LOG, "r", encoding="utf-8") as handle:
                log_tail = handle.read()[-4000:]
        except OSError:
            log_tail = "<unable to read seed log>"
    pytest.fail(
        f"Entrypoint seed sentinel {SEED_DONE_SENTINEL} did not appear within "
        f"{timeout_sec}s. Seed log tail:\n{log_tail}"
    )


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
        "agent can run TypeScript directly."
    )


def test_tigris_cli_available():
    # The CLI is used by the entrypoint script to seed the base bucket.
    assert shutil.which("tigris") is not None, (
        "tigris CLI binary not found in PATH; the entrypoint seed script needs it."
    )


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected project directory {PROJECT_DIR} to exist."
    )


def test_package_json_exists_with_required_deps():
    assert os.path.isfile(PACKAGE_JSON), (
        f"Expected {PACKAGE_JSON} to exist with @tigrisdata/agent-kit, "
        "@tigrisdata/storage, and tsx dependencies."
    )
    with open(PACKAGE_JSON, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    deps = {}
    deps.update(manifest.get("dependencies", {}) or {})
    deps.update(manifest.get("devDependencies", {}) or {})
    for required in ("@tigrisdata/agent-kit", "@tigrisdata/storage", "tsx"):
        assert required in deps, (
            f"package.json must declare {required!r} as a dependency."
        )


def test_node_modules_installed():
    assert os.path.isdir(NODE_MODULES), (
        f"Expected {NODE_MODULES} to exist (run `npm install` during image build)."
    )
    assert os.path.isdir(TIGRIS_AGENT_KIT_DIR), (
        f"Expected @tigrisdata/agent-kit to be installed at {TIGRIS_AGENT_KIT_DIR}."
    )
    assert os.path.isdir(TIGRIS_STORAGE_DIR), (
        f"Expected @tigrisdata/storage to be installed at {TIGRIS_STORAGE_DIR}."
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
            f"Environment variable {var} must be set so the SDK can "
            "authenticate against Tigris."
        )


def test_trial_id_artifact_present():
    trial_id = _read_trial_id()
    assert trial_id, f"{TRIAL_ID_PATH} must contain a non-empty trial id."


def test_run_ts_not_created_yet():
    # The agent is the one that must create run.ts. It should not exist yet.
    assert not os.path.exists(os.path.join(PROJECT_DIR, "run.ts")), (
        "run.ts must not exist before the agent writes it."
    )


def test_entrypoint_seed_completed():
    """The container entrypoint must have created the base bucket and uploaded
    the two pre-seeded `data/v*.txt` objects before the agent runs."""
    _wait_for_seed_sentinel()
    assert os.path.isfile(SEED_DONE_SENTINEL), (
        f"Entrypoint sentinel {SEED_DONE_SENTINEL} missing after wait."
    )


def _tigris_env():
    env = os.environ.copy()
    env["AWS_ACCESS_KEY_ID"] = os.environ["TIGRIS_STORAGE_ACCESS_KEY_ID"]
    env["AWS_SECRET_ACCESS_KEY"] = os.environ["TIGRIS_STORAGE_SECRET_ACCESS_KEY"]
    env.setdefault("AWS_REGION", "auto")
    return env


def test_seeded_base_bucket_exists():
    """The pre-seeded base bucket must be visible to the Tigris CLI."""
    _wait_for_seed_sentinel()
    bucket = f"harbor-base-{_read_trial_id()}"
    import re
    bucket = re.sub(r"[^a-z0-9.-]", "-", bucket.lower())
    result = subprocess.run(
        ["tigris", "buckets", "list", "--format", "json"],
        capture_output=True,
        text=True,
        env=_tigris_env(),
        cwd=PROJECT_DIR,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"'tigris buckets list --format json' failed (rc={result.returncode}): "
        f"stderr={result.stderr!r}"
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"'tigris buckets list --format json' did not return valid JSON: "
            f"{exc}. stdout={result.stdout!r}"
        )

    def _collect_names(node):
        names = []
        if isinstance(node, list):
            for item in node:
                names.extend(_collect_names(item))
        elif isinstance(node, dict):
            for key, value in node.items():
                if key.lower() in {"name", "bucket", "bucketname"} and isinstance(
                    value, str
                ):
                    names.append(value)
                else:
                    names.extend(_collect_names(value))
        return names

    names = _collect_names(payload)
    assert bucket in names, (
        f"Expected pre-seeded bucket {bucket!r} to appear in `tigris buckets list`, "
        f"but it was not found. Collected names: {names}"
    )


def test_seeded_base_bucket_has_snapshots_enabled():
    """Snapshots must be enabled on the base bucket — checkpoints require it."""
    _wait_for_seed_sentinel()
    bucket = f"harbor-base-{_read_trial_id()}"
    import re
    bucket = re.sub(r"[^a-z0-9.-]", "-", bucket.lower())
    result = subprocess.run(
        ["tigris", "snapshots", "list", bucket],
        capture_output=True,
        text=True,
        env=_tigris_env(),
        cwd=PROJECT_DIR,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"Expected `tigris snapshots list {bucket}` to succeed (indicating "
        "snapshots are enabled), but it exited with "
        f"code {result.returncode}.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_seeded_base_bucket_has_two_objects():
    """The pre-seeded base bucket must contain exactly `data/v1.txt` and `data/v2.txt`."""
    _wait_for_seed_sentinel()
    bucket = f"harbor-base-{_read_trial_id()}"
    import re
    bucket = re.sub(r"[^a-z0-9.-]", "-", bucket.lower())
    result = subprocess.run(
        ["tigris", "ls", f"t3://{bucket}/data/"],
        capture_output=True,
        text=True,
        env=_tigris_env(),
        cwd=PROJECT_DIR,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"'tigris ls t3://{bucket}/data/' failed (rc={result.returncode}): "
        f"stderr={result.stderr!r} stdout={result.stdout!r}"
    )
    assert "v1.txt" in result.stdout, (
        f"Expected pre-seeded 'data/v1.txt' to be present under t3://{bucket}/data/, "
        f"but it was missing. Listing output:\n{result.stdout}"
    )
    assert "v2.txt" in result.stdout, (
        f"Expected pre-seeded 'data/v2.txt' to be present under t3://{bucket}/data/, "
        f"but it was missing. Listing output:\n{result.stdout}"
    )
