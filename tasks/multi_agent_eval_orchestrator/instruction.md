# Multi-Agent Eval Orchestrator

Build a TypeScript orchestrator at `/home/user/orchestrator/index.ts` using `@tigrisdata/agent-kit`. A pre-task setup step has already provisioned the gold dataset bucket `gold-eval-dataset` (snapshots enabled) and seeded it with three prompt objects under the `prompts/` prefix: `prompts/p1.json`, `prompts/p2.json`, and `prompts/p3.json`.

Your orchestrator must:

1. Fork `gold-eval-dataset` into exactly 3 isolated environments in a single `createForks` call using the prefix `eval-attempt` and `ReadOnly` scoped credentials.
2. For each fork, in parallel, provision a separate **write** workspace via `createWorkspace` named `eval-writer-<i>` (where `<i>` is the fork's index `0`, `1`, `2`) with `Editor` credentials. Inside each writer workspace, fetch every prompt object from the matching read-only fork bucket, then write an answer object at key `answers/p<N>.txt` whose body is the UTF-8 text content of the prompt file reversed character-by-character (i.e., `prompt_content.split("").reverse().join("")` in JS). The fork must be read using its own scoped credentials, the writer with its own scoped credentials. The Tigris endpoint is `https://t3.storage.dev` and the region is `auto`.
3. After all three attempts finish, fetch every answer back from the three writer workspaces and aggregate them into `/home/user/orchestrator/aggregated.json` keyed exactly as `{ "<fork-bucket-name>": { "p1": "<reversed p1.json content>", "p2": "<reversed p2.json content>", "p3": "<reversed p3.json content>" }, ... }`. The top-level keys MUST be the fork bucket names returned by `createForks` (which will be `eval-attempt-0`, `eval-attempt-1`, `eval-attempt-2`).
4. Tear down every fork via `teardownForks` and every writer workspace via `teardownWorkspace` before the process exits, even on failure (use `try`/`finally`).
5. Be invokable with `npx tsx index.ts` from `/home/user/orchestrator` and exit with status `0` on success.

## Constraints
- Project path: `/home/user/orchestrator`
- Use the real Tigris API (no mocks).
- Do not modify `package.json`, `tsconfig.json`, `node_modules`, or anything outside the project directory.
- All fork and writer workspace buckets MUST be deleted before the process exits.
- The bucket `gold-eval-dataset` and its prompt objects MUST be left untouched.

## Integrations
- Tigris (real `@tigrisdata/agent-kit` API plus AWS S3-compatible API via `@aws-sdk/client-s3`; admin credentials are provided in the environment as `TIGRIS_STORAGE_ACCESS_KEY_ID` and `TIGRIS_STORAGE_SECRET_ACCESS_KEY`).