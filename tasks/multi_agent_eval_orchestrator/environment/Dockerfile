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
LABEL Description="Tigris Agent Kit multi-agent eval orchestrator task: Node.js v24 with a pre-initialized /home/user/orchestrator project that has @tigrisdata/agent-kit, @tigrisdata/cli, @aws-sdk/client-s3, and tsx installed locally, plus baked seed prompts under /opt/harbor-seed."

# Bake the canonical seed prompt corpus into /opt/harbor-seed so the verifier
# and the runtime setup script can both reference the exact prompt bytes.
# These files MUST NOT have trailing newlines so that the reversed-string
# answer assertions are reproducible.
RUN mkdir -p /opt/harbor-seed/prompts && \
    printf '%s' '{"id":"p1","prompt":"hello"}'  > /opt/harbor-seed/prompts/p1.json && \
    printf '%s' '{"id":"p2","prompt":"world"}'  > /opt/harbor-seed/prompts/p2.json && \
    printf '%s' '{"id":"p3","prompt":"tigris"}' > /opt/harbor-seed/prompts/p3.json

# Pre-create the project directory with package.json and tsconfig.json. The
# user must author /home/user/orchestrator/index.ts themselves.
RUN mkdir -p /home/user/orchestrator && \
    cd /home/user/orchestrator && \
    cat >package.json <<'EOF'
{
  "name": "orchestrator",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "dependencies": {
    "@aws-sdk/client-s3": "^3.658.0",
    "@tigrisdata/agent-kit": "^0.1.0",
    "@tigrisdata/cli": "2.18.0",
    "tsx": "^4.19.0",
    "typescript": "^5.6.0"
  }
}
EOF

RUN cd /home/user/orchestrator && \
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

# Helper Node script that uploads the seeded prompts into the gold dataset
# bucket. Uses an absolute require path so it works regardless of cwd or
# package.json type. Lives outside the project directory to avoid leaking
# setup internals into the user's workspace.
RUN cat >/opt/harbor-seed/upload.cjs <<'EOF'
const {
  S3Client,
  PutObjectCommand,
} = require("/home/user/orchestrator/node_modules/@aws-sdk/client-s3");
const { readFileSync } = require("fs");
const path = require("path");

const SEED_DIR = "/opt/harbor-seed/prompts";
const BUCKET = "gold-eval-dataset";

async function main() {
  const accessKeyId = process.env.TIGRIS_STORAGE_ACCESS_KEY_ID;
  const secretAccessKey = process.env.TIGRIS_STORAGE_SECRET_ACCESS_KEY;
  if (!accessKeyId || !secretAccessKey) {
    throw new Error(
      "TIGRIS_STORAGE_ACCESS_KEY_ID and TIGRIS_STORAGE_SECRET_ACCESS_KEY must be set."
    );
  }
  const client = new S3Client({
    region: "auto",
    endpoint: "https://t3.storage.dev",
    credentials: { accessKeyId, secretAccessKey },
  });
  for (const name of ["p1.json", "p2.json", "p3.json"]) {
    const body = readFileSync(path.join(SEED_DIR, name));
    await client.send(
      new PutObjectCommand({
        Bucket: BUCKET,
        Key: "prompts/" + name,
        Body: body,
        ContentType: "application/json",
      })
    );
    console.log("uploaded prompts/" + name);
  }
}

main().catch((err) => {
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
});
EOF

# Setup script invoked at task start. Provisions an empty `gold-eval-dataset`
# bucket with snapshots enabled and uploads the three seeded prompt files.
# Best-effort cleanup of any leftover fork / writer buckets from a prior run.
RUN cat >/home/user/orchestrator/setup.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/user/orchestrator"
BUCKET_NAME="gold-eval-dataset"

if [ -x "/usr/local/bin/tigris" ]; then
  TIGRIS_BIN="/usr/local/bin/tigris"
elif command -v tigris >/dev/null 2>&1; then
  TIGRIS_BIN="$(command -v tigris)"
elif [ -x "${PROJECT_DIR}/node_modules/.bin/tigris" ]; then
  TIGRIS_BIN="${PROJECT_DIR}/node_modules/.bin/tigris"
else
  echo "Tigris CLI not found." >&2
  exit 1
fi

if [ -z "${TIGRIS_STORAGE_ACCESS_KEY_ID:-}" ] || [ -z "${TIGRIS_STORAGE_SECRET_ACCESS_KEY:-}" ]; then
  echo "TIGRIS_STORAGE_ACCESS_KEY_ID and TIGRIS_STORAGE_SECRET_ACCESS_KEY must be set." >&2
  exit 1
fi

export AWS_ACCESS_KEY_ID="${TIGRIS_STORAGE_ACCESS_KEY_ID}"
export AWS_SECRET_ACCESS_KEY="${TIGRIS_STORAGE_SECRET_ACCESS_KEY}"
export AWS_REGION="auto"

# Best-effort cleanup of any stale buckets from a prior partial run so the
# task starts with the expected initial state.
for name in "${BUCKET_NAME}" \
            "eval-attempt-0" "eval-attempt-1" "eval-attempt-2" \
            "eval-writer-0" "eval-writer-1" "eval-writer-2"; do
  "${TIGRIS_BIN}" buckets delete "${name}" --force >/dev/null 2>&1 || true
done

"${TIGRIS_BIN}" buckets create "${BUCKET_NAME}" --enable-snapshots

# Upload the three canonical prompt files from the baked seed corpus.
node /opt/harbor-seed/upload.cjs

echo "setup.sh: gold-eval-dataset ready with prompts/{p1,p2,p3}.json."
EOF

RUN chmod +x /home/user/orchestrator/setup.sh

RUN cd /home/user/orchestrator && npm install --no-audit --no-fund && \
    ln -sf /home/user/orchestrator/node_modules/.bin/tigris /usr/local/bin/tigris

# Container contents:
#   - Ubuntu 24.04 base with curl, wget, ca-certificates, git, python3,
#     python3-pip, python3-pytest, bash.
#   - Node.js v24 installed via NodeSource.
#   - /home/user/orchestrator — TypeScript project pre-initialized with
#     package.json, tsconfig.json, and node_modules containing
#     @tigrisdata/agent-kit, @tigrisdata/cli, @aws-sdk/client-s3, tsx, and
#     typescript. index.ts is intentionally absent — the user creates it.
#   - /home/user/orchestrator/setup.sh — executable script that provisions
#     the empty `gold-eval-dataset` bucket with snapshots enabled and uploads
#     the three seeded prompts at task start.
#   - /opt/harbor-seed/prompts/{p1,p2,p3}.json — canonical seed prompt files
#     with no trailing newlines, used by setup.sh for the upload and by the
#     verifier for computing the expected reversed answers.
#   - /opt/harbor-seed/upload.cjs — Node helper used by setup.sh to upload.
#   - tigris CLI symlinked to /usr/local/bin/tigris.

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
