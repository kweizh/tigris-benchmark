FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm i -g @tigrisdata/cli && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="any-task-builder"
LABEL Description="Tigris Agent Kit workspace TTL provisioning task environment (Ubuntu 24.04, Node.js v24, tigris CLI, @tigrisdata/agent-kit project)."

RUN mkdir -p /home/user/ttl-workspace && \
    cd /home/user/ttl-workspace && \
    cat >package.json <<'EOF'
{
  "name": "ttl-workspace",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "start": "tsx index.ts"
  },
  "dependencies": {
    "@tigrisdata/agent-kit": "^0.1.0"
  },
  "devDependencies": {
    "tsx": "^4.19.0",
    "typescript": "^5.6.0",
    "@types/node": "^22.0.0"
  }
}
EOF

RUN cd /home/user/ttl-workspace && \
    npm install --no-audit --no-fund --loglevel=error

# Container contents:
#   - Base: ubuntu:24.04
#   - System tools: curl wget ca-certificates git python3 python3-pip python3-pytest bash
#   - Node.js v24 (NodeSource)
#   - @tigrisdata/cli installed globally (provides `tigris` binary)
#   - /home/user/ttl-workspace/package.json declaring @tigrisdata/agent-kit, tsx, typescript
#   - /home/user/ttl-workspace/node_modules with @tigrisdata/agent-kit and tsx pre-installed locally
#   - No index.ts or workspace.json yet — those are created by the user task

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
