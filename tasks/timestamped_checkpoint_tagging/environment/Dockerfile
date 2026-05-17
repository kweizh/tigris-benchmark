FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash \
        unzip jq && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm i -g @tigrisdata/cli@2.18.0 @tigrisdata/agent-kit && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="any-task-builder"
LABEL Description="Tigris Agent Kit task environment with Node.js v24, @tigrisdata/cli, @tigrisdata/agent-kit, and a pre-initialized ckpt-tag project containing build_id.txt and a setup.sh that provisions the snapshot-enabled bucket."

RUN mkdir -p /home/user/ckpt-tag && \
    cd /home/user/ckpt-tag && \
    cat >package.json <<'EOF'
{
  "name": "ckpt-tag",
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
    "typescript": "^5.6.0"
  }
}
EOF

RUN cat >/home/user/ckpt-tag/tsconfig.json <<'EOF'
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true
  }
}
EOF

RUN printf 'v42\n' > /home/user/ckpt-tag/build_id.txt

# Container contents:
#   - Ubuntu 24.04 base
#   - Node.js v24 + npm + npx
#   - @tigrisdata/cli (tigris) and @tigrisdata/agent-kit installed globally
#   - /home/user/ckpt-tag: project scaffold with package.json, tsconfig.json, build_id.txt (=v42)

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
