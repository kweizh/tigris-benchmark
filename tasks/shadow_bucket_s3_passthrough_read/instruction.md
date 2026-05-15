# Tigris Shadow Bucket: Read-Through Migration from an Origin Bucket

## Background
Tigris supports **zero-downtime migration** from any S3-compatible source via the **shadow bucket** mechanism (see https://www.tigrisdata.com/docs/migration/). When a Tigris bucket is configured with a shadow source, reads for objects that are not yet present in the Tigris bucket are transparently fetched from the shadow source, returned to the caller, and asynchronously copied into the Tigris bucket for future access.

In this task, both the origin and the shadow are Tigris buckets (Tigris is itself S3-compatible at endpoint `https://t3.storage.dev`), so the entire migration loop is exercised end-to-end without any external AWS dependency.

The container's entrypoint script has ALREADY pre-seeded the origin bucket BEFORE the agent runs:

- Origin bucket name: `harbor-origin-${trial_id}` (where `${trial_id}` is the content of `/logs/artifacts/trial_id`). Note: S3 bucket names can only contain lowercase letters, numbers, dots, and hyphens. You must normalize the bucket name by converting it to lowercase and replacing any invalid characters (like underscores) with hyphens.
- Pre-seeded object key: `docs/readme.md`
- Pre-seeded object content (exact bytes, no trailing newline): `from origin`

The shadow bucket has NOT been created yet. That is your job.

## Requirements
Using the `tigris` CLI and the `aws` CLI, do the following:

1. Create a NEW Tigris bucket named EXACTLY `harbor-shadow-${trial_id}` (read the `${trial_id}` from `/logs/artifacts/trial_id`). Note: S3 bucket names can only contain lowercase letters, numbers, dots, and hyphens. You must normalize the bucket name by converting it to lowercase and replacing any invalid characters (like underscores) with hyphens.
2. Configure the new bucket so that the **pre-existing** Tigris bucket `harbor-origin-${trial_id}` is its **shadow source**. The shadow source endpoint MUST be `https://t3.storage.dev`, the region MUST be `auto`, and the shadow credentials MUST be the same Tigris credentials provided to the container (`TIGRIS_STORAGE_ACCESS_KEY_ID` / `TIGRIS_STORAGE_SECRET_ACCESS_KEY`). DO NOT enable write-through.
3. Without ever writing the object `docs/readme.md` directly into the shadow bucket, fetch the object via the shadow bucket using the AWS CLI:
   ```bash
   aws s3 cp s3://harbor-shadow-${trial_id}/docs/readme.md /home/user/tigris-task/proxied.md \
     --endpoint-url https://t3.storage.dev --region auto
   ```
   The shadow bucket must serve the read by proxying it from the origin bucket.
4. After the proxied read completes, the local file `/home/user/tigris-task/proxied.md` MUST contain exactly the bytes `from origin` (11 bytes, no trailing newline).
5. Do NOT delete or modify the origin bucket or the origin object. The verifier reads them.

## Implementation Guide
1. Read the trial id and derive both bucket names:
   ```bash
   TRIAL_ID="$(cat /logs/artifacts/trial_id)"
   ORIGIN="harbor-origin-${TRIAL_ID}"
   SHADOW="harbor-shadow-${TRIAL_ID}"
   ```
2. Create the empty shadow bucket:
   ```bash
   tigris buckets create "$SHADOW"
   ```
3. Configure shadow migration (point the shadow bucket at the origin bucket as its read-through source):
   ```bash
   tigris buckets set-migration "$SHADOW" \
     --bucket "$ORIGIN" \
     --endpoint https://t3.storage.dev \
     --region auto \
     --access-key "$TIGRIS_STORAGE_ACCESS_KEY_ID" \
     --secret-key "$TIGRIS_STORAGE_SECRET_ACCESS_KEY"
   ```
   Refer to https://www.tigrisdata.com/docs/cli/buckets/set-migration/ for the flag specification.
4. Confirm the migration configuration is set by inspecting the shadow bucket:
   ```bash
   tigris buckets get "$SHADOW"
   ```
5. Now use the AWS CLI to read the object through the shadow bucket — the object is NOT directly present in the shadow bucket, so the shadow read-through must service the request from the origin:
   ```bash
   aws s3 cp "s3://${SHADOW}/docs/readme.md" /home/user/tigris-task/proxied.md \
     --endpoint-url https://t3.storage.dev --region auto
   ```
6. Verify locally that `/home/user/tigris-task/proxied.md` exists and contains EXACTLY the bytes `from origin`.

## Constraints
- Project path: `/home/user/tigris-task`
- Output file MUST be at exactly `/home/user/tigris-task/proxied.md`.
- Origin bucket name MUST be exactly `harbor-origin-${trial_id}` (do NOT recreate or modify it — it is pre-seeded by the container entrypoint). Note: S3 bucket names can only contain lowercase letters, numbers, dots, and hyphens. You must normalize the bucket name by converting it to lowercase and replacing any invalid characters (like underscores) with hyphens.
- Shadow bucket name MUST be exactly `harbor-shadow-${trial_id}` (you create it). Note: S3 bucket names can only contain lowercase letters, numbers, dots, and hyphens. You must normalize the bucket name by converting it to lowercase and replacing any invalid characters (like underscores) with hyphens.
- Shadow source endpoint MUST be `https://t3.storage.dev`; region MUST be `auto`.
- DO NOT upload `docs/readme.md` (or any object) directly into the shadow bucket via `tigris cp`, `tigris mk`, `aws s3 cp` to the shadow bucket, or any other mechanism — the bytes MUST be served by the shadow read-through from the origin bucket.
- DO NOT enable write-through mode on the shadow migration configuration.
- DO NOT delete either bucket; the verifier deletes both during cleanup.
- The local file `/home/user/tigris-task/proxied.md` MUST contain EXACTLY the bytes `from origin` (11 bytes, no trailing whitespace/newline).
- The container is pre-wired so that the Tigris CLI and the AWS CLI both authenticate against the Harbor-provided credentials: `/etc/profile.d/tigris-auth.sh` maps `TIGRIS_STORAGE_ACCESS_KEY_ID` / `TIGRIS_STORAGE_SECRET_ACCESS_KEY` onto `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION=auto`. If you invoke the CLI from a non-login shell, source this file first or pass the AWS_* variables inline.

## Integrations
- Tigris Object Storage (credentials provided as `TIGRIS_STORAGE_ACCESS_KEY_ID` and `TIGRIS_STORAGE_SECRET_ACCESS_KEY`).