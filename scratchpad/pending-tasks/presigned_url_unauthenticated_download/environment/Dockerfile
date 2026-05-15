FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash && \
    pip3 install --break-system-packages boto3 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

LABEL Author="any-task-builder"
LABEL Description="Python 3 + boto3 + curl environment for minting a Tigris S3 SigV4 presigned URL and fetching it unauthenticated via curl."

RUN mkdir -p /home/user && chmod 0755 /home/user
RUN mkdir -p /home/user/tigris-task && chmod 0755 /home/user/tigris-task

# Container contents:
#   - always required libs: curl wget ca-certificates git python3 python3-pip python3-pytest bash
#   - boto3 (installed via pip3 --break-system-packages) for S3-compatible access to Tigris,
#     in particular `s3_client.generate_presigned_url(...)`
#   - curl for fetching the presigned URL with no auth headers/env
#   - /home/user/tigris-task — empty project directory where the agent will write
#     presigned.url and downloaded.txt
#
# Runtime expectations (provided by Harbor via task.toml, NOT baked into the image):
#   - AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (mapped from TIGRIS_STORAGE_*)
#   - AWS_ENDPOINT_URL_S3 = https://t3.storage.dev
#   - AWS_REGION          = auto
#   - /logs/artifacts/trial_id (mounted by Harbor) supplies the per-trial bucket suffix

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
