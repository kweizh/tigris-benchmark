FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="any-task-builder"
LABEL Description="Tigris Agent Kit webhook_secret_signed_coordination task: Node.js v24 with a pre-initialized /home/user/signed-coord project containing @tigrisdata/agent-kit, @tigrisdata/cli, tsx, and typescript installed locally, plus a setup.sh that provisions the analytics-out bucket and writes expected_token.txt at container start."

# Pre-create the project directory with package.json, tsconfig.json, and a
# local node_modules containing the required packages. The user must author
# /home/user/signed-coord/index.ts themselves.
RUN mkdir -p /home/user/signed-coord && \
    cd /home/user/signed-coord && \
    cat >package.json <<'EOF'
{
  "name": "signed-coord",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "dependencies": {
    "@tigrisdata/agent-kit": "^0.1.0",
    "@tigrisdata/cli": "^1.0.0",
    "tsx": "^4.19.0",
    "typescript": "^5.6.0"
  }
}
EOF

RUN cd /home/user/signed-coord && \
    cat >tsconfig.json <<'EOF'
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "Bundler",
    "esModuleInterop": true,
    "strict": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "allowSyntheticDefaultImports": true,
    "forceConsistentCasingInFileNames": true,
    "outDir": "dist"
  },
  "include": ["*.ts"]
}
EOF

# Setup script runs automatically at container start (via the CMD wrapper
# below) AFTER the orchestrator has injected env vars into the container.
# It (re-)creates the source bucket `analytics-out` with snapshots enabled
# via the Tigris CLI, then writes the verbatim value of WEBHOOK_SECRET to
# /home/user/signed-coord/expected_token.txt so the agent can verify the
# secret was injected through the environment. It is idempotent so it can
# safely run on retries.
RUN cat >/home/user/signed-coord/setup.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/user/signed-coord"
BUCKET_NAME="analytics-out"
EXPECTED_TOKEN_FILE="${PROJECT_DIR}/expected_token.txt"

if [ -x "/usr/local/bin/tigris" ]; then
  TIGRIS_BIN="/usr/local/bin/tigris"
elif command -v tigris >/dev/null 2>&1; then
  TIGRIS_BIN="$(command -v tigris)"
elif [ -x "${PROJECT_DIR}/node_modules/.bin/tigris" ]; then
  TIGRIS_BIN="${PROJECT_DIR}/node_modules/.bin/tigris"
else
  echo "Tigris CLI not found." >&2
  exit 1
fi

if [ -z "${TIGRIS_STORAGE_ACCESS_KEY_ID:-}" ] || [ -z "${TIGRIS_STORAGE_SECRET_ACCESS_KEY:-}" ]; then
  echo "TIGRIS_STORAGE_ACCESS_KEY_ID and TIGRIS_STORAGE_SECRET_ACCESS_KEY must be set." >&2
  exit 1
fi

if [ -z "${WEBHOOK_SECRET:-}" ]; then
  echo "WEBHOOK_SECRET must be set in the container environment." >&2
  exit 1
fi

export AWS_ACCESS_KEY_ID="${TIGRIS_STORAGE_ACCESS_KEY_ID}"
export AWS_SECRET_ACCESS_KEY="${TIGRIS_STORAGE_SECRET_ACCESS_KEY}"
export AWS_REGION="auto"

# Best-effort: nuke any prior bucket so the task starts clean (snapshots
# enabled). Reset any prior notification config so the verifier observes
# only what the agent creates.
"${TIGRIS_BIN}" buckets set-notifications "${BUCKET_NAME}" --reset >/dev/null 2>&1 || true
"${TIGRIS_BIN}" buckets delete "${BUCKET_NAME}" --force >/dev/null 2>&1 || true

"${TIGRIS_BIN}" buckets create "${BUCKET_NAME}" --enable-snapshots

# Write the canonical secret value (i.e. the orchestrator-injected
# WEBHOOK_SECRET) so the agent can verify the env var matches.
printf '%s' "${WEBHOOK_SECRET}" >"${EXPECTED_TOKEN_FILE}"
chmod 0644 "${EXPECTED_TOKEN_FILE}"

echo "setup.sh: created bucket ${BUCKET_NAME} (snapshots enabled) and wrote ${EXPECTED_TOKEN_FILE}."
EOF

RUN chmod +x /home/user/signed-coord/setup.sh

RUN cd /home/user/signed-coord && npm install --no-audit --no-fund && \
    ln -sf /home/user/signed-coord/node_modules/.bin/tigris /usr/local/bin/tigris

# Container contents:
#   - Ubuntu 24.04 base with curl, wget, ca-certificates, git, python3,
#     python3-pip, python3-pytest, bash.
#   - Node.js v24 installed via NodeSource.
#   - /home/user/signed-coord — TypeScript project pre-initialized with
#     package.json, tsconfig.json, and node_modules containing
#     @tigrisdata/agent-kit, @tigrisdata/cli, tsx, and typescript.
#     index.ts is intentionally absent — the user must create it.
#   - /home/user/signed-coord/setup.sh — executable script that provisions
#     the `analytics-out` bucket (snapshots enabled) and writes
#     expected_token.txt at container start. It is invoked automatically
#     by the CMD wrapper below so that expected_token.txt exists by the
#     time the initial-state tests run.
#   - tigris CLI symlinked to /usr/local/bin/tigris.

# The CMD wrapper runs setup.sh once at container start (so the
# orchestrator-injected env vars are available) and then sleeps so the
# container stays up for the agent and verifier. Errors from setup.sh
# are logged to /home/user/signed-coord/setup.log; subsequent retries
# remain idempotent because setup.sh resets the bucket before creating
# it again.
CMD ["/bin/bash", "-c", "/home/user/signed-coord/setup.sh >/home/user/signed-coord/setup.log 2>&1 || true; trap : TERM INT; sleep infinity & wait"]
