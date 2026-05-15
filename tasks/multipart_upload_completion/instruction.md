# Multipart Upload of a Large Object to Tigris with the AWS CLI

## Background
Tigris is an S3-compatible object storage service exposing a single global endpoint at `https://t3.storage.dev`. The standard `aws` CLI can be used against Tigris by configuring the S3 endpoint URL. For objects larger than the `multipart_threshold`, the AWS CLI automatically uses the S3 multipart upload protocol (`CreateMultipartUpload` / `UploadPart` / `CompleteMultipartUpload`). In this task you will force the AWS CLI to upload a 16 MiB file to Tigris using multipart upload with a small chunk size, then record the local file's MD5 fingerprint so the verifier can confirm end-to-end integrity.

## Requirements
- Create a Tigris bucket named `harbor-mpu-${trial_id}` (where `${trial_id}` is the content of `/logs/artifacts/trial_id`).
- Configure the AWS CLI so the multipart threshold and chunk size are both 5 MB, ensuring a 16 MiB upload is performed as a multipart upload (≥4 parts).
- Upload the pre-existing local file `/home/user/tigris-task/large.bin` (16 MiB, deterministic content) to the bucket under the object key `archives/large.bin` using `aws s3 cp` with `--cli-write-timeout 0`.
- Compute the MD5 (hex digest) of the local file and write it (exactly 32 lowercase hex characters, no trailing newline allowed beyond a single optional `\n`) to `/home/user/tigris-task/local.md5`.

## Implementation Guide
1. Read the trial id:
   ```bash
   TRIAL_ID="$(cat /logs/artifacts/trial_id)"
   BUCKET="harbor-mpu-${TRIAL_ID}"
   ```
2. Create the Tigris bucket via the AWS CLI:
   ```bash
   aws s3 mb "s3://${BUCKET}"
   ```
3. Force a small multipart threshold/chunk size so the 16 MiB upload is performed as a multipart upload:
   ```bash
   aws configure set default.s3.multipart_threshold 5MB
   aws configure set default.s3.multipart_chunksize 5MB
   ```
4. Upload the file using multipart upload:
   ```bash
   aws s3 cp --cli-write-timeout 0 \
       /home/user/tigris-task/large.bin \
       "s3://${BUCKET}/archives/large.bin"
   ```
5. Compute the local file's MD5 and write it to `/home/user/tigris-task/local.md5`:
   ```bash
   md5sum /home/user/tigris-task/large.bin | awk '{print $1}' > /home/user/tigris-task/local.md5
   ```
6. (Optional) Confirm the upload worked: `aws s3api head-object --bucket "${BUCKET}" --key archives/large.bin`. The returned `ETag` should contain a `-` followed by the part count (multipart ETag format).

## Constraints
- Project path: /home/user/tigris-task
- Pre-existing file: /home/user/tigris-task/large.bin (exactly 16 MiB = 16777216 bytes of NUL bytes, generated deterministically with `dd if=/dev/zero bs=1048576 count=16`). Do NOT modify or regenerate this file.
- Bucket name format: `harbor-mpu-${trial_id}` where `${trial_id}` is read from `/logs/artifacts/trial_id`.
- Object key: `archives/large.bin` (note the `archives/` prefix).
- Output file: /home/user/tigris-task/local.md5 (32 lowercase hex characters representing the MD5 of `large.bin`).
- The AWS CLI is pre-configured via the environment variables `AWS_ENDPOINT_URL_S3=https://t3.storage.dev`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_REGION=auto`. Do NOT hardcode credentials in any file.
- Use the real Tigris service. Do NOT mock or stub any of the calls.

## Integrations
- Tigris (object storage, accessed via the AWS S3 protocol on `https://t3.storage.dev`)