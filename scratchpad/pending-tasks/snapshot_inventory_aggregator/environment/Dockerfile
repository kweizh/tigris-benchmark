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

# Ship the setup.sh helper that recreates the six buckets and their
# snapshots at task start. It must run at runtime (not build time) because
# the Tigris admin credentials are only available inside the running
# container.
RUN cat >/home/user/inv/setup.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

ENDPOINT="${TIGRIS_STORAGE_ENDPOINT:-https://t3.storage.dev}"

if [[ -z "${TIGRIS_STORAGE_ACCESS_KEY_ID:-}" || -z "${TIGRIS_STORAGE_SECRET_ACCESS_KEY:-}" ]]; then
  echo "ERROR: TIGRIS_STORAGE_ACCESS_KEY_ID and TIGRIS_STORAGE_SECRET_ACCESS_KEY must be set." >&2
  exit 1
fi

echo "[setup] Configuring tigris CLI..."
tigris configure \
  --access-key "${TIGRIS_STORAGE_ACCESS_KEY_ID}" \
  --access-secret "${TIGRIS_STORAGE_SECRET_ACCESS_KEY}" \
  --endpoint "${ENDPOINT}"

ALL_BUCKETS=(inv-bench-a inv-bench-b inv-bench-c inv-other-x inv-other-y inv-other-z)

echo "[setup] Tearing down any pre-existing buckets..."
for bucket in "${ALL_BUCKETS[@]}"; do
  tigris buckets delete "${bucket}" --yes >/dev/null 2>&1 || true
done

# Let deletions propagate before recreating.
sleep 3

echo "[setup] Creating snapshot-enabled bucket inv-bench-a (2 snapshots)..."
tigris buckets create inv-bench-a --enable-snapshots
tigris snapshots take inv-bench-a inv-bench-a-s1
sleep 1
tigris snapshots take inv-bench-a inv-bench-a-s2
sleep 1

echo "[setup] Creating snapshot-enabled bucket inv-bench-b (1 snapshot)..."
tigris buckets create inv-bench-b --enable-snapshots
tigris snapshots take inv-bench-b inv-bench-b-s1
sleep 1

echo "[setup] Creating snapshot-enabled bucket inv-bench-c (3 snapshots)..."
tigris buckets create inv-bench-c --enable-snapshots
tigris snapshots take inv-bench-c inv-bench-c-s1
sleep 1
tigris snapshots take inv-bench-c inv-bench-c-s2
sleep 1
tigris snapshots take inv-bench-c inv-bench-c-s3
sleep 1

echo "[setup] Creating distractor bucket inv-other-x (snapshot-enabled with 2 snapshots that must be ignored)..."
tigris buckets create inv-other-x --enable-snapshots
tigris snapshots take inv-other-x inv-other-x-s1
sleep 1
tigris snapshots take inv-other-x inv-other-x-s2
sleep 1

echo "[setup] Creating distractor bucket inv-other-y (no snapshots)..."
tigris buckets create inv-other-y

echo "[setup] Creating distractor bucket inv-other-z (no snapshots)..."
tigris buckets create inv-other-z

echo "[setup] Done. Final bucket list:"
tigris buckets list --format json
EOF

RUN chmod +x /home/user/inv/setup.sh

# Container contents:
#   - Ubuntu 24.04 base with curl, wget, ca-certificates, git, python3,
#     python3-pip, python3-pytest, bash, gnupg, and jq.
#   - Node.js v24 installed via NodeSource.
#   - @tigrisdata/cli installed globally so `tigris` is on PATH.
#   - /etc/profile.d/tigris-auth.sh — login-shell bridge mapping
#     TIGRIS_STORAGE_ACCESS_KEY_ID / TIGRIS_STORAGE_SECRET_ACCESS_KEY into
#     the AWS_* variables used by the Tigris CLI.
#   - /home/user/inv — pre-initialized project directory with package.json
#     and node_modules containing @tigrisdata/agent-kit, plus an executable
#     setup.sh that provisions the six buckets and their snapshots at task
#     start (the build itself does not have Tigris credentials).
#   - /home/user/inv/index.js and /home/user/inv/inventory.json are
#     intentionally absent — the user creates them as part of the task.

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
