FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash gnupg unzip && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm i -g @tigrisdata/cli && \
    ARCH="$(dpkg --print-architecture)" && \
    case "$ARCH" in \
        amd64) AWS_ARCH=x86_64 ;; \
        arm64) AWS_ARCH=aarch64 ;; \
        *) echo "Unsupported arch: $ARCH" && exit 1 ;; \
    esac && \
    curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-${AWS_ARCH}.zip" -o /tmp/awscliv2.zip && \
    unzip -q /tmp/awscliv2.zip -d /tmp && \
    /tmp/aws/install && \
    rm -rf /tmp/aws /tmp/awscliv2.zip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

LABEL Author="any-task-builder"
LABEL Description="Tigris CLI + AWS CLI environment that pre-seeds an origin bucket (harbor-origin-${trial_id}) containing docs/readme.md with content 'from origin', so the agent can configure a shadow bucket and read the object through the shadow read-through."

RUN mkdir -p /home/user && chmod 0755 /home/user

# Pre-create the project working directory; the agent will deposit the
# proxied.md file inside it.
RUN mkdir -p /home/user/tigris-task && \
    chmod 0755 /home/user/tigris-task

# Wire the Harbor-provided TIGRIS_STORAGE_* credentials into the AWS-compatible
# environment variables that both the `tigris` CLI and the `aws` CLI consume.
# No secrets are baked into the image — these variables are resolved from the
# runtime environment every time a login shell starts.
RUN printf '%s\n' \
    'export AWS_ACCESS_KEY_ID="${TIGRIS_STORAGE_ACCESS_KEY_ID:-${AWS_ACCESS_KEY_ID:-}}"' \
    'export AWS_SECRET_ACCESS_KEY="${TIGRIS_STORAGE_SECRET_ACCESS_KEY:-${AWS_SECRET_ACCESS_KEY:-}}"' \
    'export AWS_REGION="${AWS_REGION:-auto}"' \
    'export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-auto}"' \
    > /etc/profile.d/tigris-auth.sh && \
    chmod 0644 /etc/profile.d/tigris-auth.sh && \
    printf '%s\n' \
    '# Source Tigris CLI auth bridge for non-login interactive shells' \
    '. /etc/profile.d/tigris-auth.sh' \
    >> /root/.bashrc

# Entrypoint script: at container start, wait for the Harbor-provided
# /logs/artifacts/trial_id file, then use the Tigris CLI to create the
# bucket `harbor-origin-${trial_id}` and upload the object `docs/readme.md`
# with EXACTLY the bytes "from origin" (no trailing newline). Once seeding
# succeeds, the script writes a sentinel at /tmp/tigris-seed.done and enters
# the standard sleep-infinity wait pattern so the container stays alive for
# the agent.
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
    '    ORIGIN_BUCKET="harbor-origin-${TRIAL_ID}"' \
    '    echo "[seed] origin bucket: $ORIGIN_BUCKET"' \
    '' \
    '    export AWS_ACCESS_KEY_ID="${TIGRIS_STORAGE_ACCESS_KEY_ID:-${AWS_ACCESS_KEY_ID:-}}"' \
    '    export AWS_SECRET_ACCESS_KEY="${TIGRIS_STORAGE_SECRET_ACCESS_KEY:-${AWS_SECRET_ACCESS_KEY:-}}"' \
    '    export AWS_REGION="${AWS_REGION:-auto}"' \
    '    export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-auto}"' \
    '' \
    '    if [ -z "${AWS_ACCESS_KEY_ID}" ] || [ -z "${AWS_SECRET_ACCESS_KEY}" ]; then' \
    '        echo "[seed] ERROR: TIGRIS_STORAGE_ACCESS_KEY_ID / TIGRIS_STORAGE_SECRET_ACCESS_KEY not set"' \
    '    else' \
    '        echo "[seed] creating origin bucket $ORIGIN_BUCKET"' \
    '        if tigris buckets create "$ORIGIN_BUCKET"; then' \
    '            echo "[seed] origin bucket created"' \
    '        else' \
    '            echo "[seed] origin bucket create returned non-zero (may already exist); continuing"' \
    '        fi' \
    '' \
    '        TMP_OBJ=/tmp/readme.md' \
    '        # Write EXACTLY 11 bytes: "from origin" with NO trailing newline.' \
    '        printf "%s" "from origin" > "$TMP_OBJ"' \
    '        SEED_BYTES=$(wc -c < "$TMP_OBJ")' \
    '        echo "[seed] uploading docs/readme.md ($SEED_BYTES bytes) to $ORIGIN_BUCKET"' \
    '' \
    '        if tigris cp "$TMP_OBJ" "t3://${ORIGIN_BUCKET}/docs/readme.md"; then' \
    '            echo "[seed] origin object uploaded"' \
    '            : > /tmp/tigris-seed.done' \
    '            echo "[seed] wrote sentinel /tmp/tigris-seed.done"' \
    '        else' \
    '            echo "[seed] ERROR: origin object upload failed"' \
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
#   - awscli for `aws s3 cp ... --endpoint-url https://t3.storage.dev` reads
#   - Node.js v24 runtime for the Tigris CLI npm package
#   - @tigrisdata/cli installed globally, providing the `tigris` (and `t3`) command
#   - /home/user/tigris-task — empty project directory where the agent must
#     deposit the proxied.md file fetched via the shadow bucket.
#   - /etc/profile.d/tigris-auth.sh — login-shell bridge that maps
#     TIGRIS_STORAGE_ACCESS_KEY_ID / TIGRIS_STORAGE_SECRET_ACCESS_KEY into
#     AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION=auto so both
#     the `tigris` CLI and the `aws` CLI authenticate against the Harbor
#     credentials.
#   - /usr/local/bin/seed-and-wait.sh — entrypoint script that pre-seeds the
#     per-trial origin bucket `harbor-origin-${trial_id}` and uploads
#     `docs/readme.md` (content exactly `from origin`, no trailing newline)
#     before entering the sleep-infinity wait loop. Writes
#     /tmp/tigris-seed.done on success.

CMD ["/usr/local/bin/seed-and-wait.sh"]
