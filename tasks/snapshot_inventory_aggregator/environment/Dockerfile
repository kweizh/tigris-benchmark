FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash gnupg jq && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g @tigrisdata/cli && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

LABEL Author="any-task-builder"
LABEL Description="Tigris snapshot-inventory aggregator task environment: Node.js v24, the @tigrisdata/cli installed globally, a pre-initialized /home/user/inv project containing @tigrisdata/agent-kit and an executable setup.sh that recreates six buckets (three with the inv-bench- prefix plus three unrelated buckets) at task start."

RUN mkdir -p /home/user && chmod 0755 /home/user

# Bridge the Harbor-injected TIGRIS_STORAGE_* credentials to the AWS-compatible
# environment variables that the `tigris` CLI consumes. The script is read by
# login shells and is also sourced from /root/.bashrc for interactive shells.
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

# Pre-create the project directory with a package.json that pulls in the
# @tigrisdata/agent-kit dependency. The user does not have to import it for
# this particular task, but the broader benchmark exercises the agent kit
# library, so its presence is part of the expected initial state.
RUN mkdir -p /home/user/inv && \
    cd /home/user/inv && \
    cat >package.json <<'EOF'
{
  "name": "inv",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "dependencies": {
    "@tigrisdata/agent-kit": "^0.1.0"
  }
}
EOF

RUN cd /home/user/inv && npm install --no-audit --no-fund

# Container contents:
#   - Ubuntu 24.04 base with curl, wget, ca-certificates, git, python3,
#     python3-pip, python3-pytest, bash, gnupg, and jq.
#   - Node.js v24 installed via NodeSource.
#   - @tigrisdata/cli installed globally so `tigris` is on PATH.
#   - /etc/profile.d/tigris-auth.sh — login-shell bridge mapping
#     TIGRIS_STORAGE_ACCESS_KEY_ID / TIGRIS_STORAGE_SECRET_ACCESS_KEY into
#     the AWS_* variables used by the Tigris CLI.
#   - /home/user/inv — pre-initialized project directory with package.json
#     and node_modules containing @tigrisdata/agent-kit.
#   - /home/user/inv/index.js and /home/user/inv/inventory.json are
#     intentionally absent — the user creates them as part of the task.

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
