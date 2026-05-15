import json
import os
import shutil
import socket
import subprocess
import time

import pytest

PROJECT_DIR = "/home/user/tigris-task"
PACKAGE_JSON = os.path.join(PROJECT_DIR, "package.json")
NODE_MODULES = os.path.join(PROJECT_DIR, "node_modules")
TIGRIS_SDK_DIR = os.path.join(NODE_MODULES, "@tigrisdata", "storage")
AGENT_KIT_DIR = os.path.join(NODE_MODULES, "@tigrisdata", "agent-kit")
TSX_BIN = os.path.join(NODE_MODULES, ".bin", "tsx")

RECEIVED_JSONL = os.path.join(PROJECT_DIR, "received.jsonl")
TUNNEL_URL_FILE = os.path.join(PROJECT_DIR, "tunnel.url")
RECEIVER_PORT = 8088


def _wait_for_port(port, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            try:
                if sock.connect_ex(("127.0.0.1", port)) == 0:
                    return True
            except OSError:
                pass
        time.sleep(1)
    return False


def _wait_for_file(path, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    if handle.read().strip():
                        return True
            except OSError:
                pass
        time.sleep(2)
    return False


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


def test_cloudflared_binary_available():
    assert shutil.which("cloudflared") is not None, (
        "cloudflared binary not found in PATH; the entrypoint needs it to expose the local receiver."
    )


def test_project_directory_exists():
    assert os.path.isdir(PROJECT_DIR), (
        f"Expected project directory {PROJECT_DIR} to exist."
    )


def test_package_json_exists_with_required_deps():
    assert os.path.isfile(PACKAGE_JSON), (
        f"Expected {PACKAGE_JSON} to exist with @tigrisdata/storage, @tigrisdata/agent-kit, and tsx dependencies."
    )
    with open(PACKAGE_JSON, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    deps = {}
    deps.update(manifest.get("dependencies", {}) or {})
    deps.update(manifest.get("devDependencies", {}) or {})
    for required in ("@tigrisdata/storage", "@tigrisdata/agent-kit", "tsx"):
        assert required in deps, (
            f"package.json must declare {required} as a dependency."
        )


def test_node_modules_installed():
    assert os.path.isdir(NODE_MODULES), (
        f"Expected {NODE_MODULES} to exist (run `npm install` during image build)."
    )
    assert os.path.isdir(TIGRIS_SDK_DIR), (
        f"Expected @tigrisdata/storage to be installed at {TIGRIS_SDK_DIR}."
    )
    assert os.path.isdir(AGENT_KIT_DIR), (
        f"Expected @tigrisdata/agent-kit to be installed at {AGENT_KIT_DIR}."
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


def test_receiver_is_listening_on_port_8088():
    assert _wait_for_port(RECEIVER_PORT, timeout=30), (
        f"Expected the entrypoint-started HTTP receiver to be listening on port {RECEIVER_PORT}."
    )


def test_received_jsonl_exists_and_is_empty():
    assert os.path.isfile(RECEIVED_JSONL), (
        f"Expected {RECEIVED_JSONL} to be pre-created (empty) by the entrypoint."
    )
    with open(RECEIVED_JSONL, "r", encoding="utf-8") as handle:
        content = handle.read()
    assert content.strip() == "", (
        f"Expected {RECEIVED_JSONL} to be empty before the agent runs; got: {content!r}"
    )


def test_tunnel_url_file_eventually_populated():
    # cloudflared quick-tunnel can take up to ~90s to publish a URL.
    assert _wait_for_file(TUNNEL_URL_FILE, timeout=120), (
        f"Expected {TUNNEL_URL_FILE} to be populated by the entrypoint with a public tunnel URL."
    )
    with open(TUNNEL_URL_FILE, "r", encoding="utf-8") as handle:
        url = handle.read().strip()
    assert url.startswith("https://"), (
        f"Expected tunnel URL to be an https:// URL, got: {url!r}"
    )
    assert "trycloudflare.com" in url, (
        f"Expected a cloudflare quick-tunnel URL (containing 'trycloudflare.com'), got: {url!r}"
    )


def test_run_ts_not_created_yet():
    # The agent is the one that must create run.ts. It should not exist yet.
    assert not os.path.exists(os.path.join(PROJECT_DIR, "run.ts")), (
        "run.ts must not exist before the agent writes it."
    )
    assert not os.path.exists(os.path.join(PROJECT_DIR, "run.log")), (
        "run.log must not exist before the agent writes it."
    )
