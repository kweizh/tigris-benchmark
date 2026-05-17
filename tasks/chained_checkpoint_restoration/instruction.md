# Chained Checkpoint Restoration with Tigris Agent Kit

## Background
Production AI pipelines mutate shared buckets on every step. When a mutation needs to be audited or rolled back, the typical workflow is: snapshot the bucket before the risky write, perform the write, then restore the snapshot into an isolated fork for inspection. This is exactly what `checkpoint` and `restore` from `@tigrisdata/agent-kit` are designed for.

A Tigris bucket already exists with snapshots enabled (created automatically before the task starts). Your job is to build the end-to-end checkpoint → mutate → restore → teardown flow as a single TypeScript script.

## Requirements
Write a TypeScript script at `/home/user/chained-ckpt/index.ts` that performs the following actions in order:

1. **Upload v1**: Read the trial id from `/logs/artifacts/trial_id`. Construct the bucket name as `harbor-awscli-${trial_id}` (substitute the actual id; do NOT keep the `${trial_id}` placeholder literal). Note: S3 bucket names can only contain lowercase letters, numbers, dots, and hyphens. You must normalize the bucket name by converting it to lowercase and replacing any invalid characters (like underscores) with hyphens. Upload an object with key `v1.txt` and body `version=1` (UTF-8, no trailing newline) into this existing bucket. Use any S3-compatible client (e.g. `@aws-sdk/client-s3`) pointed at the Tigris endpoint `https://t3.storage.dev`.
2. **Checkpoint**: Take a named checkpoint of the bucket using
   ```ts
   import { checkpoint } from "@tigrisdata/agent-kit";
   const { data: ckpt, error } = await checkpoint(bucketName, { name: "before-mutation" });
   ```
   Save the returned `snapshotId` because you will need it for the restore step.
3. **Mutate**: Upload the same key `v1.txt` again, this time with body `version=2`. This overwrites the original content in the source bucket.
4. **Restore**: Restore the captured checkpoint into a new fork using
   ```ts
   import { restore } from "@tigrisdata/agent-kit";
   const { data: restored } = await restore(bucketName, ckpt.snapshotId, { forkName: "rollback-recovery" });
   ```
   Write the resulting recovery bucket name to `/home/user/chained-ckpt/recovery.json` as JSON in the exact shape `{"recoveryBucket": "<bucket-name>"}`.
5. **Tear down the recovery fork**: After writing `recovery.json`, delete the recovery fork bucket so it does not leak. You may use `removeBucket` from `@tigrisdata/storage`, the AWS S3 SDK, or shell out to `tigris buckets delete <name>` — whichever is convenient. Do NOT delete the source bucket, the original `v1.txt` object in the source bucket, or the snapshot.

The script must exit with status 0 on success. Read credentials from the environment variables `TIGRIS_STORAGE_ACCESS_KEY_ID` and `TIGRIS_STORAGE_SECRET_ACCESS_KEY` (already set in the environment).

## Implementation Guide
1. The project at `/home/user/chained-ckpt` is already initialized with a `package.json` that declares `@tigrisdata/agent-kit`, `@tigrisdata/storage`, `@aws-sdk/client-s3`, `tsx`, and `typescript` as dependencies. Run `npm install` once before authoring the script.
2. After your script is ready, run it with `npx tsx index.ts` from inside `/home/user/chained-ckpt`.
3. Check `result.error` on every Agent Kit call — Agent Kit returns `TigrisResponse<T>` discriminated unions and never throws.
4. The Tigris S3 endpoint is `https://t3.storage.dev`; the region for the AWS SDK should be set to `auto`.

## Constraints
- Project path: `/home/user/chained-ckpt`
- Source bucket name: dynamically constructed as `harbor-awscli-${trial_id}` (already exists with snapshots enabled)
- Checkpoint name: `before-mutation`
- Fork name passed to `restore`: `rollback-recovery` (the actual bucket name may include extra suffixes appended by the service — always read the real name from `restored.bucket`)
- Output file: `/home/user/chained-ckpt/recovery.json` with shape `{"recoveryBucket": "<bucket>"}`
- The recovery fork bucket MUST be deleted by the script before it exits.
- The source bucket MUST remain in place, with `v1.txt` still containing `version=2` after the script finishes.
- Do NOT delete the snapshot `before-mutation`.

## Integrations
- Tigris (cloud object storage). Credentials are pre-provisioned in the environment via `TIGRIS_STORAGE_ACCESS_KEY_ID` and `TIGRIS_STORAGE_SECRET_ACCESS_KEY`.