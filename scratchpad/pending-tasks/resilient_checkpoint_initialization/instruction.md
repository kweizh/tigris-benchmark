Checkpoints allow developers to snapshot a bucket's state before an agent performs risky writes. However, the `checkpoint` operation will fail if snapshots are not explicitly enabled on the source bucket.

You need to write a robust initialization function that attempts to take a checkpoint named "stable-v1" for a bucket named "agent-data" in a debugging environment. If the operation fails due to missing snapshot configurations, catch the error and return a specific string prompting the user to enable snapshots via the CLI.

**Constraints:**
- Do NOT execute shell commands to enable snapshots programmatically.
- If the checkpoint fails, return the exact string: "Please run: tigris buckets create agent-data --enable-snapshots".
- If successful, return the resulting `snapshotId`.