# syntax=docker/dockerfile:1.7
FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm i -g @tigrisdata/agent-kit @tigrisdata/cli && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="any-task-builder"
LABEL Description="Tigris Agent Kit task: enable snapshots on a pre-existing 'agent-corpus' bucket via the Tigris CLI."

# Create the project directory and place the runtime bucket-setup script.
# The bucket itself is created at task run-time by setup.sh (NOT at build time)
# because Tigris credentials are injected from task.toml at run-time, not build time.
RUN <<DOCKER_EOF
set -e
mkdir -p /home/user/snapshot-enable
cat >/home/user/snapshot-enable/setup.sh <<'SETUP_EOF'
#!/bin/bash
# Bootstrap script: prepares the pre-existing 'agent-corpus' bucket (WITHOUT
# snapshots enabled) so the task agent can enable snapshots on it via the CLI.
#
# This script is executed by Harbor's bootstrap process at task run-time.
# It relies on the TIGRIS_STORAGE_ACCESS_KEY_ID and TIGRIS_STORAGE_SECRET_ACCESS_KEY
# environment variables being injected from task.toml.
set -u

BUCKET_NAME="agent-corpus"

if [ -z "${TIGRIS_STORAGE_ACCESS_KEY_ID:-}" ] || [ -z "${TIGRIS_STORAGE_SECRET_ACCESS_KEY:-}" ]; then
    echo "ERROR: TIGRIS_STORAGE_ACCESS_KEY_ID / TIGRIS_STORAGE_SECRET_ACCESS_KEY must be set." >&2
    exit 1
fi

# Configure the Tigris CLI so subsequent commands authenticate.
tigris configure \
    --access-key "$TIGRIS_STORAGE_ACCESS_KEY_ID" \
    --access-secret "$TIGRIS_STORAGE_SECRET_ACCESS_KEY"

# If the bucket already exists from a previous run with snapshots enabled,
# delete it first so the task always starts from a snapshot-DISABLED state.
if tigris buckets get "$BUCKET_NAME" >/tmp/bucket_get.out 2>&1; then
    if grep -qiE 'snapshot[s]?[^A-Za-z0-9]*(enabled|: *true|= *true)' /tmp/bucket_get.out; then
        echo "Bucket '$BUCKET_NAME' already exists with snapshots enabled. Recreating without snapshots."
        tigris buckets delete "$BUCKET_NAME" --force 2>/dev/null || \
        tigris buckets delete "$BUCKET_NAME" -y 2>/dev/null || \
        tigris buckets delete "$BUCKET_NAME" || true
    else
        echo "Bucket '$BUCKET_NAME' already exists without snapshots. Leaving as-is."
        exit 0
    fi
fi

# Create the bucket WITHOUT snapshots enabled. This is the pre-task initial state.
tigris buckets create "$BUCKET_NAME"

# Sanity-check the bucket exists.
tigris buckets get "$BUCKET_NAME"
SETUP_EOF
chmod +x /home/user/snapshot-enable/setup.sh
DOCKER_EOF

# Container contents:
#   - Ubuntu 24.04 base
#   - System packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash gnupg
#   - Node.js v24 (via NodeSource)
#   - Global npm packages: @tigrisdata/agent-kit, @tigrisdata/cli (provides the `tigris` binary)
#   - /home/user/snapshot-enable        — project directory
#   - /home/user/snapshot-enable/setup.sh — run-time bootstrap that
#       (1) authenticates the Tigris CLI from env vars, and
#       (2) creates the 'agent-corpus' bucket WITHOUT snapshots enabled.

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
