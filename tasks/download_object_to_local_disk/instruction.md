# Tigris CLI: Download an Object to Local Disk

## Background
Tigris is a globally distributed, S3-compatible object storage service. The `tigris` CLI (`@tigrisdata/cli`) supports S3-style copy semantics via the `tigris cp` command, which understands `t3://<bucket>/<key>` URIs. A common workflow for an AI agent is to pull a pre-seeded asset out of a Tigris bucket onto its local working directory before processing it.

A bucket and object have already been pre-seeded into Tigris by the container's entrypoint script BEFORE the agent starts:

- Bucket: `harbor-download-${trial_id}` (where `${trial_id}` is the content of `/logs/artifacts/trial_id`).
- Object key: `assets/welcome.md`
- Object content (exact bytes, including trailing newline): `# Welcome to Tigris\n`

Your job is to download that object to a local file on disk using the Tigris CLI, without modifying or removing the source object.

## Requirements
Using the `tigris` CLI exclusively, do the following:

1. Read the current `trial_id` from `/logs/artifacts/trial_id`. The bucket name MUST be exactly `harbor-download-${trial_id}` — do NOT hardcode any other suffix.
2. Download the pre-seeded object `assets/welcome.md` from that bucket to the absolute local path `/home/user/tigris-task/welcome.md` using `tigris cp`.
3. Leave the source object in the bucket untouched — the verifier will assert that `tigris ls t3://harbor-download-${trial_id}/assets/welcome.md` still resolves.

## Implementation Guide
1. Open a terminal in the project directory `/home/user/tigris-task`.
2. Determine the trial id and compute the bucket name:
   ```bash
   TRIAL_ID="$(cat /logs/artifacts/trial_id)"
   BUCKET="harbor-download-${TRIAL_ID}"
   ```
3. Run the download:
   ```bash
   tigris cp "t3://${BUCKET}/assets/welcome.md" /home/user/tigris-task/welcome.md
   ```
4. Verify locally that the file exists at `/home/user/tigris-task/welcome.md` and contains exactly the bytes `# Welcome to Tigris\n`.
5. The container is pre-wired to expose the Tigris credentials to the CLI: `/etc/profile.d/tigris-auth.sh` maps `TIGRIS_STORAGE_ACCESS_KEY_ID` / `TIGRIS_STORAGE_SECRET_ACCESS_KEY` to the AWS-compatible variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION=auto`) that the `tigris` CLI consumes. If you invoke `tigris` from a non-login shell, source this file first or pass the AWS_* variables inline.

## Constraints
- Project path: `/home/user/tigris-task`
- Output file MUST be at exactly `/home/user/tigris-task/welcome.md`.
- Bucket name MUST be exactly `harbor-download-${trial_id}` where `${trial_id}` is read from `/logs/artifacts/trial_id`. Do NOT hardcode the suffix.
- Use the Tigris CLI (`@tigrisdata/cli`) only — do not implement the download via raw S3/HTTP calls or other SDKs.
- Do NOT move, rename, overwrite, or delete the source object `t3://harbor-download-${trial_id}/assets/welcome.md`. The verifier asserts the source still exists.
- Do NOT delete the bucket; the verifier cleans it up after assertions.
- The local file `/home/user/tigris-task/welcome.md` must contain EXACTLY the bytes `# Welcome to Tigris\n` (19 bytes total, including the trailing newline).

## Integrations
- Tigris Object Storage (credentials provided as `TIGRIS_STORAGE_ACCESS_KEY_ID` and `TIGRIS_STORAGE_SECRET_ACCESS_KEY`).