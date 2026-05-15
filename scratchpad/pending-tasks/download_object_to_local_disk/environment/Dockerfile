FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm i -g @tigrisdata/cli && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

LABEL Author="any-task-builder"
LABEL Description="Tigris CLI environment that pre-seeds a per-trial bucket and an assets/welcome.md object at container start, so the agent can download it to local disk."

RUN mkdir -p /home/user && chmod 0755 /home/user

# Pre-create the project working directory; the agent will deposit the
# downloaded welcome.md file inside it.
RUN mkdir -p /home/user/tigris-task && \
    chmod 0755 /home/user/tigris-task

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
# /logs/artifacts/trial_id file, then use the Tigris CLI to create the bucket
# `harbor-download-${trial_id}` and upload the object `assets/welcome.md`
# (contents: `# Welcome to Tigris\n`). Once seeding succeeds, the script
# writes a sentinel at /tmp/tigris-seed.done and enters the standard
# sleep-infinity wait pattern so the container stays alive for the agent.
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
    '    BUCKET="harbor-download-${TRIAL_ID}"' \
    '    echo "[seed] target bucket: $BUCKET"' \
    '' \
    '    export AWS_ACCESS_KEY_ID="${TIGRIS_STORAGE_ACCESS_KEY_ID:-${AWS_ACCESS_KEY_ID:-}}"' \
    '    export AWS_SECRET_ACCESS_KEY="${TIGRIS_STORAGE_SECRET_ACCESS_KEY:-${AWS_SECRET_ACCESS_KEY:-}}"' \
    '    export AWS_REGION="${AWS_REGION:-auto}"' \
    '' \
    '    if [ -z "${AWS_ACCESS_KEY_ID}" ] || [ -z "${AWS_SECRET_ACCESS_KEY}" ]; then' \
    '        echo "[seed] ERROR: TIGRIS_STORAGE_ACCESS_KEY_ID / TIGRIS_STORAGE_SECRET_ACCESS_KEY not set"' \
    '    else' \
    '        echo "[seed] creating bucket $BUCKET"' \
    '        if tigris buckets create "$BUCKET"; then' \
    '            echo "[seed] bucket created"' \
    '        else' \
    '            echo "[seed] bucket create returned non-zero (may already exist); continuing"' \
    '        fi' \
    '' \
    '        TMP_OBJ=/tmp/welcome.md' \
    '        printf "# Welcome to Tigris\\n" > "$TMP_OBJ"' \
    '        echo "[seed] uploading welcome.md ($(wc -c < "$TMP_OBJ") bytes)"' \
    '' \
    '        if tigris cp "$TMP_OBJ" "t3://${BUCKET}/assets/welcome.md"; then' \
    '            echo "[seed] object uploaded"' \
    '            : > /tmp/tigris-seed.done' \
    '            echo "[seed] wrote sentinel /tmp/tigris-seed.done"' \
    '        else' \
    '            echo "[seed] ERROR: object upload failed"' \
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
#   - Node.js v24 runtime for the Tigris CLI npm package
#   - @tigrisdata/cli installed globally, providing the `tigris` (and `t3`) command
#   - /home/user/tigris-task — empty project directory where the agent must
#     deposit the downloaded welcome.md file.
#   - /etc/profile.d/tigris-auth.sh — login-shell bridge that maps
#     TIGRIS_STORAGE_ACCESS_KEY_ID / TIGRIS_STORAGE_SECRET_ACCESS_KEY into
#     AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION=auto so the
#     `tigris` CLI authenticates against the Harbor-provided credentials.
#   - /usr/local/bin/seed-and-wait.sh — entrypoint script that pre-seeds the
#     per-trial bucket `harbor-download-${trial_id}` and uploads
#     `assets/welcome.md` (content `# Welcome to Tigris\n`) before entering
#     the sleep-infinity wait loop. Writes /tmp/tigris-seed.done on success.

CMD ["/usr/local/bin/seed-and-wait.sh"]
