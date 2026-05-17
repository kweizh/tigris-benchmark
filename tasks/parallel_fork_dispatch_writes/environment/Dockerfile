FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm i -g @tigrisdata/cli tsx@4.19.2 typescript@5.6.3 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

LABEL Author="any-task-builder"
LABEL Description="Tigris Agent Kit environment that seeds a snapshot-enabled source bucket with seed/dataset.txt at container start so the agent can fork it 3x in parallel via @tigrisdata/agent-kit."

RUN mkdir -p /home/user && chmod 0755 /home/user

# Pre-create the project working directory and pre-install the agent-kit /
# storage SDK + tsx dev dependency. The agent only needs to author run.ts
# and execute it.
RUN mkdir -p /home/user/tigris-task && \
    cd /home/user/tigris-task && \
    cat > package.json <<'EOF'
{
  "name": "tigris-task",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "start": "tsx run.ts"
  },
  "dependencies": {
    "@tigrisdata/agent-kit": "^0.1.0",
    "@tigrisdata/storage": "^3.0.0"
  },
  "devDependencies": {
    "tsx": "^4.19.2",
    "typescript": "^5.6.3",
    "@types/node": "^22.7.5"
  }
}
EOF

RUN cd /home/user/tigris-task && \
    cat > tsconfig.json <<'EOF'
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "Bundler",
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": false,
    "outDir": "dist"
  },
  "include": ["*.ts"]
}
EOF

RUN cd /home/user/tigris-task && npm install --no-audit --no-fund

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
#   - always required libs: curl wget ca-certificates git python3 python3-pip python3-pytest bash gnupg
#   - Node.js v24 runtime for the Tigris CLI + npm packages
#   - @tigrisdata/cli installed globally
#   - tsx and typescript installed globally so the agent can run TypeScript directly
#   - /home/user/tigris-task — project pre-initialized with @tigrisdata/agent-kit,
#     @tigrisdata/storage, and tsx installed locally (npm install run at build time)
#   - tsconfig.json for ES2022 module compilation
#   - /etc/profile.d/tigris-auth.sh — login-shell bridge mapping TIGRIS_STORAGE_*
#     into AWS_* so the `tigris` CLI authenticates against Harbor credentials

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
