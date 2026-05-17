FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash \
        unzip jq && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    pip3 install --break-system-packages --no-cache-dir awscli && \
    npm i -g @tigrisdata/cli @tigrisdata/agent-kit && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="any-task-builder"
LABEL Description="Tigris Agent Kit task environment with Node.js v24, @tigrisdata/cli, @tigrisdata/agent-kit, aws-cli, and a pre-initialized chained-ckpt project."

RUN mkdir -p /home/user/chained-ckpt && \
    cd /home/user/chained-ckpt && \
    cat >package.json <<'EOF'
{
  "name": "chained-ckpt",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "start": "tsx index.ts"
  },
  "dependencies": {
    "@tigrisdata/agent-kit": "^0.1.0",
    "@tigrisdata/storage": "^0.1.0",
    "@aws-sdk/client-s3": "^3.658.0"
  },
  "devDependencies": {
    "tsx": "^4.19.0",
    "typescript": "^5.6.0"
  }
}
EOF

RUN cat >/home/user/chained-ckpt/tsconfig.json <<'EOF'
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

# Container contents:
#   - Ubuntu 24.04 base
#   - Node.js v24 + npm + npx
#   - @tigrisdata/cli (tigris) and @tigrisdata/agent-kit installed globally
#   - aws-cli for S3-compatible object verification against Tigris
#   - /home/user/chained-ckpt: project scaffold with package.json, tsconfig.json

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
