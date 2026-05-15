# Tigris CLI: Force-Delete a Non-Empty Bucket

## Background
During agent evaluation runs, the environment provisions a temporary bucket on the real Tigris service and pre-seeds it with a handful of scratch objects. When the run ends those buckets need to be torn down cleanly, but the Tigris CLI's `tigris buckets delete` subcommand requires the bucket to be empty first — a well-known friction point that trips up cleanup scripts that don't account for residual objects (see https://www.tigrisdata.com/docs/cli/buckets/delete/).

The container has already been seeded at start-up: a bucket named `harbor-cleanup-${trial_id}` exists in the Tigris account and contains three pre-seeded objects under the `temp/` prefix (`temp/a.tmp`, `temp/b.tmp`, `temp/c.tmp`). Your job is to delete that non-empty bucket cleanly from the Tigris account using the Tigris CLI. The bucket exists with objects, please force-delete it. Note: S3 bucket names can only contain lowercase letters, numbers, dots, and hyphens. You must normalize the bucket name by converting it to lowercase and replacing any invalid characters (like underscores) with hyphens.

## Requirements
- Read the Harbor trial identifier from `/logs/artifacts/trial_id` and derive the bucket name `harbor-cleanup-${trial_id}`. Note: S3 bucket names can only contain lowercase letters, numbers, dots, and hyphens. You must normalize the bucket name by converting it to lowercase and replacing any invalid characters (like underscores) with hyphens.
- Use the Tigris CLI (`@tigrisdata/cli`) to remove the bucket and its residual objects from the account. The canonical command to remove the bucket itself is `tigris buckets delete harbor-cleanup-${trial_id} --force`.
- After the task completes, the bucket `harbor-cleanup-${trial_id}` must no longer be present in the Tigris account as observed via `tigris buckets list --format json`.

## Implementation Guide
1. Open a terminal in the project directory `/home/user/cleanup-task`.
2. Read the trial id from `/logs/artifacts/trial_id` and trim any trailing whitespace.
3. Derive the bucket name as `harbor-cleanup-${trial_id}`. Note: S3 bucket names can only contain lowercase letters, numbers, dots, and hyphens. You must normalize the bucket name by converting it to lowercase and replacing any invalid characters (like underscores) with hyphens.
4. (Optional sanity check) Confirm the bucket and its three pre-seeded objects exist:
   ```bash
   tigris buckets list --format json
   tigris ls t3://harbor-cleanup-${trial_id}/temp/
   ```
5. The CLI's `tigris buckets delete` requires the bucket to be empty, so first remove the residual objects recursively:
   ```bash
   tigris rm -r t3://harbor-cleanup-${trial_id}/
   ```
6. Then force-delete the bucket itself (the `--force` flag skips the interactive confirmation prompt that the CLI would otherwise display):
   ```bash
   tigris buckets delete harbor-cleanup-${trial_id} --force
   ```
7. The container's login shell is pre-wired to expose the Tigris credentials to the CLI: `/etc/profile.d/tigris-auth.sh` maps `TIGRIS_STORAGE_ACCESS_KEY_ID`/`TIGRIS_STORAGE_SECRET_ACCESS_KEY` to the AWS-compatible variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION=auto`) consumed by the `tigris` CLI. If you invoke `tigris` from a non-login shell, source this file first or pass the AWS_* variables inline.

## Constraints
- Project path: `/home/user/cleanup-task`
- Bucket name MUST be exactly `harbor-cleanup-${trial_id}` where `${trial_id}` is the contents of `/logs/artifacts/trial_id` (trimmed of trailing whitespace). Do NOT hardcode any other suffix. Note: S3 bucket names can only contain lowercase letters, numbers, dots, and hyphens. You must normalize the bucket name by converting it to lowercase and replacing any invalid characters (like underscores) with hyphens.
- Use the Tigris CLI (`@tigrisdata/cli`) only — do not delete the bucket via raw S3/HTTP, the AWS CLI, or any other tool.
- A naive `tigris buckets delete harbor-cleanup-${trial_id}` (with or without `--force`) on a non-empty bucket will fail because the bucket contains three pre-seeded objects under `temp/`. The residual objects must be removed first (e.g., with `tigris rm -r t3://harbor-cleanup-${trial_id}/`).
- The bucket exists with objects already, please force-delete it; do NOT create or re-create the bucket as part of this task.

## Integrations
- Tigris Object Storage (credentials provided as `TIGRIS_STORAGE_ACCESS_KEY_ID` and `TIGRIS_STORAGE_SECRET_ACCESS_KEY`).