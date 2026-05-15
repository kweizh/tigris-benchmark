# Tigris CLI: Apply a 7-Day Object Expiration TTL to a Bucket

## Background
Tigris buckets can be configured with an object expiration TTL so that objects are automatically deleted after a fixed number of days. This is a common requirement for ephemeral evaluation buckets that should not accumulate state indefinitely. The Tigris CLI (`@tigrisdata/cli`) exposes this as the `tigris buckets set-ttl` subcommand (documented at https://www.tigrisdata.com/docs/cli/buckets/set-ttl/), which configures bucket-level object expiration in days or to a specific date.

## Requirements
- Read the Harbor trial identifier from `/logs/artifacts/trial_id` and use it to derive a unique bucket name `harbor-ttl-${trial_id}`. Note: S3 bucket names can only contain lowercase letters, numbers, dots, and hyphens. You must normalize the bucket name by converting it to lowercase and replacing any invalid characters (like underscores) with hyphens.
- Create that bucket using the Tigris CLI.
- Configure the bucket's object expiration TTL to 7 days using the documented Tigris CLI subcommand `tigris buckets set-ttl`.
- The bucket configuration returned by `tigris buckets get <bucket> --format json` must reflect that the 7-day TTL is in effect.

## Implementation Guide
1. Open a terminal in the project directory `/home/user/ttl-task`.
2. Read the trial id from `/logs/artifacts/trial_id` and trim any trailing whitespace.
3. Derive the bucket name as `harbor-ttl-${trial_id}`. Note: S3 bucket names can only contain lowercase letters, numbers, dots, and hyphens. You must normalize the bucket name by converting it to lowercase and replacing any invalid characters (like underscores) with hyphens.
4. Create the bucket with:
   ```bash
   tigris buckets create harbor-ttl-${trial_id}
   ```
5. Apply the 7-day expiration TTL with the documented subcommand:
   ```bash
   tigris buckets set-ttl harbor-ttl-${trial_id} --days 7
   ```
6. The container's login shell is pre-wired to expose the Tigris credentials to the CLI: `/etc/profile.d/tigris-auth.sh` maps `TIGRIS_STORAGE_ACCESS_KEY_ID`/`TIGRIS_STORAGE_SECRET_ACCESS_KEY` to the AWS-compatible variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION=auto`) consumed by the `tigris` CLI. If you invoke `tigris` from a non-login shell, source this file first or pass the AWS_* variables inline.

## Constraints
- Project path: `/home/user/ttl-task`
- Bucket name MUST be exactly `harbor-ttl-${trial_id}` where `${trial_id}` is the contents of `/logs/artifacts/trial_id` (trimmed of trailing whitespace). Do NOT hardcode any other suffix. Note: S3 bucket names can only contain lowercase letters, numbers, dots, and hyphens. You must normalize the bucket name by converting it to lowercase and replacing any invalid characters (like underscores) with hyphens.
- TTL MUST be exactly 7 days. Use `--days 7`.
- Use the Tigris CLI (`@tigrisdata/cli`) only — do not configure TTL via raw S3/HTTP, the AWS CLI, or any other tool.
- The bucket must remain provisioned after the task completes so the verifier can inspect it. The verifier will delete the bucket after assertions.

## Integrations
- Tigris Object Storage (credentials provided as `TIGRIS_STORAGE_ACCESS_KEY_ID` and `TIGRIS_STORAGE_SECRET_ACCESS_KEY`).