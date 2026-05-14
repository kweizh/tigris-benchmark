FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash jq gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g @tigrisdata/cli && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

LABEL Author="any-task-builder"
LABEL Description="Tigris CLI end-to-end lifecycle orchestrator environment: Node.js v24, @tigrisdata/cli installed globally, jq for JSON parsing, /home/user/lifecycle project with a pre-populated local.txt seed file, and a profile.d auth bridge that maps Harbor's TIGRIS_STORAGE_* credentials onto the AWS-compatible variables the tigris CLI consumes."

RUN mkdir -p /home/user && chmod 0755 /home/user

# Pre-create the project directory and the local seed file used by the task.
RUN mkdir -p /home/user/lifecycle && \
    chmod 0755 /home/user/lifecycle && \
    printf '%s\n' 'hello from the tigris lifecycle task' > /home/user/lifecycle/local.txt && \
    chmod 0644 /home/user/lifecycle/local.txt

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

# Container contents:
#   - Ubuntu 24.04 base with curl, wget, ca-certificates, git, python3,
#     python3-pip, python3-pytest, bash, gnupg, and jq.
#   - Node.js v24 installed via NodeSource.
#   - @tigrisdata/cli installed globally so `tigris` is on PATH.
#   - /home/user/lifecycle/ — pre-created project directory with a seed file
#     local.txt that the agent's script must upload as object 'seed.txt'.
#   - /etc/profile.d/tigris-auth.sh — login-shell bridge that maps
#     TIGRIS_STORAGE_ACCESS_KEY_ID / TIGRIS_STORAGE_SECRET_ACCESS_KEY into
#     AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION=auto so the
#     `tigris` CLI authenticates against the Harbor-provided credentials.
#   - run.sh and snapshots.txt are intentionally absent — the agent creates them.

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
