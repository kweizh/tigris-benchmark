# Concurrent Tigris Workspace Pool Provisioning

## Background
Large-scale agent evaluation harnesses typically pre-warm a pool of isolated Tigris workspaces in parallel — one per agent — before kicking off evaluation runs. Provisioning workspaces sequentially is too slow when the pool size grows. Tigris Agent Kit's `createWorkspace` / `teardownWorkspace` primitives are designed to be invoked concurrently from a single Node.js process via `Promise.all`, and teardown should aggregate partial failures via `Promise.allSettled` so the failure of one workspace does not leak the others.

You must implement a TypeScript script that provisions a pool of four Tigris workspaces in parallel, writes an initialization marker into each, captures a summary of the pool, and tears the entire pool down resiliently.

## Requirements
- Implement `/home/user/ws-pool/index.ts` that uses `@tigrisdata/agent-kit` and `@aws-sdk/client-s3`.
- Provision exactly four workspaces **concurrently** using a single `Promise.all` call. Sequential `await` calls on the four creations are NOT acceptable.
- Workspace names MUST be exactly (in this order): `pool-agent-1`, `pool-agent-2`, `pool-agent-3`, `pool-agent-4`.
- Each workspace MUST be created with `ttl: { days: 1 }` and `credentials: { role: "Editor" }`.
- For each created workspace, upload a single object whose key is `init.txt` and whose body is the workspace's agent name (e.g. the workspace `pool-agent-1` must contain an `init.txt` whose contents are exactly the string `pool-agent-1`). The upload MUST use the workspace's scoped credentials against the Tigris S3 endpoint `https://t3.storage.dev`.
- After all uploads succeed, write a summary file to `/home/user/ws-pool/pool.json`. Its contents MUST be a JSON array of exactly four objects with the keys `name` and `bucket`:
  ```json
  [
    { "name": "pool-agent-1", "bucket": "<workspace bucket name>" },
    { "name": "pool-agent-2", "bucket": "<workspace bucket name>" },
    { "name": "pool-agent-3", "bucket": "<workspace bucket name>" },
    { "name": "pool-agent-4", "bucket": "<workspace bucket name>" }
  ]
  ```
- After writing `pool.json`, tear down every workspace using `Promise.allSettled` over `teardownWorkspace` calls. One failure MUST NOT short-circuit teardown of the others.
- The script MUST exit with status code 0 on success.

## Implementation Guide
1. The project directory `/home/user/ws-pool` is already initialized with `package.json` and `node_modules` containing `@tigrisdata/agent-kit`, `@aws-sdk/client-s3`, `tsx`, and `typescript`.
2. Create `/home/user/ws-pool/index.ts` that performs the following in order:
   - Defines the names list `["pool-agent-1", "pool-agent-2", "pool-agent-3", "pool-agent-4"]`.
   - Calls `createWorkspace(name, { ttl: { days: 1 }, credentials: { role: "Editor" } })` for every name **in parallel** with `Promise.all`.
   - Errors during creation MUST cause the script to exit non-zero.
   - For each workspace, uses `@aws-sdk/client-s3`'s `S3Client` (with endpoint `https://t3.storage.dev`, region `auto`, and the workspace's scoped credentials) plus `PutObjectCommand` to upload `init.txt` containing the agent name. The uploads SHOULD also run in parallel via `Promise.all`.
   - Writes `/home/user/ws-pool/pool.json` with the JSON array described above.
   - Tears down every workspace via `Promise.allSettled([teardownWorkspace(w1), teardownWorkspace(w2), ...])`.
3. Run with `npx tsx index.ts` from `/home/user/ws-pool`.
4. Credentials are read automatically from the environment variables `TIGRIS_STORAGE_ACCESS_KEY_ID` and `TIGRIS_STORAGE_SECRET_ACCESS_KEY`.

## Constraints
- Project path: `/home/user/ws-pool`
- Script path: `/home/user/ws-pool/index.ts`
- Summary file: `/home/user/ws-pool/pool.json`
- Start command: `npx tsx index.ts`
- Workspace names: exactly `pool-agent-1`, `pool-agent-2`, `pool-agent-3`, `pool-agent-4`
- TTL: 1 day for every workspace
- Credentials role: `Editor` for every workspace
- Concurrency: workspace creation MUST be issued via a single `Promise.all` call (no sequential awaits).
- Teardown: MUST use `Promise.allSettled`.
- You MUST use the real Tigris API via `@tigrisdata/agent-kit`. Do NOT mock any function.

## Integrations
- Tigris Agent Kit (`@tigrisdata/agent-kit`)
- Tigris CLI (`@tigrisdata/cli`)