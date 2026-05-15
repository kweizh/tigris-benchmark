# Tigris Data Evaluation Benchmark Plan

Tigris is a globally distributed, S3-compatible object storage service designed for high-performance workloads, particularly AI agentic workflows. This benchmark covers the core storage features, the specialized Agent Kit, and the Tigris CLI.

## 1. Library Overview

* **Description**: Tigris is a serverless, globally distributed object storage service with a single global endpoint (`https://t3.storage.dev`). It provides native S3 compatibility, zero egress fees, and unique features like instant bucket forking and snapshots.
* **Ecosystem Role**: Acts as the primary storage layer for distributed applications and AI agents. It replaces AWS S3, Google Cloud Storage, or Cloudflare R2, offering lower latency for small objects and specialized primitives for agent state management.
* **Project Setup**:
  1. **CLI Installation**: `npm install -g @tigrisdata/cli`
  2. **Authentication**: Use environment variables for machine access:

   ```bash
   export TIGRIS_STORAGE_ACCESS_KEY_ID=tid_...
   export TIGRIS_STORAGE_SECRET_ACCESS_KEY=tsec_...
   export TIGRIS_STORAGE_ENDPOINT=https://t3.storage.dev
   ```

  3. **SDK Installation**: `npm install @tigrisdata/storage @tigrisdata/agent-kit`

## 2. Core Primitives & APIs

### A. Tigris CLI (`tigris`)

The CLI manages buckets and objects. It supports standard S3-like operations and Tigris-specific features.

* **Bucket Management**:

  ```bash
  # Create a bucket with snapshots enabled (required for forks/checkpoints)
  tigris buckets create my-bucket --enable-snapshots

  # List all buckets
  tigris buckets list

  # Set TTL for objects (auto-expiration)
  tigris buckets set-ttl my-bucket --days 7
  ```

* **Object Operations**:

  ```bash
  # Upload an object
  tigris cp ./local-file.txt t3://my-bucket/remote-file.txt

  # List objects
  tigris ls t3://my-bucket/
  ```

### B. Storage SDK (`@tigrisdata/storage`)

The native TypeScript SDK for direct bucket and object manipulation.

```typescript
import { createBucket, putObject, listObjects } from "@tigrisdata/storage";
// Create a bucket
const { data, error } = await createBucket("agent-storage", { enableSnapshot: true });
// Upload an object
await putObject("agent-storage", "logs/run-1.json", JSON.stringify({ status: "ok" }));
// List objects with prefix
const objects = await listObjects("agent-storage", { prefix: "logs/" });
```

*Documentation:* [Tigris SDK Reference](https://www.tigrisdata.com/docs/sdks/tigris/)

### C. Agent Kit (`@tigrisdata/agent-kit`)

Specialized primitives for AI agent workflows: **Workspaces**, **Forks**, **Checkpoints**, and **Coordination**.

* **Workspaces**: Ephemeral buckets with scoped credentials and TTL.

  ```typescript
  import { createWorkspace, teardownWorkspace } from "@tigrisdata/agent-kit";
  const { data: workspace, error } = await createWorkspace("agent-run-42", {
  ttl: { days: 1 },
  credentials: { role: "Editor" } // Mints a scoped access key
  });

  // workspace.credentials.accessKeyId is scoped ONLY to this bucket
  ```

* **Forks & Checkpoints**: Instant copy-on-write clones for parallel evaluation.

  ```typescript
  import { checkpoint, restore, createForks } from "@tigrisdata/agent-kit";
  // Take a point-in-time snapshot
  const { data: ckpt } = await checkpoint("production-data", { name: "before-eval" });
  // Restore to a new bucket for safe experimentation
  const { data: restored } = await restore("production-data", ckpt.snapshotId, {
   forkName: "experiment-sandbox"
  });
  ```

*Documentation:* [Agent Kit Docs](https://www.tigrisdata.com/docs/ai/agent-kit/)

## 3. Real-World Use Cases & Templates

* **Parallel Agent Evaluation**: Using `createForks(baseBucket, count)` to give 10 different agents their own isolated, writable copy of a 1TB dataset instantly.
* **Ephemeral Scratch Pads**: Using `createWorkspace` with a 1-hour TTL for agent intermediate steps, ensuring no data leakage or cost accumulation.
* **Event-Driven Pipelines**: Using `setupCoordination` to trigger a "Summarizer" agent as soon as a "Collector" agent finishes writing a JSON file to a specific prefix.

## 4. Developer Friction Points

1. **Snapshot Requirement**: Forks and Checkpoints fail silently or with errors if the source bucket was not created with `--enable-snapshots`. This is a common configuration pitfall. ([Issue Reference](https://www.tigrisdata.com/docs/ai/agent-kit/#troubleshooting))
2. **Partial Failures**: In `createWorkspace`, the bucket might be created, but the IAM key generation might fail due to quotas. Agents must check for `workspace.credentials` explicitly.
3. **Force Deletion**: The CLI and SDK require a `force` flag to delete buckets that are not empty. Forgetting this leads to "BucketNotEmpty" errors during cleanup.

## 5. Evaluation Ideas

1. **Workspace Lifecycle**: Implement a script that creates a workspace with a 1-day TTL, uploads a "state.json" file using the scoped credentials, and then tears it down cleanly.
2. **Parallel Forking**: Use the CLI to enable snapshots on a bucket, then use the Agent Kit to create 3 concurrent forks with "ReadOnly" credentials for parallel data processing.
3. **Checkpoint & Rollback**: Simulate a "risky" agent operation by taking a checkpoint, performing writes, and then "rolling back" by restoring the checkpoint to a fresh bucket.
4. **Webhook Coordination**: Set up a coordination filter that only triggers a webhook when files with a `.finished` extension are uploaded to a specific prefix.
5. **CLI-SDK Interop**: Use the CLI to create a bucket and set a TTL, then use the SDK to verify the bucket configuration and upload an object.
6. **S3 Migration (Shadow Buckets)**: Configure a Tigris bucket to "shadow" an existing S3 bucket, demonstrating zero-downtime migration by reading a file that exists only in S3 through the Tigris endpoint.

## 6. Sources

1. [Tigris llms.txt](https://www.tigrisdata.com/llms.txt) - Core product overview and environment variables.
2. [Tigris Agent Kit Documentation](https://www.tigrisdata.com/docs/ai/agent-kit/) - Detailed primitives for AI agents.
3. [Tigris CLI Reference](https://www.tigrisdata.com/docs/cli/) - Installation and command usage.
4. [Object Notifications (Coordination)](https://www.tigrisdata.com/docs/buckets/object-notifications/) - Webhook payload and filtering logic.
5. [Tigris SDK on NPM](https://www.npmjs.com/package/@tigrisdata/storage) - Native storage client documentation.