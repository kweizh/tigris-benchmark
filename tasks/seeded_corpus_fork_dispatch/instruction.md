# Seed a Corpus and Dispatch Read-Only Forks for Parallel Agents

## Background
Multi-agent eval pipelines often need to dispatch the *same* starting corpus to several agents at once. Tigris Agent Kit (`@tigrisdata/agent-kit`) makes this efficient: you seed a source bucket once, then use `createForks` to mint N copy-on-write clones (each optionally scoped to its own IAM access key). This task wires the seeding step (S3 upload via the AWS SDK) together with `createForks`/`teardownForks` and persists the names of the resulting forks for downstream tooling.

A setup script `/home/user/seeded-fork/setup.sh` runs at task start and creates the source bucket `seed-corpus` with snapshots enabled. The bucket is empty — you must seed it from the three local files `data/a.txt`, `data/b.txt`, and `data/c.txt`.

## Requirements
Write a TypeScript program at `/home/user/seeded-fork/index.ts` that:

1. Reads the trial id from `/logs/artifacts/trial_id`. Constructs the source bucket name as `harbor-seeded-${trial_id}` (substitute the actual id; do NOT keep the `${trial_id}` placeholder literal). Note: S3 bucket names can only contain lowercase letters, numbers, dots, and hyphens. You must normalize the bucket name by converting it to lowercase and replacing any invalid characters (like underscores) with hyphens.
2. Reads the three local files `data/a.txt`, `data/b.txt`, and `data/c.txt` (relative to `/home/user/seeded-fork`) and uploads them to the source bucket using the AWS SDK for JavaScript v3 (`@aws-sdk/client-s3`). Use the admin Tigris credentials from the environment (`TIGRIS_STORAGE_ACCESS_KEY_ID`, `TIGRIS_STORAGE_SECRET_ACCESS_KEY`), the Tigris endpoint `https://t3.storage.dev`, and `region: "auto"`. The uploaded object keys must be exactly `a.txt`, `b.txt`, and `c.txt`.
3. Calls `createForks(sourceBucketName, 2, { prefix: "eval-dispatch", credentials: { role: "ReadOnly" } })` from `@tigrisdata/agent-kit`. Both forks must be requested in a single call.
4. Writes the resulting fork bucket names to `/home/user/seeded-fork/forks.json` as `{ "forks": [name1, name2] }` (a top-level object with a `forks` array of strings) BEFORE tearing the forks down.
5. Calls `teardownForks` at the end to delete both fork buckets and revoke their scoped credentials. Use a `try`/`finally` so teardown runs even if an earlier step fails.
6. Exits with status `0` on success.

## Implementation Guide
1. Change into the project directory at `/home/user/seeded-fork`. The project already has `package.json`, `tsconfig.json`, and a populated local `node_modules` containing `@tigrisdata/agent-kit`, `@tigrisdata/cli`, `@aws-sdk/client-s3`, `tsx`, and `typescript`. The `data/` subdirectory containing `a.txt`, `b.txt`, and `c.txt` is also pre-created. You only need to create `index.ts`.
2. Import `createForks`, `teardownForks` from `@tigrisdata/agent-kit` and `S3Client`, `PutObjectCommand` from `@aws-sdk/client-s3`. Use the Node `fs/promises` module for reading the local files and writing `forks.json`.
3. Read the trial id and construct the source bucket name. Construct one `S3Client` for the seeding step using the admin Tigris credentials, `region: "auto"`, and `endpoint: "https://t3.storage.dev"`. Upload each of `a.txt`, `b.txt`, `c.txt` with the same key as filename.
4. Call `createForks(sourceBucketName, 2, { prefix: "eval-dispatch", credentials: { role: "ReadOnly" } })`. Check `error` first; if non-null, throw it.
5. Build the `forks.json` payload from `forkSet.forks.map(f => f.bucket)` and write it to `/home/user/seeded-fork/forks.json` (UTF-8). The JSON must be a top-level object with a single `forks` field holding the array of bucket names.
6. After `forks.json` is written, call `teardownForks(forkSet)` so the fork buckets and their scoped keys are removed. The source bucket and its objects must remain untouched.
7. Run the script with `npx tsx index.ts` from `/home/user/seeded-fork`. It must exit with status 0.

## Constraints
- Project path: `/home/user/seeded-fork`
- Setup script (runs automatically at task start, creating the source bucket): `/home/user/seeded-fork/setup.sh`
- Bucket name: dynamically constructed as `harbor-seeded-${trial_id}` (where `${trial_id}` is read from `/logs/artifacts/trial_id`, normalized to lowercase with invalid characters replaced by hyphens)
- Fork prefix: `eval-dispatch` (each fork bucket name must begin with this prefix)
- Fork count: exactly 2 (single `createForks` call)
- Fork credentials role: `ReadOnly`
- Output manifest: `/home/user/seeded-fork/forks.json` with shape `{ "forks": [<bucket-name-1>, <bucket-name-2>] }`
- Use ONLY the AWS SDK for JavaScript v3 (`@aws-sdk/client-s3`) for the seed uploads — do not shell out to the Tigris CLI for the upload step.
- Do not modify `package.json`, `tsconfig.json`, `node_modules`, or the contents of `data/`.
- The fork buckets must NOT remain after the script exits — `teardownForks` must run.

## Integrations
- Tigris (real `@tigrisdata/agent-kit` API, AWS S3-compatible API, and `@tigrisdata/cli`; admin credentials provided via `TIGRIS_STORAGE_ACCESS_KEY_ID` / `TIGRIS_STORAGE_SECRET_ACCESS_KEY`).