import os
import shutil
import subprocess

PROJECT_DIR = "/home/user/tigris-task"
TRIAL_ID_PATH = "/logs/artifacts/trial_id"


def test_tigris_cli_available():
    assert shutil.which("tigris") is not None, (
        "tigris CLI binary not found in PATH; expected '@tigrisdata/cli' to be installed."
    )


def test_node_available():
    assert shutil.which("node") is not None, (
        "node binary not found in PATH; required to run the npm-installed Tigris CLI."
    )


def test_project_dir_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Project directory {PROJECT_DIR} does not exist."
    )


def test_trial_id_file_exists():
    assert os.path.isfile(TRIAL_ID_PATH), (
        f"trial_id file {TRIAL_ID_PATH} is missing; "
        "tasks rely on /logs/artifacts/trial_id to derive unique resource names."
    )
    with open(TRIAL_ID_PATH) as f:
        trial_id = f.read().strip()
    assert trial_id, f"trial_id file {TRIAL_ID_PATH} is empty."


def test_tigris_env_vars_present():
    for var in (
        "TIGRIS_STORAGE_ACCESS_KEY_ID",
        "TIGRIS_STORAGE_SECRET_ACCESS_KEY",
        "TIGRIS_STORAGE_ENDPOINT",
    ):
        assert os.environ.get(var), (
            f"Environment variable {var} must be set for the Tigris CLI to authenticate."
        )
    assert os.environ["TIGRIS_STORAGE_ENDPOINT"].startswith("https://"), (
        "TIGRIS_STORAGE_ENDPOINT must be an https URL (e.g., https://t3.storage.dev)."
    )


def test_tigris_cli_can_list_buckets():
    """Sanity check that the credentials in env successfully authenticate the CLI."""
    result = subprocess.run(
        ["tigris", "buckets", "list", "--format", "json"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        "Pre-task sanity check failed: `tigris buckets list --format json` exited "
        f"with code {result.returncode}.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
