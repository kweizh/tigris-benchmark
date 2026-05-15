FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g @tigrisdata/cli tsx@4.19.2 typescript@5.6.3 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="any-task-builder"
LABEL Description="Tigris Storage SDK bucket-to-bucket copy task: Node.js 24, @tigrisdata/storage and tsx pre-installed in /home/user/tigris-task. Entrypoint pre-seeds a source bucket with 5 JSON objects."

# Pre-create the project working directory and install dependencies so the
# agent can immediately run `tsx copy.ts` against `@tigrisdata/storage`.
RUN mkdir -p /home/user/tigris-task && \
    cd /home/user/tigris-task && \
    cat > package.json <<'EOF'
{
  "name": "tigris-task",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "start": "tsx copy.ts"
  },
  "dependencies": {
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
# /logs/artifacts/trial_id file, then use the Tigris CLI to create the source
# bucket `harbor-src-${trial_id}` and upload five JSON objects under the
# `data/` prefix. Once seeding succeeds, the script writes a sentinel at
# /tmp/tigris-seed.done and enters the standard sleep-infinity wait pattern.
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
    '    SRC_BUCKET="harbor-src-${TRIAL_ID}"' \
    '    echo "[seed] source bucket: $SRC_BUCKET"' \
    '' \
    '    export AWS_ACCESS_KEY_ID="${TIGRIS_STORAGE_ACCESS_KEY_ID:-${AWS_ACCESS_KEY_ID:-}}"' \
    '    export AWS_SECRET_ACCESS_KEY="${TIGRIS_STORAGE_SECRET_ACCESS_KEY:-${AWS_SECRET_ACCESS_KEY:-}}"' \
    '    export AWS_REGION="${AWS_REGION:-auto}"' \
    '' \
    '    if [ -z "${AWS_ACCESS_KEY_ID}" ] || [ -z "${AWS_SECRET_ACCESS_KEY}" ]; then' \
    '        echo "[seed] ERROR: TIGRIS_STORAGE_ACCESS_KEY_ID / TIGRIS_STORAGE_SECRET_ACCESS_KEY not set"' \
    '    else' \
    '        echo "[seed] creating source bucket $SRC_BUCKET"' \
    '        if tigris buckets create "$SRC_BUCKET"; then' \
    '            echo "[seed] source bucket created"' \
    '        else' \
    '            echo "[seed] source bucket create returned non-zero (may already exist); continuing"' \
    '        fi' \
    '' \
    '        FAIL=0' \
    '        for N in 1 2 3 4 5; do' \
    '            NUM=$(printf "%02d" "$N")' \
    '            PAYLOAD=""' \
    '            for _ in $(seq 1 "$N"); do PAYLOAD="${PAYLOAD}foo"; done' \
    '            BODY=$(printf "{\"index\": %d, \"payload\": \"%s\"}" "$N" "$PAYLOAD")' \
    '            TMP="/tmp/seed-${NUM}.json"' \
    '            printf "%s" "$BODY" > "$TMP"' \
    '            echo "[seed] uploading data/${NUM}.json (${#BODY} bytes)"' \
    '            if tigris cp "$TMP" "t3://${SRC_BUCKET}/data/${NUM}.json"; then' \
    '                echo "[seed] data/${NUM}.json uploaded"' \
    '            else' \
    '                echo "[seed] ERROR: data/${NUM}.json upload failed"' \
    '                FAIL=1' \
    '            fi' \
    '            rm -f "$TMP"' \
    '        done' \
    '' \
    '        if [ "$FAIL" -eq 0 ]; then' \
    '            : > /tmp/tigris-seed.done' \
    '            echo "[seed] wrote sentinel /tmp/tigris-seed.done"' \
    '        else' \
    '            echo "[seed] ERROR: one or more seed uploads failed; sentinel not written"' \
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
#   - always required libs: curl wget ca-certificates git python3 python3-pip python3-pytest bash gnupg
#   - Node.js v24 runtime
#   - @tigrisdata/cli installed globally (provides the `tigris` command used by the entrypoint seeder)
#   - tsx and typescript installed globally (the agent runs copy.ts directly)
#   - /home/user/tigris-task — project pre-initialized with @tigrisdata/storage and tsx installed locally
#   - /etc/profile.d/tigris-auth.sh — login-shell bridge that maps TIGRIS_STORAGE_* into AWS_* so the
#     `tigris` CLI authenticates against the Harbor-provided credentials.
#   - /usr/local/bin/seed-and-wait.sh — entrypoint script that pre-seeds `harbor-src-${trial_id}`
#     with five JSON objects under `data/01.json`..`data/05.json` before entering the sleep-infinity
#     wait loop. Writes /tmp/tigris-seed.done on success.

CMD ["/usr/local/bin/seed-and-wait.sh"]
