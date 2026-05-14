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
LABEL Description="Tigris Agent Kit isolated_fork_writer_audit task: Node.js v24 with a pre-initialized /home/user/isolation project containing @tigrisdata/agent-kit, @tigrisdata/cli, @aws-sdk/client-s3, tsx, and typescript installed locally, plus a setup.sh that provisions the gold-source bucket with seed files at task start."

# Pre-create the project directory with package.json, tsconfig.json, and a
# local node_modules containing the required packages. The user must author
# /home/user/isolation/index.ts themselves.
RUN mkdir -p /home/user/isolation && \
    cd /home/user/isolation && \
    cat >package.json <<'EOF'
{
  "name": "isolation",
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

RUN cd /home/user/isolation && \
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
# the source bucket `gold-source` with snapshots enabled and pre-seeds it with
# `seed1.txt` and `seed2.txt` via the Tigris CLI. It is idempotent so it can
# safely run on retries. It uses the admin Tigris credentials that the task
# runtime injects via TIGRIS_STORAGE_ACCESS_KEY_ID / TIGRIS_STORAGE_SECRET_ACCESS_KEY.
RUN cat >/home/user/isolation/setup.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/user/isolation"
BUCKET_NAME="gold-source"

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

# Best-effort: nuke any prior bucket so the task starts clean (snapshots+seeds).
"${TIGRIS_BIN}" buckets delete "${BUCKET_NAME}" --force >/dev/null 2>&1 || true

"${TIGRIS_BIN}" buckets create "${BUCKET_NAME}" --enable-snapshots

# Prepare seed files locally and upload them.
SEED_DIR="$(mktemp -d)"
trap 'rm -rf "${SEED_DIR}"' EXIT
printf 'gold-source seed object number one.\n' >"${SEED_DIR}/seed1.txt"
printf 'gold-source seed object number two.\n' >"${SEED_DIR}/seed2.txt"

"${TIGRIS_BIN}" objects upload "${SEED_DIR}/seed1.txt" "${BUCKET_NAME}/seed1.txt"
"${TIGRIS_BIN}" objects upload "${SEED_DIR}/seed2.txt" "${BUCKET_NAME}/seed2.txt"

echo "setup.sh: created bucket ${BUCKET_NAME} (snapshots enabled) with seed1.txt and seed2.txt."
EOF

RUN chmod +x /home/user/isolation/setup.sh

RUN cd /home/user/isolation && npm install --no-audit --no-fund && \
    ln -sf /home/user/isolation/node_modules/.bin/tigris /usr/local/bin/tigris

# Container contents:
#   - Ubuntu 24.04 base with curl, wget, ca-certificates, git, python3,
#     python3-pip, python3-pytest, bash.
#   - Node.js v24 installed via NodeSource.
#   - /home/user/isolation — TypeScript project pre-initialized with
#     package.json, tsconfig.json, and node_modules containing
#     @tigrisdata/agent-kit, @tigrisdata/cli, @aws-sdk/client-s3, tsx, and
#     typescript. index.ts is intentionally absent — the user must create it.
#   - /home/user/isolation/setup.sh — executable script that provisions the
#     `gold-source` bucket with snapshots enabled and seeds it with
#     seed1.txt and seed2.txt at task start.
#   - tigris CLI symlinked to /usr/local/bin/tigris.

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
