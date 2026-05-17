FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash \
        jq unzip && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    pip3 install --break-system-packages --no-cache-dir awscli && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="any-task-builder"
LABEL Description="Tigris Agent Kit restored-fork validation task: Node.js v24, AWS CLI, jq, and a pre-initialized /home/user/restore-validate project with @tigrisdata/agent-kit, @tigrisdata/cli, @aws-sdk/client-s3, and tsx installed locally. Ships an executable setup.sh that prepares archive-bucket (with a uploaded manifest.json and a fresh checkpoint) at task start."

# Pre-create the project directory with package.json, tsconfig.json, and
# a project-local node_modules containing the required packages. The user
# must author /home/user/restore-validate/index.ts themselves.
RUN mkdir -p /home/user/restore-validate && \
    cd /home/user/restore-validate && \
    cat >package.json <<'EOF'
{
  "name": "restore-validate",
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

RUN cd /home/user/restore-validate && \
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

RUN cd /home/user/restore-validate && npm install --no-audit --no-fund && \
    ln -sf /home/user/restore-validate/node_modules/.bin/tigris /usr/local/bin/tigris

# Helper ESM script invoked by setup.sh: takes a checkpoint of archive-bucket
# using the agent-kit `checkpoint` function and prints the resulting
# snapshotId on a single line of stdout.
RUN cat >/home/user/restore-validate/setup-checkpoint.mjs <<'EOF'
import { checkpoint } from "@tigrisdata/agent-kit";

const bucket = process.argv[2];
if (!bucket) {
  console.error("usage: node setup-checkpoint.mjs <bucket>");
  process.exit(2);
}

const { data, error } = await checkpoint(bucket, { name: "initial" });
if (error || !data) {
  console.error("checkpoint failed:", error?.message ?? "no data returned");
  process.exit(1);
}
process.stdout.write(data.snapshotId + "\n");
EOF

# Helper ESM script invoked by setup.sh: uploads a local file to a bucket
# using the AWS S3 SDK pointed at the Tigris endpoint. Reads admin
# credentials from the standard Tigris env vars.
RUN cat >/home/user/restore-validate/setup-upload.mjs <<'EOF'
import { readFileSync } from "node:fs";
import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";

const [bucket, key, path] = process.argv.slice(2);
if (!bucket || !key || !path) {
  console.error("usage: node setup-upload.mjs <bucket> <key> <path>");
  process.exit(2);
}

const s3 = new S3Client({
  region: "auto",
  endpoint: process.env.TIGRIS_STORAGE_ENDPOINT || "https://t3.storage.dev",
  credentials: {
    accessKeyId: process.env.TIGRIS_STORAGE_ACCESS_KEY_ID,
    secretAccessKey: process.env.TIGRIS_STORAGE_SECRET_ACCESS_KEY,
  },
});

await s3.send(
  new PutObjectCommand({
    Bucket: bucket,
    Key: key,
    Body: readFileSync(path),
    ContentType: "application/json",
  }),
);

console.log(`uploaded ${path} -> s3://${bucket}/${key}`);
EOF

# Write the setup.sh helper that prepares the bucket and metadata files at
# task start. It must be executed at runtime because admin Tigris
# credentials are only available in the running container.
RUN cat >/home/user/restore-validate/setup.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

cd /home/user/restore-validate

BUCKET="archive-bucket"
FORK="validation-fork"
ENDPOINT="${TIGRIS_STORAGE_ENDPOINT:-https://t3.storage.dev}"

if [[ -z "${TIGRIS_STORAGE_ACCESS_KEY_ID:-}" || -z "${TIGRIS_STORAGE_SECRET_ACCESS_KEY:-}" ]]; then
  echo "ERROR: TIGRIS_STORAGE_ACCESS_KEY_ID and TIGRIS_STORAGE_SECRET_ACCESS_KEY must be set." >&2
  exit 1
fi

echo "[setup] Configuring tigris CLI..."
tigris configure \
  --access-key "${TIGRIS_STORAGE_ACCESS_KEY_ID}" \
  --access-secret "${TIGRIS_STORAGE_SECRET_ACCESS_KEY}" \
  --endpoint "${ENDPOINT}"

echo "[setup] Removing pre-existing fork ${FORK} (if present)..."
tigris buckets delete "${FORK}" --yes >/dev/null 2>&1 || true

echo "[setup] Removing pre-existing source bucket ${BUCKET} (if present)..."
tigris buckets delete "${BUCKET}" --yes >/dev/null 2>&1 || true

# Wait briefly for deletion to propagate.
sleep 3

echo "[setup] Creating bucket ${BUCKET} with snapshots enabled..."
tigris buckets create "${BUCKET}" --enable-snapshots

echo "[setup] Writing manifest.json..."
cat >manifest.json <<'MANIFEST'
{
  "name": "Tigris Restore Validation Manifest",
  "version": "1.0.0",
  "artifacts": [
    {"id": "alpha", "path": "data/alpha.bin", "size": 1024},
    {"id": "beta",  "path": "data/beta.bin",  "size": 2048},
    {"id": "gamma", "path": "data/gamma.bin", "size": 4096}
  ],
  "createdAt": "2024-01-01T00:00:00Z"
}
MANIFEST

echo "[setup] Computing manifest SHA256..."
sha256sum manifest.json | awk '{print $1}' >expected_sha256.txt
echo "[setup] expected_sha256=$(cat expected_sha256.txt)"

echo "[setup] Uploading manifest.json to ${BUCKET}..."
node setup-upload.mjs "${BUCKET}" "manifest.json" "manifest.json"

# Give the upload a moment to be durable before snapshotting.
sleep 2

echo "[setup] Taking checkpoint of ${BUCKET}..."
SNAPSHOT_ID="$(node setup-checkpoint.mjs "${BUCKET}")"
if [[ -z "${SNAPSHOT_ID}" ]]; then
  echo "ERROR: checkpoint returned empty snapshotId" >&2
  exit 1
fi
echo "${SNAPSHOT_ID}" >snapshot_id.txt
echo "[setup] snapshot_id=${SNAPSHOT_ID}"

echo "[setup] Done."
EOF

RUN chmod +x /home/user/restore-validate/setup.sh

# Container contents:
#   - Ubuntu 24.04 base with curl, wget, ca-certificates, git, python3,
#     python3-pip, python3-pytest, bash, jq, and the AWS CLI (used by the
#     verifier for independent re-download of the restored object).
#   - Node.js v24 installed via NodeSource.
#   - /home/user/restore-validate — pre-initialized TypeScript project with
#     package.json, tsconfig.json, and node_modules containing
#     @tigrisdata/agent-kit, @tigrisdata/cli, @aws-sdk/client-s3, tsx, and
#     typescript. index.ts is intentionally absent — the user creates it.
#   - tigris CLI symlinked to /usr/local/bin/tigris.
#   - setup.sh (executable) and its two ESM helpers (setup-upload.mjs,
#     setup-checkpoint.mjs) that prepare the archive-bucket, upload
#     manifest.json, take a checkpoint, and write snapshot_id.txt /
#     expected_sha256.txt at task start.

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
