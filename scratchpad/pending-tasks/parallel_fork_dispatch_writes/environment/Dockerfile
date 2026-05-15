FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm i -g @tigrisdata/cli tsx@4.19.2 typescript@5.6.3 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

LABEL Author="any-task-builder"
LABEL Description="Tigris Agent Kit environment that seeds a snapshot-enabled source bucket with seed/dataset.txt at container start so the agent can fork it 3x in parallel via @tigrisdata/agent-kit."

RUN mkdir -p /home/user && chmod 0755 /home/user

# Pre-create the project working directory and pre-install the agent-kit /
# storage SDK + tsx dev dependency. The agent only needs to author run.ts
# and execute it.
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

# Wire the Harbor-provided TIGRIS_STORAGE_* credentials into the AWS-compatible
# environment variables that the `tigris` CLI consumes. No secrets are baked
# into the image — these variables are resolved from the runtime environment
# every time a login shell starts.
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

# Entrypoint script: at container start, wait for the Harbor-provided
# /logs/artifacts/trial_id file, then use the Tigris CLI to create the
# source bucket `harbor-source-${trial_id}` with snapshots enabled and
# upload `seed/dataset.txt` (contents: `initial`, no trailing newline).
# Once seeding succeeds, the script writes a sentinel at
# /tmp/tigris-seed.done and enters the standard sleep-infinity wait
# pattern so the container stays alive for the agent.
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
    '    SOURCE_BUCKET="harbor-source-${TRIAL_ID}"' \
    '    echo "[seed] target source bucket: $SOURCE_BUCKET"' \
    '' \
    '    export AWS_ACCESS_KEY_ID="${TIGRIS_STORAGE_ACCESS_KEY_ID:-${AWS_ACCESS_KEY_ID:-}}"' \
    '    export AWS_SECRET_ACCESS_KEY="${TIGRIS_STORAGE_SECRET_ACCESS_KEY:-${AWS_SECRET_ACCESS_KEY:-}}"' \
    '    export AWS_REGION="${AWS_REGION:-auto}"' \
    '' \
    '    if [ -z "${AWS_ACCESS_KEY_ID}" ] || [ -z "${AWS_SECRET_ACCESS_KEY}" ]; then' \
    '        echo "[seed] ERROR: TIGRIS_STORAGE_ACCESS_KEY_ID / TIGRIS_STORAGE_SECRET_ACCESS_KEY not set"' \
    '    else' \
    '        # Best-effort cleanup of any stale bucket/forks from a prior trial' \
    '        for i in 0 1 2; do' \
    '            tigris rm -r "t3://harbor-fork-${TRIAL_ID}-${i}/" >/dev/null 2>&1 || true' \
    '            tigris buckets delete "harbor-fork-${TRIAL_ID}-${i}" --force >/dev/null 2>&1 || true' \
    '        done' \
    '        tigris rm -r "t3://${SOURCE_BUCKET}/" >/dev/null 2>&1 || true' \
    '        tigris buckets delete "${SOURCE_BUCKET}" --force >/dev/null 2>&1 || true' \
    '' \
    '        echo "[seed] creating snapshot-enabled bucket $SOURCE_BUCKET"' \
    '        if tigris buckets create "$SOURCE_BUCKET" --enable-snapshots; then' \
    '            echo "[seed] source bucket created"' \
    '        else' \
    '            echo "[seed] bucket create returned non-zero (may already exist); continuing"' \
    '        fi' \
    '' \
    '        TMP_OBJ=/tmp/dataset.txt' \
    '        printf "initial" > "$TMP_OBJ"' \
    '        echo "[seed] uploading seed/dataset.txt ($(wc -c < "$TMP_OBJ") bytes)"' \
    '' \
    '        if tigris cp "$TMP_OBJ" "t3://${SOURCE_BUCKET}/seed/dataset.txt"; then' \
    '            echo "[seed] seed object uploaded"' \
    '            : > /tmp/tigris-seed.done' \
    '            echo "[seed] wrote sentinel /tmp/tigris-seed.done"' \
    '        else' \
    '            echo "[seed] ERROR: seed object upload failed"' \
    '        fi' \
    '        rm -f "$TMP_OBJ"' \
    '    fi' \
    'fi' \
    '' \
    'echo "[seed] entering sleep-infinity wait loop"' \
    'trap : TERM INT' \
    'sleep infinity & wait' \
    > /usr/local/bin/seed-and-wait.sh && \
    chmod 0755 /usr/local/bin/seed-and-wait.sh

# Container contents:
#   - always required libs: curl wget ca-certificates git python3 python3-pip python3-pytest bash gnupg
#   - Node.js v24 runtime for the Tigris CLI + npm packages
#   - @tigrisdata/cli installed globally for the entrypoint seed script
#   - tsx and typescript installed globally so the agent can run TypeScript directly
#   - /home/user/tigris-task — project pre-initialized with @tigrisdata/agent-kit,
#     @tigrisdata/storage, and tsx installed locally (npm install run at build time)
#   - tsconfig.json for ES2022 module compilation
#   - /etc/profile.d/tigris-auth.sh — login-shell bridge mapping TIGRIS_STORAGE_*
#     into AWS_* so the `tigris` CLI authenticates against Harbor credentials
#   - /usr/local/bin/seed-and-wait.sh — entrypoint script that creates the
#     snapshot-enabled source bucket harbor-source-${trial_id} and uploads the
#     seed/dataset.txt object before entering the sleep-infinity wait loop.

CMD ["/usr/local/bin/seed-and-wait.sh"]
