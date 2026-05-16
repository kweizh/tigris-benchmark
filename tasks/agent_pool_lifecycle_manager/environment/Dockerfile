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
LABEL Description="Tigris Agent Kit agent-pool lifecycle manager task environment (Ubuntu 24.04, Node.js v24, tigris CLI, @tigrisdata/agent-kit + @aws-sdk/client-s3 project)."

RUN mkdir -p /home/user/pool && \
    cd /home/user/pool && \
    cat >package.json <<'EOF'
{
  "name": "pool",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "cli": "tsx cli.ts"
  },
  "dependencies": {
    "@tigrisdata/agent-kit": "^0.1.0",
    "@aws-sdk/client-s3": "^3.654.0"
  },
  "devDependencies": {
    "tsx": "^4.19.0",
    "typescript": "^5.6.0",
    "@types/node": "^22.0.0"
  }
}
EOF

RUN cd /home/user/pool && \
    cat >tsconfig.json <<'EOF'
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "esModuleInterop": true,
    "strict": false,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "allowSyntheticDefaultImports": true,
    "types": ["node"]
  },
  "include": ["*.ts"]
}
EOF

RUN cd /home/user/pool && \
    npm install --no-audit --no-fund --loglevel=error

# Container contents:
#   - Base: ubuntu:24.04
#   - System tools: curl wget ca-certificates git python3 python3-pip python3-pytest bash
#   - Node.js v24 (NodeSource)
#   - @tigrisdata/cli installed globally (provides `tigris` binary)
#   - /home/user/pool/package.json declaring @tigrisdata/agent-kit, @aws-sdk/client-s3, tsx, typescript, @types/node
#   - /home/user/pool/tsconfig.json with ES2022 + ESM bundler resolution
#   - /home/user/pool/node_modules with all dependencies pre-installed locally
#   - No manager.ts, cli.ts, pool-state.json, or scenario.log yet — those are produced by the user task

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
