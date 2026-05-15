FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm i -g @tigrisdata/cli && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="any-task-builder"
LABEL Description="Ubuntu 24.04 + Node.js 24 + Tigris CLI for creating a snapshot-enabled bucket via 'tigris buckets create --enable-snapshots'."

RUN mkdir -p /home/user/tigris-task && chmod 0755 /home/user/tigris-task

# Container contents:
#   - System libs: curl wget ca-certificates git python3 python3-pip python3-pytest bash gnupg
#   - Node.js v24 (from NodeSource) and npm
#   - Tigris CLI installed globally via `npm i -g @tigrisdata/cli` (binary: `tigris`)
#   - /home/user/tigris-task: working project directory for the task
#
# The agent at runtime reads /logs/artifacts/trial_id and the TIGRIS_STORAGE_* env vars
# to create a snapshot-enabled bucket named harbor-snap-${trial_id} via:
#   tigris buckets create harbor-snap-${trial_id} --enable-snapshots

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
