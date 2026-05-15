# Upload an Object to Tigris using the AWS CLI

## Background
Tigris is an S3-compatible object storage service exposing a single global endpoint at `https://t3.storage.dev`. Because of its S3 compatibility, the standard `aws` CLI can be used against Tigris by pointing it at the Tigris endpoint and providing Tigris access credentials. In this task you will use the AWS CLI to create a bucket and upload a file to it on Tigris.

## Requirements
- Use the standard `aws` CLI (already installed) configured to talk to Tigris.
- Create a Tigris bucket whose name is derived from the trial id.
- Upload the existing local file `/home/user/tigris-task/hello.txt` (contents: literal text `hello tigris`) to that bucket under the key `hello.txt`.

## Implementation Guide
1. Read the trial id from `/logs/artifacts/trial_id`.
2. Construct the bucket name as `harbor-awscli-${trial_id}` (substitute the actual id; do NOT keep the `${trial_id}` placeholder literal).
3. Use the AWS CLI against the Tigris endpoint to create the bucket, for example:
   ```bash
   aws s3 mb s3://harbor-awscli-${trial_id}
   ```
4. Upload the pre-existing file `/home/user/tigris-task/hello.txt` to the bucket:
   ```bash
   aws s3 cp /home/user/tigris-task/hello.txt s3://harbor-awscli-${trial_id}/hello.txt
   ```
5. Confirm the object is listed by running `aws s3 ls s3://harbor-awscli-${trial_id}/`.

## Constraints
- Project path: /home/user/tigris-task
- Pre-existing file: /home/user/tigris-task/hello.txt (contains exactly the bytes `hello tigris`, no trailing newline). Do NOT modify its contents.
- Bucket name format: `harbor-awscli-${trial_id}` where `${trial_id}` is read from `/logs/artifacts/trial_id`.
- The AWS CLI is pre-configured via the environment variables `AWS_ENDPOINT_URL_S3=https://t3.storage.dev`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_REGION=auto`. Do NOT hardcode credentials in any file.
- Use the real Tigris service. Do NOT mock or stub any of the calls.

## Integrations
- Tigris (object storage, accessed via the AWS S3 protocol on `https://t3.storage.dev`)