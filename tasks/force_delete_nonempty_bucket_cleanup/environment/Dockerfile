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
LABEL Description="Tigris CLI environment that seeds a non-empty bucket at container start so the agent can practice force-deleting it via @tigrisdata/cli."

RUN mkdir -p /home/user && chmod 0755 /home/user
RUN mkdir -p /home/user/cleanup-task && chmod 0755 /home/user/cleanup-task

# Wire the Harbor-provided TIGRIS_STORAGE_* credentials into the AWS-compatible
# environment variables that the `tigris` CLI consumes. No secrets are baked
# into the image - these variables are resolved from the runtime environment
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

# Container start-up: a real bucket on the Tigris service is created at run
# time (NOT at build time, because no credentials are available at build
# time) and seeded with three small scratch objects. After seeding completes
# the container enters the standard idle wait loop so Harbor can schedule
# the agent and verifier against it.
RUN printf '%s\n' \
    '#!/usr/bin/env bash' \
    'set -uo pipefail' \
    '' \
    '# Bring Tigris credentials into the AWS-compatible variable namespace.' \
    '. /etc/profile.d/tigris-auth.sh' \
    '' \
    'TRIAL_ID_FILE="/logs/artifacts/trial_id"' \
    'echo "[seed] waiting for trial id file at ${TRIAL_ID_FILE}..."' \
    'for _ in $(seq 1 60); do' \
    '  if [ -s "${TRIAL_ID_FILE}" ]; then' \
    '    break' \
    '  fi' \
    '  sleep 1' \
    'done' \
    '' \
    'if [ ! -s "${TRIAL_ID_FILE}" ]; then' \
    '  echo "[seed] ERROR: trial id file ${TRIAL_ID_FILE} is missing or empty after wait" >&2' \
    'fi' \
    '' \
    'TRIAL_ID="$(tr -d "[:space:]" < "${TRIAL_ID_FILE}" 2>/dev/null || true)"' \
    'BUCKET_NAME="harbor-cleanup-${TRIAL_ID}"' \
    'echo "[seed] target bucket: ${BUCKET_NAME}"' \
    '' \
    'if [ -z "${TIGRIS_STORAGE_ACCESS_KEY_ID:-}" ] || [ -z "${TIGRIS_STORAGE_SECRET_ACCESS_KEY:-}" ]; then' \
    '  echo "[seed] ERROR: TIGRIS_STORAGE_ACCESS_KEY_ID / TIGRIS_STORAGE_SECRET_ACCESS_KEY not provided" >&2' \
    'else' \
    '  # Best-effort cleanup in case a previous run left this bucket behind:' \
    '  # empty it first (the CLI requires empty buckets), then delete it.' \
    '  tigris rm -r "t3://${BUCKET_NAME}/" >/dev/null 2>&1 || true' \
    '  tigris buckets delete "${BUCKET_NAME}" --force >/dev/null 2>&1 || true' \
    '' \
    '  echo "[seed] creating bucket ${BUCKET_NAME}"' \
    '  if ! tigris buckets create "${BUCKET_NAME}"; then' \
    '    echo "[seed] ERROR: failed to create bucket ${BUCKET_NAME}" >&2' \
    '  else' \
    '    SEED_DIR="$(mktemp -d)"' \
    '    for name in a b c; do' \
    '      printf "scratch-%s\\n" "${name}" > "${SEED_DIR}/${name}.tmp"' \
    '      if ! tigris cp "${SEED_DIR}/${name}.tmp" "t3://${BUCKET_NAME}/temp/${name}.tmp"; then' \
    '        echo "[seed] ERROR: failed to upload ${name}.tmp" >&2' \
    '      fi' \
    '    done' \
    '    rm -rf "${SEED_DIR}"' \
    '    echo "[seed] seeding complete for ${BUCKET_NAME}"' \
    '  fi' \
    'fi' \
    '' \
    'echo "[seed] entering idle wait"' \
    'trap : TERM INT' \
    'sleep infinity & wait' \
    > /usr/local/bin/harbor-seed-and-idle.sh && \
    chmod 0755 /usr/local/bin/harbor-seed-and-idle.sh

# Container contents:
#   - always required libs: curl wget ca-certificates git python3 python3-pip python3-pytest bash gnupg
#   - Node.js v24 runtime for the Tigris CLI npm package
#   - @tigrisdata/cli installed globally, providing the `tigris` (and `t3`) command
#   - /home/user/cleanup-task - empty project directory for the task
#   - /etc/profile.d/tigris-auth.sh - login-shell bridge that maps
#     TIGRIS_STORAGE_ACCESS_KEY_ID / TIGRIS_STORAGE_SECRET_ACCESS_KEY into
#     AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION=auto so the
#     `tigris` CLI authenticates against the Harbor-provided credentials.
#   - /usr/local/bin/harbor-seed-and-idle.sh - entrypoint script that creates
#     bucket "harbor-cleanup-${trial_id}" on the live Tigris service and
#     uploads temp/a.tmp, temp/b.tmp, temp/c.tmp before entering idle wait.

CMD ["/bin/bash", "-c", "trap : TERM INT; /usr/local/bin/harbor-seed-and-idle.sh"]
