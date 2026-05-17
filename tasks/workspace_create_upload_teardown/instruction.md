# Tigris Agent Kit: Workspace Lifecycle With Scoped Credentials

## Background
Tigris Agent Kit (`@tigrisdata/agent-kit`) provides a `createWorkspace` primitive that provisions an ephemeral bucket plus a scoped IAM access key. The scoped key is restricted to that single workspace bucket only — leaking the key cannot expose any other data. In this task you will write a TypeScript program that creates such a workspace, then uses the scoped credentials (not the root credentials in the environment) to upload a small state object into the workspace bucket. You will also surface the scoped access key id so the verifier can confirm it is different from the root key.

## Requirements
- Write a TypeScript program at `/home/user/tigris-task/run.ts` that:
  1. Reads the current `trial_id` from `/logs/artifacts/trial_id` and `.trim()`s it.
  2. Builds the workspace name as `harbor-ws-${trial_id}` (Note: S3 bucket names can only contain lowercase letters, numbers, dots, and hyphens. You must normalize the bucket name by converting it to lowercase and replacing any invalid characters (like underscores) with hyphens.).
  3. Calls `createWorkspace(name, { ttl: { days: 1 }, credentials: { role: "Editor" } })` from `@tigrisdata/agent-kit`. If the call returns an error or returns a workspace without `credentials`, exit with a non-zero exit code.
  4. Using ONLY the scoped credentials returned in `workspace.credentials` (NOT the root `TIGRIS_STORAGE_ACCESS_KEY_ID` / `TIGRIS_STORAGE_SECRET_ACCESS_KEY` env vars), upload a single object with `@tigrisdata/storage`'s `put`:
     - Key: `state.json`
     - Body: the exact string `{"status":"ok","run":"${trial_id}"}` (no extra whitespace, with `${trial_id}` substituted).
     - Content-Type: `application/json`.
     - Target bucket: `workspace.bucket`.
     - Pass the scoped credentials explicitly via `config: { bucket, accessKeyId, secretAccessKey }`.
  5. After a successful upload, print the scoped `workspace.credentials.accessKeyId` to stdout (a single line, no extra prefix) AND also write it to `/home/user/tigris-task/output.log` so it can be inspected after the run.
- Run the program with `tsx /home/user/tigris-task/run.ts` (`tsx` is installed both globally and as a local dev dependency).
- All Tigris API calls must hit the real Tigris service via `@tigrisdata/agent-kit` and `@tigrisdata/storage`. Do not mock anything.

## Implementation Guide
1. `cd /home/user/tigris-task`
2. The project is already initialized with a `package.json` that depends on `@tigrisdata/agent-kit`, `@tigrisdata/storage`, and `tsx`, and the dependencies are pre-installed in `node_modules`. A `tsconfig.json` is also provided.
3. Create `run.ts` with the logic described above. Suggested imports:
   ```typescript
   import { readFile, writeFile } from "node:fs/promises";
   import { createWorkspace } from "@tigrisdata/agent-kit";
   import { put } from "@tigrisdata/storage";
   ```
4. For every SDK call, check the returned `{ data, error }` envelope. On any unexpected error, log it and exit non-zero.
5. Do NOT call `teardownWorkspace` from `run.ts` — the verifier is responsible for tearing down the workspace after it inspects the result.
6. Run with `tsx run.ts` and confirm it exits with code 0 and prints exactly one line: the scoped access key id (it should start with `tid_`).

## Constraints
- Project path: /home/user/tigris-task
- Source file: /home/user/tigris-task/run.ts
- Log file: /home/user/tigris-task/output.log (must contain the scoped access key id printed by the script)
- Workspace name: `harbor-ws-${trial_id}` where `${trial_id}` is read from `/logs/artifacts/trial_id`.
- Object key: `state.json`
- Object body: exact string `{"status":"ok","run":"${trial_id}"}` (UTF-8, no trailing newline).
- The upload MUST be performed using the scoped credentials returned by `createWorkspace`. Do not fall back to the root env-var credentials for the upload step.
- Do not hardcode credentials anywhere; the root credentials are exposed via environment variables and consumed automatically by `@tigrisdata/agent-kit`.

## Integrations
- Tigris Data (real `https://t3.storage.dev` endpoint via `@tigrisdata/agent-kit` and `@tigrisdata/storage`).
