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
LABEL Description="Tigris Agent Kit task environment with Node.js v24, @tigrisdata/cli, @tigrisdata/agent-kit, and a pre-initialized ckpt-tag project containing build_id.txt and a setup.sh that provisions the snapshot-enabled bucket."

RUN mkdir -p /home/user/ckpt-tag && \
    cd /home/user/ckpt-tag && \
    cat >package.json <<'EOF'
{
  "name": "ckpt-tag",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "start": "tsx index.ts"
  },
  "dependencies": {
    "@tigrisdata/agent-kit": "^0.1.0"
  },
  "devDependencies": {
    "tsx": "^4.19.0",
    "typescript": "^5.6.0"
  }
}
EOF

RUN cat >/home/user/ckpt-tag/tsconfig.json <<'EOF'
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

RUN printf 'v42\n' > /home/user/ckpt-tag/build_id.txt

RUN cat >/home/user/ckpt-tag/setup.sh <<'EOF'
#!/usr/bin/env bash
# Pre-task setup: provision the source bucket required by the task.
# Idempotent — safe to re-run.
set -u

: "${TIGRIS_STORAGE_ACCESS_KEY_ID:?TIGRIS_STORAGE_ACCESS_KEY_ID is required}"
: "${TIGRIS_STORAGE_SECRET_ACCESS_KEY:?TIGRIS_STORAGE_SECRET_ACCESS_KEY is required}"

export AWS_ACCESS_KEY_ID="${TIGRIS_STORAGE_ACCESS_KEY_ID}"
export AWS_SECRET_ACCESS_KEY="${TIGRIS_STORAGE_SECRET_ACCESS_KEY}"
export AWS_REGION="auto"

BUCKET="agent-pipeline-data"

# Create the bucket with snapshots enabled if it does not already exist.
if tigris buckets get "${BUCKET}" >/dev/null 2>&1; then
    echo "Bucket ${BUCKET} already exists; ensuring snapshots are enabled."
    tigris buckets set "${BUCKET}" --enable-snapshots >/dev/null 2>&1 || true
else
    tigris buckets create "${BUCKET}" --enable-snapshots
fi

echo "setup.sh: bucket ${BUCKET} ready."
EOF

RUN chmod +x /home/user/ckpt-tag/setup.sh

# Container contents:
#   - Ubuntu 24.04 base
#   - Node.js v24 + npm + npx
#   - @tigrisdata/cli (tigris) and @tigrisdata/agent-kit installed globally
#   - /home/user/ckpt-tag: project scaffold with package.json, tsconfig.json, build_id.txt (=v42), setup.sh
#   - setup.sh creates the snapshot-enabled bucket `agent-pipeline-data` at container start

CMD ["/bin/bash", "-c", "trap : TERM INT; /home/user/ckpt-tag/setup.sh; sleep infinity & wait"]
