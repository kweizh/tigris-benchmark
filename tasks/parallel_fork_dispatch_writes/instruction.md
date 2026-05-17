# Parallel Fork Dispatch with Tigris Agent Kit

## Background
Tigris Agent Kit (`@tigrisdata/agent-kit`) exposes a `createForks` primitive that snapshots a source bucket once and provisions N copy-on-write fork buckets from that snapshot. This is the recommended pattern for fanning out the same starting dataset to multiple parallel agents without paying N times the storage cost.

A source bucket must be created with snapshots enabled and pre-seeded with an object BEFORE the agent starts:

- Bucket name: `harbor-source-${trial_id}` (snapshots enabled), where `${trial_id}` is the content of `/logs/artifacts/trial_id` (newline-trimmed). Note: S3 bucket names can only contain lowercase letters, numbers, dots, and hyphens. You must normalize the bucket name by converting it to lowercase and replacing any invalid characters (like underscores) with hyphens.
- Pre-seeded object: `seed/dataset.txt` with body bytes `initial` (no trailing newline).

Your job is to write a TypeScript program that uses Agent Kit to fork that source bucket 3 ways, then fan out **in parallel** to write a distinct `worker/output.txt` object into each fork. The verifier later asserts both that each fork contains the correct distinct worker output AND that the seed object is still present in every fork (proving the copy-on-write fork inherited the source's state).

## Requirements
Write a TypeScript program at `/home/user/tigris-task/run.ts` that does ALL of the following, in order:

1. Read the current trial id from `/logs/artifacts/trial_id` and `.trim()` it.
2. Compute `sourceBucket = "harbor-source-${trial_id}"` and `forkPrefix = "harbor-fork-${trial_id}"` (normalized to lowercase, invalid characters replaced with hyphens).
3. Call `createForks(sourceBucket, 3, { prefix: forkPrefix })` from `@tigrisdata/agent-kit`. This must produce exactly 3 fork buckets named `harbor-fork-${trial_id}-0`, `harbor-fork-${trial_id}-1`, `harbor-fork-${trial_id}-2` (with `${trial_id}` normalized).
4. Check the returned `TigrisResponse<Forks>` envelope for an `error` field and exit non-zero on failure.
5. Using `@tigrisdata/storage`'s `put(key, body, { config: { bucket } })`, fan out IN PARALLEL with `Promise.all` to write the object `worker/output.txt` into each of the three fork buckets, where fork index `i` (0, 1, 2) receives the body bytes `worker-${i}` (e.g. fork `...-0` receives `worker-0`).
6. Print the resulting fork bucket names to stdout (one per line, in `forks[]` order) so the run is auditable.

Run the program with `tsx /home/user/tigris-task/run.ts`. `tsx` is pre-installed both globally and locally in `/home/user/tigris-task/node_modules`. The program MUST exit with code 0 on success.

## Implementation Guide
1. `cd /home/user/tigris-task`. The project is already initialized with a `package.json` that pre-declares `@tigrisdata/agent-kit`, `@tigrisdata/storage`, and `tsx`, and dependencies are already installed into `node_modules` at image build time. A `tsconfig.json` is also provided.
2. Create `run.ts` using ES module imports:
   ```typescript
   import { readFile } from "node:fs/promises";
   import { createForks } from "@tigrisdata/agent-kit";
   import { put } from "@tigrisdata/storage";
   ```
3. Read the trial id, derive the bucket names, and call `createForks` with `count = 3` and `prefix = "harbor-fork-${trialId}"`.
4. After `createForks` succeeds, build an array of 3 promises — one per fork — that each call `put("worker/output.txt", "worker-" + i, { config: { bucket: forkSet.forks[i].bucket } })`, and `await Promise.all([...])` so the three writes happen concurrently.
5. After all three writes resolve successfully, print each `forkSet.forks[i].bucket` to stdout (one per line).
6. The Tigris credentials (`TIGRIS_STORAGE_ACCESS_KEY_ID`, `TIGRIS_STORAGE_SECRET_ACCESS_KEY`, `TIGRIS_STORAGE_ENDPOINT`) are exposed as environment variables — both SDKs pick them up automatically. Do NOT hardcode credentials.

## Constraints
- Project path: `/home/user/tigris-task`
- Source file: `/home/user/tigris-task/run.ts`
- Source bucket (must be created with snapshots enabled and pre-seeded before the agent runs): `harbor-source-${trial_id}` (normalized).
- Fork bucket names (created by `createForks` via the `prefix` option): `harbor-fork-${trial_id}-0`, `harbor-fork-${trial_id}-1`, `harbor-fork-${trial_id}-2` (normalized).
- The three fork writes MUST happen in parallel via `Promise.all`. Sequential `for await` loops are not acceptable — the verifier will inspect `run.ts` for `Promise.all`.
- Use `@tigrisdata/agent-kit`'s `createForks` exclusively for fork creation. Do not implement forking via `tigris buckets create` or raw S3 calls.
- Use `@tigrisdata/storage`'s `put` for the per-fork writes. Do not shell out to the CLI for the worker writes.
- Do not delete the source bucket or any fork bucket. The verifier owns cleanup of all four buckets.
- Do not hardcode the trial id; always read it from `/logs/artifacts/trial_id`.

## Integrations
- Tigris Object Storage (real `https://t3.storage.dev` endpoint; credentials exposed as `TIGRIS_STORAGE_ACCESS_KEY_ID`, `TIGRIS_STORAGE_SECRET_ACCESS_KEY`, `TIGRIS_STORAGE_ENDPOINT`).
