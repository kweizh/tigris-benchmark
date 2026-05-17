FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="any-task-builder"
LABEL Description="Tigris Agent Kit isolated_fork_writer_audit task: Node.js v24 with a pre-initialized /home/user/isolation project containing @tigrisdata/agent-kit, @tigrisdata/cli, @aws-sdk/client-s3, tsx, and typescript installed locally, plus a setup.sh that provisions the gold-source bucket with seed files at task start."

# Pre-create the project directory with package.json, tsconfig.json, and a
# local node_modules containing the required packages. The user must author
# /home/user/isolation/index.ts themselves.
RUN mkdir -p /home/user/isolation && \
    cd /home/user/isolation && \
    cat >package.json <<'EOF'
{
  "name": "isolation",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "dependencies": {
    "@aws-sdk/client-s3": "^3.658.0",
    "@tigrisdata/agent-kit": "^0.1.0",
    "@tigrisdata/cli": "^1.0.0",
    "tsx": "^4.19.0",
    "typescript": "^5.6.0"
  }
}
EOF

RUN cd /home/user/isolation && \
    cat >tsconfig.json <<'EOF'
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "Bundler",
    "esModuleInterop": true,
    "strict": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "allowSyntheticDefaultImports": true,
    "forceConsistentCasingInFileNames": true,
    "outDir": "dist"
  },
  "include": ["*.ts"]
}
EOF

RUN cd /home/user/isolation && npm install --no-audit --no-fund && \
    ln -sf /home/user/isolation/node_modules/.bin/tigris /usr/local/bin/tigris

# Container contents:
#   - Ubuntu 24.04 base with curl, wget, ca-certificates, git, python3,
#     python3-pip, python3-pytest, bash.
#   - Node.js v24 installed via NodeSource.
#   - /home/user/isolation — TypeScript project pre-initialized with
#     package.json, tsconfig.json, and node_modules containing
#     @tigrisdata/agent-kit, @tigrisdata/cli, @aws-sdk/client-s3, tsx, and
#     typescript. index.ts is intentionally absent — the user must create it.
#   - tigris CLI symlinked to /usr/local/bin/tigris.

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
