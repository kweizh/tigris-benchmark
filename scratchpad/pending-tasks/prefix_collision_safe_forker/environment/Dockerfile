FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash \
        unzip jq && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm i -g @tigrisdata/cli @tigrisdata/agent-kit && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="any-task-builder"
LABEL Description="Tigris Agent Kit task environment with Node.js v24, @tigrisdata/cli, @tigrisdata/agent-kit, and a pre-initialized safe-fork project."

RUN mkdir -p /home/user/safe-fork && \
    cd /home/user/safe-fork && \
    cat >package.json <<'EOF'
{
  "name": "safe-fork",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "start": "tsx index.ts"
  },
  "dependencies": {
    "@tigrisdata/agent-kit": "^0.1.0",
    "@tigrisdata/storage": "^0.1.0"
  },
  "devDependencies": {
    "tsx": "^4.19.0",
    "typescript": "^5.6.0"
  }
}
EOF

RUN cat >/home/user/safe-fork/tsconfig.json <<'EOF'
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true
  }
}
EOF

RUN cat >/home/user/safe-fork/setup.sh <<'EOF'
#!/usr/bin/env bash
# Pre-task setup: provision the snapshot-enabled source bucket AND seed a
# leftover collision bucket (eval-prefix-stale-001) so the user must clean
# up before forking.
# Idempotent — safe to re-run.
set -u

: "${TIGRIS_STORAGE_ACCESS_KEY_ID:?TIGRIS_STORAGE_ACCESS_KEY_ID is required}"
: "${TIGRIS_STORAGE_SECRET_ACCESS_KEY:?TIGRIS_STORAGE_SECRET_ACCESS_KEY is required}"

export AWS_ACCESS_KEY_ID="${TIGRIS_STORAGE_ACCESS_KEY_ID}"
export AWS_SECRET_ACCESS_KEY="${TIGRIS_STORAGE_SECRET_ACCESS_KEY}"
export AWS_REGION="auto"

SOURCE_BUCKET="source-bucket"
STALE_BUCKET="eval-prefix-stale-001"

# Source bucket with snapshots enabled.
if tigris buckets get "${SOURCE_BUCKET}" >/dev/null 2>&1; then
    echo "Bucket ${SOURCE_BUCKET} already exists; ensuring snapshots are enabled."
    tigris buckets set "${SOURCE_BUCKET}" --enable-snapshots >/dev/null 2>&1 || true
else
    tigris buckets create "${SOURCE_BUCKET}" --enable-snapshots
fi

# Leftover collision bucket. Does NOT need snapshots.
if tigris buckets get "${STALE_BUCKET}" >/dev/null 2>&1; then
    echo "Leftover bucket ${STALE_BUCKET} already exists."
else
    tigris buckets create "${STALE_BUCKET}"
fi

echo "setup.sh: buckets ${SOURCE_BUCKET} and ${STALE_BUCKET} ready."
EOF

RUN chmod +x /home/user/safe-fork/setup.sh

# Container contents:
#   - Ubuntu 24.04 base
#   - Node.js v24 + npm + npx
#   - @tigrisdata/cli (tigris) and @tigrisdata/agent-kit installed globally
#   - /home/user/safe-fork: project scaffold with package.json, tsconfig.json, setup.sh
#   - setup.sh creates the snapshot-enabled `source-bucket` AND the leftover `eval-prefix-stale-001` bucket at task start

CMD ["/bin/bash", "-c", "trap : TERM INT; /home/user/safe-fork/setup.sh; sleep infinity & wait"]
