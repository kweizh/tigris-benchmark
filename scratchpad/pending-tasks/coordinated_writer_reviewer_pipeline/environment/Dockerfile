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
LABEL Description="Tigris Agent Kit coordinated_writer_reviewer_pipeline task: Node.js v24 with a pre-initialized /home/user/pipeline project containing @tigrisdata/agent-kit, @tigrisdata/cli, @aws-sdk/client-s3, tsx, and typescript installed locally, plus a setup.sh that provisions the pipeline-out bucket (snapshots enabled) at task start."

# Pre-create the project directory with package.json, tsconfig.json, and a
# local node_modules containing the required packages. The user must author
# /home/user/pipeline/orchestrate.ts themselves.
RUN mkdir -p /home/user/pipeline && \
    cd /home/user/pipeline && \
    cat >package.json <<'EOF'
{
  "name": "pipeline",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "dependencies": {
    "@aws-sdk/client-s3": "^3.658.0",
    "@tigrisdata/agent-kit": "^0.1.0",
    "@tigrisdata/cli": "^1.0.0",
    "tsx": "^4.19.0",
    "typescript": "^5.6.0"
  }
}
EOF

RUN cd /home/user/pipeline && \
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

# Setup script runs at task start (NOT during Docker build). It (re-)creates
# the target bucket `pipeline-out` with snapshots enabled via the Tigris CLI.
# It is idempotent so it can safely run on retries. It uses the admin Tigris
# credentials that the task runtime injects via TIGRIS_STORAGE_ACCESS_KEY_ID
# and TIGRIS_STORAGE_SECRET_ACCESS_KEY.
RUN cat >/home/user/pipeline/setup.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/user/pipeline"
BUCKET_NAME="pipeline-out"

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

export AWS_ACCESS_KEY_ID="${TIGRIS_STORAGE_ACCESS_KEY_ID}"
export AWS_SECRET_ACCESS_KEY="${TIGRIS_STORAGE_SECRET_ACCESS_KEY}"
export AWS_REGION="auto"

# Best-effort: nuke any prior bucket so the task starts clean.
"${TIGRIS_BIN}" buckets delete "${BUCKET_NAME}" --force >/dev/null 2>&1 || true

"${TIGRIS_BIN}" buckets create "${BUCKET_NAME}" --enable-snapshots

echo "setup.sh: created bucket ${BUCKET_NAME} with snapshots enabled."
EOF

RUN chmod +x /home/user/pipeline/setup.sh

RUN cd /home/user/pipeline && npm install --no-audit --no-fund && \
    ln -sf /home/user/pipeline/node_modules/.bin/tigris /usr/local/bin/tigris

# Container contents:
#   - Ubuntu 24.04 base with curl, wget, ca-certificates, git, python3,
#     python3-pip, python3-pytest, bash.
#   - Node.js v24 installed via NodeSource.
#   - /home/user/pipeline — TypeScript project pre-initialized with
#     package.json, tsconfig.json, and node_modules containing
#     @tigrisdata/agent-kit, @tigrisdata/cli, @aws-sdk/client-s3, tsx, and
#     typescript. orchestrate.ts is intentionally absent — the user must
#     create it.
#   - /home/user/pipeline/setup.sh — executable script that provisions the
#     `pipeline-out` bucket with snapshots enabled at task start.
#   - tigris CLI symlinked to /usr/local/bin/tigris.

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
