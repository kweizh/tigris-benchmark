# Tigris Agent Kit: Checkpoint, Mutate, then Restore Into a Fork

## Background
Tigris Agent Kit (`@tigrisdata/agent-kit`) exposes copy-on-write **checkpoints** and **restores** for object buckets. A checkpoint captures a bucket's state at a single point in time; `restore` materializes that captured state into a brand-new fork bucket without touching the source. This is how AI agents "roll back" a sandbox to a known-good state for re-evaluation while leaving the live data untouched.

The container already has a base bucket `harbor-base-${trial_id}` provisioned with snapshots enabled, pre-seeded by the entrypoint with two objects:
- `data/v1.txt` whose content is exactly `version1`
- `data/v2.txt` whose content is exactly `version2`

Your task is to (1) checkpoint that base bucket, (2) write a new object `data/v3.txt` (content `version3`) into the base bucket *after* the checkpoint, and (3) restore the checkpoint into a fresh fork bucket named `harbor-restore-${trial_id}`. The fork must reflect the state *before* `data/v3.txt` was added.

## Requirements
- Implement everything in a single TypeScript script at `/home/user/tigris-task/run.ts`.
- Use `@tigrisdata/agent-kit` for `checkpoint` and `restore`.
- Use `@tigrisdata/storage` (`put`) to upload `data/v3.txt`.
- Execute the script with `tsx /home/user/tigris-task/run.ts`. The script must exit with code 0 on success.

## Implementation Guide
1. Read the trial id from `/logs/artifacts/trial_id` and `.trim()` it. Build:
   - `baseBucket = harbor-base-${trial_id}`
   - `forkBucket = harbor-restore-${trial_id}`
2. Import the SDK symbols:
   ```typescript
   import { readFile } from "node:fs/promises";
   import { checkpoint, restore } from "@tigrisdata/agent-kit";
   import { put } from "@tigrisdata/storage";
   ```
3. **Step A — Take the checkpoint BEFORE writing `v3.txt`:**
   ```typescript
   const { data: ckpt, error: ckptErr } = await checkpoint(baseBucket, { name: "before-eval" });
   if (ckptErr) throw ckptErr;
   const snapshotId = ckpt.snapshotId;
   ```
4. **Step B — Write `data/v3.txt` to the base bucket after the checkpoint:**
   ```typescript
   const { error: putErr } = await put("data/v3.txt", "version3", {
     config: { bucket: baseBucket },
     contentType: "text/plain",
   });
   if (putErr) throw putErr;
   ```
5. **Step C — Restore the checkpoint into the fork bucket:**
   ```typescript
   const { data: restored, error: restoreErr } = await restore(baseBucket, snapshotId, {
     forkName: forkBucket,
   });
   if (restoreErr) throw restoreErr;
   if (restored.bucket !== forkBucket) {
     throw new Error(`unexpected restored bucket: ${restored.bucket}`);
   }
   ```
6. Optionally write `${snapshotId}` to `/home/user/tigris-task/snapshot-id.txt` for your own bookkeeping (not required for grading).
7. Run the script:
   ```bash
   cd /home/user/tigris-task && tsx run.ts
   ```
   The order matters: **checkpoint → upload v3.txt → restore**. If you write `v3.txt` before the checkpoint, the fork will contain three objects and the task will fail.

## Constraints
- Project path: `/home/user/tigris-task`
- Source file: `/home/user/tigris-task/run.ts`
- Base bucket name: `harbor-base-${trial_id}` (pre-seeded by the entrypoint with snapshots enabled and the two `data/v*.txt` objects).
- Fork bucket name: `harbor-restore-${trial_id}` (created by your `restore` call — must not pre-exist).
- The fork bucket must contain EXACTLY the two pre-seeded objects (`data/v1.txt`, `data/v2.txt`). It MUST NOT contain `data/v3.txt`, because the checkpoint was taken before the upload.
- The base bucket must still contain all three objects (`data/v1.txt`, `data/v2.txt`, `data/v3.txt`) at the end.
- Use only `@tigrisdata/agent-kit` and `@tigrisdata/storage` for the checkpoint/restore/upload work. Do not shell out to the Tigris CLI for these operations.
- Do not hardcode credentials — `TIGRIS_STORAGE_ACCESS_KEY_ID`, `TIGRIS_STORAGE_SECRET_ACCESS_KEY`, and `TIGRIS_STORAGE_ENDPOINT` are pre-populated in the environment and read automatically by the SDKs.

## Integrations
- Tigris Data (real `https://t3.storage.dev` endpoint via `@tigrisdata/agent-kit` and `@tigrisdata/storage`).
