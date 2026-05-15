FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash && \
    pip3 install --break-system-packages boto3==1.35.36 botocore==1.35.36 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

LABEL Author="any-task-builder"
LABEL Description="Tigris (boto3) environment for the bulk_concurrent_object_upload task. Provides python3 + boto3 and the AWS_ENDPOINT_URL_S3 env var pointing at the Tigris global endpoint."

RUN mkdir -p /home/user && chmod 0755 /home/user

# Pre-create the project working directory; the agent will write bulk.py and
# timing.txt inside it.
RUN mkdir -p /home/user/tigris-task && \
    chmod 0755 /home/user/tigris-task

# Hard-pin the Tigris S3 endpoint so boto3 (which natively reads
# AWS_ENDPOINT_URL_S3) can target Tigris without per-client overrides.
ENV AWS_ENDPOINT_URL_S3="https://t3.storage.dev" \
    AWS_REGION="auto"

# Container contents:
#   - always required libs: curl wget ca-certificates git python3 python3-pip python3-pytest bash
#   - boto3 + botocore (installed via pip with --break-system-packages for Ubuntu 24.04 PEP 668)
#   - /home/user/tigris-task -- empty project directory where the agent must
#     create bulk.py and timing.txt.
#   - AWS_ENDPOINT_URL_S3=https://t3.storage.dev and AWS_REGION=auto baked in
#     so boto3 routes S3 calls to Tigris. Tigris credentials are NOT baked into
#     the image -- they are injected at run time via TIGRIS_STORAGE_ACCESS_KEY_ID
#     and TIGRIS_STORAGE_SECRET_ACCESS_KEY from task.toml.

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
