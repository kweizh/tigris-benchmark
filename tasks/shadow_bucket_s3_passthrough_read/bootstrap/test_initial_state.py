import json
import os
import shutil
import subprocess
import time

import pytest

PROJECT_DIR = "/home/user/tigris-task"
TRIAL_ID_PATH = "/logs/artifacts/trial_id"
SEED_DONE_SENTINEL = "/tmp/tigris-seed.done"
SEED_LOG = "/var/log/tigris-seed.log"
EXPECTED_ORIGIN_OBJECT_KEY = "docs/readme.md"
EXPECTED_ORIGIN_OBJECT_BYTES = b"from origin"


def _tigris_env():
    """Build an env dict that maps Tigris credentials into the AWS-compatible
    variables consumed by the `tigris` CLI and the `aws` CLI."""
    env = os.environ.copy()
    access_key = os.environ.get("TIGRIS_STORAGE_ACCESS_KEY_ID")
    secret_key = os.environ.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY")
    assert access_key, "TIGRIS_STORAGE_ACCESS_KEY_ID is not set in the environment."
    assert secret_key, "TIGRIS_STORAGE_SECRET_ACCESS_KEY is not set in the environment."
    env["AWS_ACCESS_KEY_ID"] = access_key
    env["AWS_SECRET_ACCESS_KEY"] = secret_key
    env.setdefault("AWS_REGION", "auto")
    return env


def _read_trial_id():
    assert os.path.isfile(TRIAL_ID_PATH), (
        f"Expected trial id file at {TRIAL_ID_PATH} to exist before the task starts."
    )
    with open(TRIAL_ID_PATH) as f:
        trial_id = f.read().strip()
    assert trial_id, f"{TRIAL_ID_PATH} must contain a non-empty trial id."
    return trial_id


def _origin_bucket_name():
    name = f"harbor-origin-{_read_trial_id()}"
    import re
    name = re.sub(r"[^a-z0-9.-]", "-", name.lower())
    return name


def _shadow_bucket_name():
    name = f"harbor-shadow-{_read_trial_id()}"
    import re
    name = re.sub(r"[^a-z0-9.-]", "-", name.lower())
    return name


def _wait_for_seed_sentinel(timeout_sec=180):
    """Wait for the entrypoint seed script to finish creating the origin
    bucket and uploading the docs/readme.md object."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if os.path.exists(SEED_DONE_SENTINEL):
            return
        time.sleep(2)
    log_tail = ""
    if os.path.isfile(SEED_LOG):
        try:
            with open(SEED_LOG) as f:
                log_tail = f.read()[-4000:]
        except OSError:
            log_tail = "<unable to read seed log>"
    pytest.fail(
        f"Entrypoint seed sentinel {SEED_DONE_SENTINEL} did not appear within "
        f"{timeout_sec}s. Seed log tail:\n{log_tail}"
    )


def test_tigris_cli_available():
    assert shutil.which("tigris") is not None, (
        "tigris CLI binary not found in PATH. The @tigrisdata/cli npm package "
        "must be installed globally so the `tigris` command is available."
    )


def test_aws_cli_available():
    assert shutil.which("aws") is not None, (
        "aws CLI binary not found in PATH. The awscli package must be "
        "installed so the agent can run `aws s3 cp` against the Tigris endpoint."
    )


def test_node_available():
    assert shutil.which("node") is not None, (
        "node binary not found in PATH. Node.js is required to run the "
        "@tigrisdata/cli npm package."
    )


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected project directory {PROJECT_DIR} to exist before the task starts."
    )


def test_trial_id_file_exists():
    trial_id = _read_trial_id()
    assert trial_id, f"{TRIAL_ID_PATH} must contain a non-empty trial id."


def test_tigris_credentials_env_vars_present():
    assert os.environ.get("TIGRIS_STORAGE_ACCESS_KEY_ID"), (
        "TIGRIS_STORAGE_ACCESS_KEY_ID environment variable must be provided by Harbor."
    )
    assert os.environ.get("TIGRIS_STORAGE_SECRET_ACCESS_KEY"), (
        "TIGRIS_STORAGE_SECRET_ACCESS_KEY environment variable must be provided by Harbor."
    )


def test_local_proxied_md_does_not_yet_exist():
    target = os.path.join(PROJECT_DIR, "proxied.md")
    assert not os.path.exists(target), (
        f"{target} must NOT exist at the start of the task; it is produced by "
        "the agent by downloading the object through the shadow bucket."
    )


def test_entrypoint_seed_completed():
    """The container entrypoint must have created the origin bucket and
    uploaded the `docs/readme.md` object before the agent runs."""
    _wait_for_seed_sentinel()
    assert os.path.isfile(SEED_DONE_SENTINEL), (
        f"Entrypoint sentinel {SEED_DONE_SENTINEL} missing after wait."
    )


def test_origin_bucket_exists_in_tigris():
    """The pre-seeded origin bucket must be visible to the Tigris CLI."""
    _wait_for_seed_sentinel()
    bucket_name = _origin_bucket_name()
    result = subprocess.run(
        ["tigris", "buckets", "list", "--format", "json"],
        capture_output=True,
        text=True,
        env=_tigris_env(),
        cwd=PROJECT_DIR,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"'tigris buckets list --format json' failed with returncode "
        f"{result.returncode}. stderr={result.stderr!r} stdout={result.stdout!r}"
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"'tigris buckets list --format json' did not return valid JSON: "
            f"{exc}. stdout={result.stdout!r}"
        )
    if isinstance(payload, dict):
        buckets = payload.get("items", []) or payload.get("buckets", []) or []
    else:
        buckets = payload
    names = [b.get("name") for b in buckets if isinstance(b, dict)]
    assert bucket_name in names, (
        f"Expected pre-seeded origin bucket {bucket_name!r} in Tigris, but it "
        f"was not in the bucket list. Got: {names}"
    )


def test_origin_object_exists_in_origin_bucket():
    """The pre-seeded `docs/readme.md` object must already be in the origin bucket."""
    _wait_for_seed_sentinel()
    bucket_name = _origin_bucket_name()
    result = subprocess.run(
        ["tigris", "ls", f"t3://{bucket_name}/docs/"],
        capture_output=True,
        text=True,
        env=_tigris_env(),
        cwd=PROJECT_DIR,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"'tigris ls t3://{bucket_name}/docs/' failed: returncode="
        f"{result.returncode} stderr={result.stderr!r} stdout={result.stdout!r}"
    )
    assert "readme.md" in result.stdout, (
        f"Expected pre-seeded object 'docs/readme.md' to be visible under "
        f"t3://{bucket_name}/docs/, but it was not in the listing. "
        f"Got stdout:\n{result.stdout}"
    )


def test_shadow_bucket_not_yet_created():
    """The shadow bucket MUST NOT exist before the agent runs — the agent is
    expected to create it."""
    _wait_for_seed_sentinel()
    shadow = _shadow_bucket_name()
    result = subprocess.run(
        ["tigris", "buckets", "get", shadow],
        capture_output=True,
        text=True,
        env=_tigris_env(),
        cwd=PROJECT_DIR,
        timeout=60,
    )
    assert result.returncode != 0, (
        f"Shadow bucket {shadow!r} unexpectedly exists at the start of the "
        f"task. 'tigris buckets get' should fail until the agent creates it.\n"
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
