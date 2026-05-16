# Upload an Object Using Scoped Workspace Credentials

## Background
Tigris Agent Kit (`@tigrisdata/agent-kit`) provisions per-agent buckets ("workspaces") with their own scoped IAM credentials. The safest way for an agent to write into its workspace is to use those scoped credentials (`Editor` role) with an S3-compatible client — never the long-lived admin keys. Because IAM key creation can silently fail after the bucket is created, the script must explicitly verify that `workspace.credentials` is present before using it.

## Requirements
- Write a TypeScript script at `/home/user/scoped-upload/index.ts` that:
  1. Calls `createWorkspace` from `@tigrisdata/agent-kit` to provision a workspace named `scoped-upload-ws` with `credentials: { role: "Editor" }`.
  2. Validates that both the bucket and scoped credentials are present in the response (throw a descriptive error otherwise).
  3. Uses the AWS SDK for JavaScript v3 (`@aws-sdk/client-s3`) — configured with ONLY the scoped credentials from the workspace (NOT the admin `TIGRIS_STORAGE_ACCESS_KEY_ID`/`TIGRIS_STORAGE_SECRET_ACCESS_KEY` env vars) and the Tigris endpoint (`https://t3.storage.dev`, region `auto`) — to `PutObject` a file with key `greeting.txt` and body `hello scoped` into the workspace bucket.
  4. Tears down the workspace at the end with `teardownWorkspace` so the bucket and scoped key are cleaned up.
  5. On success, prints a final line `SCOPED_UPLOAD_OK <bucket-name>` to stdout (where `<bucket-name>` is the workspace bucket name).

## Implementation Guide
1. Change into the project directory at `/home/user/scoped-upload`. The project already has `package.json`, `tsconfig.json`, and an installed local `node_modules` containing `@tigrisdata/agent-kit`, `@tigrisdata/cli`, `@aws-sdk/client-s3`, and `tsx`. You only need to create `index.ts`.
2. Import `createWorkspace`, `teardownWorkspace` from `@tigrisdata/agent-kit` and `S3Client`, `PutObjectCommand` from `@aws-sdk/client-s3`.
3. Create the workspace, then construct an `S3Client` with the scoped `accessKeyId`/`secretAccessKey`, `region: "auto"`, and `endpoint: "https://t3.storage.dev"`.
4. `PutObject` with `Bucket: workspace.bucket`, `Key: "greeting.txt"`, `Body: "hello scoped"`.
5. Always call `teardownWorkspace(workspace)` (even on failure) using a `try`/`finally` block so the bucket and scoped key are removed.
6. Run the script using `npx tsx index.ts`, capturing stdout and stderr to `/home/user/scoped-upload/output.log`. The script must exit with status 0 on success.

## Constraints
- Project path: `/home/user/scoped-upload`
- Log file: `/home/user/scoped-upload/output.log`
- Use ONLY the scoped workspace credentials with the AWS SDK upload — do not pass the admin Tigris env vars to the `S3Client` constructor.
- Do not modify `package.json`, `tsconfig.json`, or `node_modules`.
- Do not invent another workspace name — it must be exactly `scoped-upload-ws`.

## Integrations
- Tigris (real `@tigrisdata/agent-kit` API and `@tigrisdata/cli`; admin credentials provided via `TIGRIS_STORAGE_ACCESS_KEY_ID` / `TIGRIS_STORAGE_SECRET_ACCESS_KEY`).