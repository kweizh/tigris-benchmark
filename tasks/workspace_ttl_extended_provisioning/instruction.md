# Provision a Long-Lived Workspace with Extended TTL

## Background
Tigris Agent Kit's `createWorkspace` function provisions a per-agent bucket with a configurable time-to-live (TTL) and scoped credentials. A long-running evaluation harness needs an isolated workspace that lives for an entire week so multiple evaluation runs can share state, while still expiring automatically if it is abandoned. Downstream tooling reads the resulting bucket name and the expected expiry timestamp from a JSON file so it can detect and reuse the workspace.

## Requirements
- Write a TypeScript script that creates a Tigris workspace using `@tigrisdata/agent-kit`.
- The workspace name MUST be exactly `long-running-eval-ws`.
- The workspace MUST be created with a TTL of 7 days and `ReadOnly` scoped credentials via `createWorkspace`.
- After successful creation, the script MUST write the resulting bucket name and the ISO 8601 formatted expiry timestamp (calculated as the moment of creation + 7 days, in UTC) to a JSON file with the keys `bucket` and `expires_at`.
- The script MUST NOT teardown the workspace — it must be left intact for downstream evaluation runs.
- The script MUST exit with a non-zero status code if `createWorkspace` returns an error.

## Implementation Guide
1. The project directory is already initialized at `/home/user/ttl-workspace` with `@tigrisdata/agent-kit`, `tsx`, and `typescript` installed locally.
2. Create `/home/user/ttl-workspace/index.ts` that:
   - Imports `createWorkspace` from `@tigrisdata/agent-kit`.
   - Captures `now = new Date()` before calling `createWorkspace`.
   - Calls `createWorkspace("long-running-eval-ws", { ttl: { days: 7 }, credentials: { role: "ReadOnly" } })`.
   - Throws or exits non-zero if `error` is set on the response.
   - Writes `/home/user/ttl-workspace/workspace.json` containing:
     ```json
     {
       "bucket": "<workspace.bucket>",
       "expires_at": "<now + 7 days as ISO 8601 UTC string>"
     }
     ```
3. Run the script with `npx tsx index.ts` from `/home/user/ttl-workspace`.
4. The credentials are picked up automatically from the environment variables `TIGRIS_STORAGE_ACCESS_KEY_ID` and `TIGRIS_STORAGE_SECRET_ACCESS_KEY` (already set in the environment).

## Constraints
- Project path: `/home/user/ttl-workspace`
- Script path: `/home/user/ttl-workspace/index.ts`
- Output file: `/home/user/ttl-workspace/workspace.json`
- Start command: `npx tsx index.ts`
- Workspace name: `long-running-eval-ws`
- TTL: exactly 7 days
- Credentials role: `ReadOnly`
- You MUST use the real Tigris API via `@tigrisdata/agent-kit`. Do NOT mock any function.
- You MUST NOT call `teardownWorkspace` in the script. The workspace must remain provisioned after the script exits.

## Integrations
- Tigris Agent Kit (`@tigrisdata/agent-kit`)
- Tigris CLI (`@tigrisdata/cli`)