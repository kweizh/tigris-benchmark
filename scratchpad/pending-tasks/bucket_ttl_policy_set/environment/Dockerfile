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
LABEL Description="Tigris CLI environment for setting a 7-day object expiration TTL on a bucket via @tigrisdata/cli."

RUN mkdir -p /home/user && chmod 0755 /home/user

RUN mkdir -p /home/user/ttl-task && chmod 0755 /home/user/ttl-task

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

# Container contents:
#   - always required libs: curl wget ca-certificates git python3 python3-pip python3-pytest bash gnupg
#   - Node.js v24 runtime for the Tigris CLI npm package
#   - @tigrisdata/cli installed globally, providing the `tigris` (and `t3`) command
#   - /home/user/ttl-task - empty project directory for the task
#   - /etc/profile.d/tigris-auth.sh - login-shell bridge that maps
#     TIGRIS_STORAGE_ACCESS_KEY_ID / TIGRIS_STORAGE_SECRET_ACCESS_KEY into
#     AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION=auto so the
#     `tigris` CLI authenticates against the Harbor-provided credentials.

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
