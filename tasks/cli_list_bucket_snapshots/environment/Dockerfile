FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash jq && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g @tigrisdata/cli@2.18.0 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="any-task-builder"
LABEL Description="Tigris CLI snapshot-listing task: Node.js v24, the @tigrisdata/cli installed globally, a pre-initialized /home/user/snapshot-list project with @tigrisdata/agent-kit installed locally, and a setup.sh script that prepares the snapshot bucket at task start."

# Pre-create the project directory with package.json and a project-local
# node_modules containing @tigrisdata/agent-kit (the agent-kit SDK is required
# by the task description even though the user does not import it directly —
# it is the library the broader benchmark is exercising). The user creates
# /home/user/snapshot-list/snapshots.txt themselves.
RUN mkdir -p /home/user/snapshot-list && \
    cd /home/user/snapshot-list && \
    cat >package.json <<'EOF'
{
  "name": "snapshot-list",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "dependencies": {
    "@tigrisdata/agent-kit": "^0.1.0"
  }
}
EOF

RUN cd /home/user/snapshot-list && npm install --no-audit --no-fund

# Write the setup.sh helper that prepares the bucket at task start. It must
# be executed at runtime (not at build time) because the admin credentials
# are only available in the running container.
RUN cat >/home/user/snapshot-list/setup.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f /logs/artifacts/trial_id ]]; then
  echo "ERROR: /logs/artifacts/trial_id not found." >&2
  exit 1
fi

TRIAL_ID=$(cat /logs/artifacts/trial_id | tr -d '[:space:]')
BUCKET="harbor-history-${TRIAL_ID}"
BUCKET=$(echo "$BUCKET" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9.-]/-/g')

ENDPOINT="${TIGRIS_STORAGE_ENDPOINT:-https://t3.storage.dev}"

if [[ -z "${TIGRIS_STORAGE_ACCESS_KEY_ID:-}" || -z "${TIGRIS_STORAGE_SECRET_ACCESS_KEY:-}" ]]; then
  echo "ERROR: TIGRIS_STORAGE_ACCESS_KEY_ID and TIGRIS_STORAGE_SECRET_ACCESS_KEY must be set." >&2
  exit 1
fi

echo "[setup] Configuring tigris CLI..."
tigris configure \
  --access-key "${TIGRIS_STORAGE_ACCESS_KEY_ID}" \
  --access-secret "${TIGRIS_STORAGE_SECRET_ACCESS_KEY}" \
  --endpoint "${ENDPOINT}"

echo "[setup] Creating bucket ${BUCKET} with snapshots enabled..."
tigris buckets create "${BUCKET}" --enable-snapshots

echo "[setup] Taking snapshots (sleeping between to guarantee distinct versions)..."
tigris snapshots take "${BUCKET}" snapshot-alpha
sleep 1
tigris snapshots take "${BUCKET}" snapshot-beta
sleep 1
tigris snapshots take "${BUCKET}" snapshot-gamma

echo "[setup] Done. Snapshots currently present:"
tigris snapshots list "${BUCKET}" --format json
EOF

RUN chmod +x /home/user/snapshot-list/setup.sh

# Container contents:
#   - Ubuntu 24.04 base with curl, wget, ca-certificates, git, python3,
#     python3-pip, python3-pytest, bash, and jq (used for parsing CLI JSON).
#   - Node.js v24 installed via NodeSource.
#   - @tigrisdata/cli installed globally so `tigris` is on PATH.
#   - /home/user/snapshot-list — pre-initialized project with package.json
#     and node_modules containing @tigrisdata/agent-kit, plus an executable
#     setup.sh that prepares the snapshot bucket and its snapshots at
#     task start (the build does not have Tigris credentials).
#   - snapshots.txt and output.log are intentionally absent — the user
#     creates them when completing the task.

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
