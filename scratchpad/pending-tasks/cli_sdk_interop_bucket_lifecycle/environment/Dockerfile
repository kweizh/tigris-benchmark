FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g @tigrisdata/cli tsx@4.19.2 typescript@5.6.3 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="any-task-builder"
LABEL Description="Tigris CLI + Storage SDK interop task: Ubuntu 24.04, Node 24, @tigrisdata/cli, and @tigrisdata/storage + tsx pre-installed in /home/user/tigris-task."

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

RUN mkdir -p /home/user/tigris-task && \
    cd /home/user/tigris-task && \
    cat > package.json <<'EOF'
{
  "name": "tigris-task",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "start": "tsx index.ts"
  },
  "dependencies": {
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

# Container contents:
#   - Ubuntu 24.04 base
#   - System packages: curl wget ca-certificates git python3 python3-pip python3-pytest bash gnupg
#   - Node.js v24 and npm
#   - @tigrisdata/cli installed globally, providing the `tigris` command
#   - tsx and typescript installed globally and as local dev deps
#   - /home/user/tigris-task — pre-initialized project with @tigrisdata/storage and tsx in node_modules
#   - /etc/profile.d/tigris-auth.sh — maps TIGRIS_STORAGE_ACCESS_KEY_ID / TIGRIS_STORAGE_SECRET_ACCESS_KEY
#     into AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION=auto so the Tigris CLI authenticates.

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
