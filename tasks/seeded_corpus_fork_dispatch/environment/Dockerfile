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
LABEL Description="Tigris Agent Kit seeded-corpus fork dispatch task: Node.js v24 with a pre-initialized /home/user/seeded-fork project that has @tigrisdata/agent-kit, @tigrisdata/cli, @aws-sdk/client-s3, and tsx installed locally, plus three local seed files in data/."

# Pre-create the project directory with package.json, tsconfig.json, and a
# project-local node_modules containing the required packages. The user must
# author /home/user/seeded-fork/index.ts themselves.
RUN mkdir -p /home/user/seeded-fork && \
    cd /home/user/seeded-fork && \
    cat >package.json <<'EOF'
{
  "name": "seeded-fork",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "dependencies": {
    "@aws-sdk/client-s3": "^3.658.0",
    "@tigrisdata/agent-kit": "^0.1.0",
    "@tigrisdata/cli": "^2.18.0",
    "tsx": "^4.19.0",
    "typescript": "^5.6.0"
  }
}
EOF

RUN cd /home/user/seeded-fork && \
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

# Pre-create the local seed corpus files the user will upload to Tigris.
RUN mkdir -p /home/user/seeded-fork/data && \
    printf 'alpha contents for the corpus seed file a.\n' >/home/user/seeded-fork/data/a.txt && \
    printf 'bravo contents for the corpus seed file b.\n' >/home/user/seeded-fork/data/b.txt && \
    printf 'charlie contents for the corpus seed file c.\n' >/home/user/seeded-fork/data/c.txt

RUN cd /home/user/seeded-fork && npm install --no-audit --no-fund && \
    ln -sf /home/user/seeded-fork/node_modules/.bin/tigris /usr/local/bin/tigris

# Container contents:
#   - Ubuntu 24.04 base with curl, wget, ca-certificates, git, python3,
#     python3-pip, python3-pytest, bash.
#   - Node.js v24 installed via NodeSource.
#   - /home/user/seeded-fork — TypeScript project pre-initialized with
#     package.json, tsconfig.json, and node_modules containing
#     @tigrisdata/agent-kit, @tigrisdata/cli, @aws-sdk/client-s3, tsx, and
#     typescript. index.ts is intentionally absent — the user creates it.
#   - /home/user/seeded-fork/data/{a,b,c}.txt — local seed corpus files.
#   - tigris CLI symlinked to /usr/local/bin/tigris.

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
