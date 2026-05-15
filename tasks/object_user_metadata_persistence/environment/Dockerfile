FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash \
        unzip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN ARCH="$(uname -m)" && \
    if [ "$ARCH" = "x86_64" ]; then \
        AWS_ZIP_URL="https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip"; \
    elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then \
        AWS_ZIP_URL="https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip"; \
    else \
        echo "Unsupported architecture: $ARCH" && exit 1; \
    fi && \
    curl -fsSL "$AWS_ZIP_URL" -o /tmp/awscliv2.zip && \
    unzip -q /tmp/awscliv2.zip -d /tmp && \
    /tmp/aws/install && \
    rm -rf /tmp/aws /tmp/awscliv2.zip

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="any-task-builder"
LABEL Description="Ubuntu 24.04 with the official AWS CLI v2 installed for use against the Tigris S3-compatible endpoint, plus a pre-staged report.txt file for the user-metadata persistence task."

RUN mkdir -p /home/user/tigris-task && \
    printf 'quarterly report' > /home/user/tigris-task/report.txt

# Container contents:
#   - AWS CLI v2 installed from awscli.amazonaws.com for talking to Tigris
#     (S3-compatible global endpoint at https://t3.storage.dev).
#   - /home/user/tigris-task: working directory for the task.
#   - /home/user/tigris-task/report.txt: pre-existing file containing the
#     literal bytes "quarterly report" (no trailing newline) to be uploaded
#     by the agent with custom user metadata and a specific content type.

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
