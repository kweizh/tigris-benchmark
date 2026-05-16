# Tigris Agent Pool Lifecycle Manager

## Background
Production agent harnesses don't just spin up a single workspace — they manage an entire pool of agent workspaces over time: provisioning many at once, dispatching work to individual agents, surveying live state, and reliably tearing the pool down at the end. Tigris Agent Kit's `createWorkspace` / `teardownWorkspace` primitives, paired with each workspace's scoped Editor credentials and the Tigris S3 endpoint, are the building blocks for such a manager.

You must implement a complete agent pool lifecycle manager as a TypeScript library plus a CLI entrypoint, then run a four-step scenario through the CLI and capture its output to a log file.

## Requirements
- Implement the manager at `/home/user/pool/manager.ts` using `@tigrisdata/agent-kit` and `@aws-sdk/client-s3`.
- Implement the CLI entrypoint at `/home/user/pool/cli.ts`. It MUST be runnable via `npx tsx cli.ts <subcommand> [args...]` from `/home/user/pool` and dispatch to functions exported by `manager.ts`.
- The CLI MUST support exactly four subcommands:

  1. `provision <N>` — Provision exactly `<N>` Tigris workspaces **concurrently** (single `Promise.all` over `createWorkspace` calls; sequential awaits are NOT acceptable). The workspaces MUST be named `pool-<N>-1`, `pool-<N>-2`, ..., `pool-<N>-<N>` (1-based; the literal value of `<N>` appears in every workspace name). Each workspace MUST be created with `ttl: { days: 1 }` and `credentials: { role: "Editor" }`. After provisioning succeeds, write `/home/user/pool/pool-state.json` whose contents are a JSON object of the form:
     ```json
     {
       "workspaces": [
         { "name": "pool-3-1", "bucket": "<bucket-name>" },
         { "name": "pool-3-2", "bucket": "<bucket-name>" },
         { "name": "pool-3-3", "bucket": "<bucket-name>" }
       ]
     }
     ```
     The order in the `workspaces` array MUST match the agent index order (entry `i` corresponds to workspace `pool-<N>-<i+1>`). The persisted record MUST also include each workspace's scoped `credentials` (accessKeyId / secretAccessKey) so later subcommands can use them — store them under a `credentials` key on each entry. If any `createWorkspace` call fails, the CLI MUST exit non-zero and MUST NOT write `pool-state.json`.

  2. `assign-task <agent-index> <text>` — Read `pool-state.json`, look up the entry whose 1-based agent index matches `<agent-index>` (so `1` refers to the first entry in the `workspaces` array), and upload a single object whose key is exactly `task.txt` and whose body is exactly `<text>` to that workspace's bucket. The upload MUST use the workspace's scoped credentials (NOT the global Tigris credentials) against the Tigris S3 endpoint `https://t3.storage.dev`, region `auto`, via `@aws-sdk/client-s3`'s `S3Client` and `PutObjectCommand`. The subcommand MUST exit 0 on success and non-zero if `pool-state.json` is missing, the agent index is out of range, or the upload fails.

  3. `status` — Read `pool-state.json` and print to stdout, in this exact format and order:
     - A first line of the form `pool size: <count>` where `<count>` is the integer number of workspaces in the pool.
     - Then one bucket name per line, in the same order as the `workspaces` array.
     Exit code MUST be 0 when `pool-state.json` exists, even if the pool is empty.

  4. `teardown` — Read `pool-state.json` and tear down every recorded workspace via `teardownWorkspace` using `Promise.allSettled` so a single failure does not short-circuit the others. After all teardown attempts have settled (regardless of partial errors), remove `/home/user/pool/pool-state.json` from disk. Exit code 0 if every teardown succeeded; non-zero if any failed.

- The four subcommands MUST be implemented in `manager.ts` as exported async functions (`provisionPool`, `assignTask`, `status`, `teardownPool`, or equivalent named exports) and invoked from `cli.ts` based on `process.argv`. Unknown subcommands MUST cause the CLI to exit non-zero with a usage message on stderr.

## Scenario to Execute
After implementing the manager and CLI, run the following four CLI invocations **in order** from `/home/user/pool` and append each invocation's combined stdout+stderr (in order) to `/home/user/pool/scenario.log`:

1. `npx tsx cli.ts provision 3`
2. `npx tsx cli.ts assign-task 1 "hello world"`
3. `npx tsx cli.ts status`
4. `npx tsx cli.ts teardown`

After the scenario completes:
- `/home/user/pool/scenario.log` MUST exist and MUST contain a line `pool size: 3` followed by exactly 3 bucket-name lines (produced by the `status` step).
- All three workspace buckets MUST have been torn down (verifiable via `tigris buckets list`).
- `/home/user/pool/pool-state.json` MUST be absent after the `teardown` step.

## Implementation Guide
1. The project directory `/home/user/pool` is pre-initialized with `package.json`, `tsconfig.json`, and `node_modules` containing `@tigrisdata/agent-kit`, `@aws-sdk/client-s3`, `tsx`, `typescript`, and `@types/node`. The Tigris CLI (`tigris`) is installed globally.
2. Read Tigris Agent Kit credentials from the environment variables `TIGRIS_STORAGE_ACCESS_KEY_ID` and `TIGRIS_STORAGE_SECRET_ACCESS_KEY` — `@tigrisdata/agent-kit` picks them up automatically.
3. Implement `manager.ts` with one exported async function per subcommand. Each function MUST throw or return non-zero so the CLI can surface failures properly.
4. Implement `cli.ts` that parses `process.argv` (after the first two entries) and dispatches to the matching manager function. Use `process.exitCode = 1` on failure.
5. To run the full scenario, you may use a shell one-liner; e.g. each command's combined output appended to `scenario.log`:
   ```bash
   cd /home/user/pool && \
     npx tsx cli.ts provision 3                >> scenario.log 2>&1 && \
     npx tsx cli.ts assign-task 1 "hello world" >> scenario.log 2>&1 && \
     npx tsx cli.ts status                     >> scenario.log 2>&1 && \
     npx tsx cli.ts teardown                   >> scenario.log 2>&1
   ```

## Constraints
- Project path: `/home/user/pool`
- Manager module: `/home/user/pool/manager.ts`
- CLI entrypoint: `/home/user/pool/cli.ts`
- State file: `/home/user/pool/pool-state.json` (created by `provision`, deleted by `teardown`)
- Log file: `/home/user/pool/scenario.log` (must contain the four scenario steps' outputs)
- Workspace naming: literal `pool-<N>-<i>` for 1-based `i` and the integer `N` passed to `provision`.
- TTL: 1 day for every workspace; credentials role: `Editor` for every workspace.
- Concurrency: provisioning MUST use a single `Promise.all` over `createWorkspace`; teardown MUST use `Promise.allSettled` over `teardownWorkspace`.
- Upload endpoint: `https://t3.storage.dev`; region: `auto`; credentials: the workspace's scoped Editor key.
- You MUST use the real Tigris API via `@tigrisdata/agent-kit`. Do NOT mock any Tigris or S3 function.

## Integrations
- Tigris Agent Kit (`@tigrisdata/agent-kit`)
- Tigris CLI (`@tigrisdata/cli`)
