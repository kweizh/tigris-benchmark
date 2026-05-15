FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g tsx@4.19.2 typescript@5.6.3 @tigrisdata/cli && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="any-task-builder"
LABEL Description="Tigris Agent Kit checkpoint/restore task: Node.js 24, @tigrisdata/agent-kit, @tigrisdata/storage, tsx, and the Tigris CLI. Entrypoint seeds a snapshot-enabled base bucket with two pre-existing data/v*.txt objects."

# Wire the Harbor-provided TIGRIS_STORAGE_* credentials into the AWS-compatible
# variables that the `tigris` CLI consumes. No secrets baked into the image —
# these resolve from the runtime environment each shell start.
RUN printf '%s\n' \
    'export AWS_ACCESS_KEY_ID="${TIGRIS_STORAGE_ACCESS_KEY_ID:-${AWS_ACCESS_KEY_ID:-}}"' \
    'export AWS_SECRET_ACCESS_KEY="${TIGRIS_STORAGE_SECRET_ACCESS_KEY:-${AWS_SECRET_ACCESS_KEY:-}}"' \
    'export AWS_REGION="${AWS_REGION:-auto}"' \
    > /etc/profile.d/tigris-auth.sh && \
    chmod 0644 /etc/profile.d/tigris-auth.sh && \
    printf '%s\n' \
    '# Source Tigris CLI auth bridge for non-login interactive shells' \
    '. /etc/profile.d/tigris-auth.sh' \
    >> /root/.bashrc

# Pre-initialize the project directory with @tigrisdata/agent-kit,
# @tigrisdata/storage, tsx, and a tsconfig.json so the agent can run TypeScript
# without any installation step.
RUN mkdir -p /home/user/tigris-task && \
    cd /home/user/tigris-task && \
    cat > package.json <<'EOF'
{
  "name": "tigris-task",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "start": "tsx run.ts"
  },
  "dependencies": {
    "@tigrisdata/agent-kit": "^0.1.0",
    "@tigrisdata/storage": "^3.0.0"
  },
  "devDependencies": {
    "tsx": "^4.19.2",
    "typescript": "^5.6.3",
    "@types/node": "^22.7.5"
  }
}
EOF

RUN cd /home/user/tigris-task && \
    cat > tsconfig.json <<'EOF'
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "Bundler",
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": false,
    "outDir": "dist"
  },
  "include": ["*.ts"]
}
EOF

RUN cd /home/user/tigris-task && npm install --no-audit --no-fund

# Entrypoint script: at container start, wait for the Harbor-provided
# /logs/artifacts/trial_id file, then use the Tigris CLI to create
# `harbor-base-${trial_id}` with snapshots enabled and upload two pre-seeded
# objects (data/v1.txt = "version1", data/v2.txt = "version2"). Writes
# /tmp/tigris-seed.done on success, then enters the standard sleep-infinity
# wait loop so the container stays alive for the agent.
RUN printf '%s\n' \
    '#!/usr/bin/env bash' \
    'set -uo pipefail' \
    '' \
    'LOG=/var/log/tigris-seed.log' \
    'mkdir -p /var/log' \
    'exec > >(tee -a "$LOG") 2>&1' \
    '' \
    'echo "[seed] starting at $(date -u +%FT%TZ)"' \
    '' \
    'TRIAL_ID_FILE=/logs/artifacts/trial_id' \
    'for i in $(seq 1 120); do' \
    '    if [ -s "$TRIAL_ID_FILE" ]; then break; fi' \
    '    sleep 1' \
    'done' \
    '' \
    'if [ ! -s "$TRIAL_ID_FILE" ]; then' \
    '    echo "[seed] ERROR: $TRIAL_ID_FILE missing or empty after waiting"' \
    'else' \
    '    TRIAL_ID="$(tr -d "[:space:]" < "$TRIAL_ID_FILE")"' \
    '    BASE_BUCKET="harbor-base-${TRIAL_ID}"' \
    '    echo "[seed] target base bucket: $BASE_BUCKET"' \
    '' \
    '    export AWS_ACCESS_KEY_ID="${TIGRIS_STORAGE_ACCESS_KEY_ID:-${AWS_ACCESS_KEY_ID:-}}"' \
    '    export AWS_SECRET_ACCESS_KEY="${TIGRIS_STORAGE_SECRET_ACCESS_KEY:-${AWS_SECRET_ACCESS_KEY:-}}"' \
    '    export AWS_REGION="${AWS_REGION:-auto}"' \
    '' \
    '    if [ -z "${AWS_ACCESS_KEY_ID}" ] || [ -z "${AWS_SECRET_ACCESS_KEY}" ]; then' \
    '        echo "[seed] ERROR: TIGRIS_STORAGE_ACCESS_KEY_ID / TIGRIS_STORAGE_SECRET_ACCESS_KEY not set"' \
    '    else' \
    '        echo "[seed] creating snapshot-enabled bucket $BASE_BUCKET"' \
    '        if tigris buckets create "$BASE_BUCKET" --enable-snapshots; then' \
    '            echo "[seed] base bucket created"' \
    '        else' \
    '            echo "[seed] base bucket create returned non-zero (may already exist); continuing"' \
    '        fi' \
    '' \
    '        TMP_V1=/tmp/v1.txt' \
    '        TMP_V2=/tmp/v2.txt' \
    '        printf "version1" > "$TMP_V1"' \
    '        printf "version2" > "$TMP_V2"' \
    '' \
    '        ok=1' \
    '        echo "[seed] uploading data/v1.txt ($(wc -c < "$TMP_V1") bytes)"' \
    '        if ! tigris cp "$TMP_V1" "t3://${BASE_BUCKET}/data/v1.txt"; then' \
    '            echo "[seed] ERROR: data/v1.txt upload failed"' \
    '            ok=0' \
    '        fi' \
    '        echo "[seed] uploading data/v2.txt ($(wc -c < "$TMP_V2") bytes)"' \
    '        if ! tigris cp "$TMP_V2" "t3://${BASE_BUCKET}/data/v2.txt"; then' \
    '            echo "[seed] ERROR: data/v2.txt upload failed"' \
    '            ok=0' \
    '        fi' \
    '        rm -f "$TMP_V1" "$TMP_V2"' \
    '' \
    '        if [ "$ok" = "1" ]; then' \
    '            : > /tmp/tigris-seed.done' \
    '            echo "[seed] wrote sentinel /tmp/tigris-seed.done"' \
    '        fi' \
    '    fi' \
    'fi' \
    '' \
    'echo "[seed] entering sleep-infinity wait loop"' \
    'trap : TERM INT' \
    'sleep infinity & wait' \
    > /usr/local/bin/seed-and-wait.sh && \
    chmod 0755 /usr/local/bin/seed-and-wait.sh

# Container contents:
#   - Ubuntu 24.04 base
#   - System libs: curl wget ca-certificates git python3 python3-pip python3-pytest bash gnupg
#   - Node.js v24 (from NodeSource) and npm
#   - Globally installed: tsx, typescript, @tigrisdata/cli (binary: `tigris`)
#   - /home/user/tigris-task — pre-initialized project with
#       @tigrisdata/agent-kit, @tigrisdata/storage, tsx, and typescript
#       installed locally (node_modules populated, tsconfig.json present).
#   - /etc/profile.d/tigris-auth.sh — login-shell bridge that maps
#       TIGRIS_STORAGE_ACCESS_KEY_ID / TIGRIS_STORAGE_SECRET_ACCESS_KEY into
#       AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION=auto so the
#       `tigris` CLI authenticates against Harbor-provided credentials.
#   - /usr/local/bin/seed-and-wait.sh — entrypoint script that pre-seeds the
#       snapshot-enabled base bucket harbor-base-${trial_id} with two objects
#       data/v1.txt ("version1") and data/v2.txt ("version2"), then enters
#       sleep infinity. Writes /tmp/tigris-seed.done sentinel on success.

CMD ["/usr/local/bin/seed-and-wait.sh"]
