### 1. Library Overview
*   **Description**: Tigris Agent Kit is a TypeScript library that provides high-level storage primitives specifically designed for AI agents. It abstracts complex sequences of S3 and IAM API calls into four core workflows: Forks, Workspaces, Checkpoints, and Coordination.
*   **Ecosystem Role**: It sits below agent frameworks (like LangGraph or CrewAI) as a storage and credential management layer. It ensures agents have isolated, reproducible, and self-cleaning storage environments.
*   **Project Setup**:
    1.  Install the package: `npm install @tigrisdata/agent-kit`.
    2.  Configure environment variables for the cloud platform:
        ```bash
        TIGRIS_STORAGE_ACCESS_KEY_ID=tid_...
        TIGRIS_STORAGE_SECRET_ACCESS_KEY=tsec_...
        TIGRIS_STORAGE_ENDPOINT=https://t3.storage.dev # Optional override
        ```
    3.  (CLI) Install Tigris CLI: `npm i -g @tigrisdata/cli` and run `tigris login`.
### 2. Core Primitives & APIs
*   **Workspaces**: Provision per-agent buckets with TTL and scoped credentials.
    ```typescript
    import { createWorkspace, teardownWorkspace } from "@tigrisdata/agent-kit";
    
    const { data: workspace, error } = await createWorkspace("agent-run-42", {
      ttl: { days: 1 },
      credentials: { role: "Editor" }
    });
    
    if (error) throw error;
    console.log(workspace.bucket, workspace.credentials);
    // Cleanup
    await teardownWorkspace(workspace);
    ```
    *   [Workspaces Documentation](https://www.tigrisdata.com/docs/ai/agent-kit/#workspaces)
*   **Forks**: Instant copy-on-write clones of a source bucket for parallel agents.
    ```typescript
    import { createForks, teardownForks } from "@tigrisdata/agent-kit";
    
    const { data: forkSet, error } = await createForks("prod-data", 3, {
      prefix: "eval-run",
      credentials: { role: "ReadOnly" }
    });
    
    if (error) throw error;
    forkSet.forks.forEach(f => console.log(f.bucket));
    await teardownForks(forkSet);
    ```
    *   [Forks Documentation](https://www.tigrisdata.com/docs/ai/agent-kit/#forks)
*   **Checkpoints & Restore**: Snapshot bucket state and restore into new forks for debugging or rollback.
    ```typescript
    import { checkpoint, restore } from "@tigrisdata/agent-kit";
    
    const { data: ckpt } = await checkpoint("my-bucket", { name: "stable-v1" });    const { data: restored } = await restore("my-bucket", ckpt.snapshotId, {
      forkName: "investigation-fork"
    });
    ```
    *   [Checkpoints Documentation](https://www.tigrisdata.com/docs/ai/agent-kit/#checkpoints)
*   **Coordination**: Event-driven triggers using bucket webhooks (no polling).
    ```typescript
    import { setupCoordination } from "@tigrisdata/agent-kit";
    
    await setupCoordination("output-bucket", {
      webhookUrl: "https://api.myapp.com/webhook",
      filter: 'WHERE `key` REGEXP "^results/"',
      auth: { token: process.env.WEBHOOK_SECRET }
    });
    ```
    *   [Coordination Documentation](https://www.tigrisdata.com/docs/ai/agent-kit/#coordination)
### 3. Real-World Use Cases & Templates
*   **Multi-Agent Evals**: Forking a 1TB "gold dataset" into 50 isolated environments for parallel testing without duplicating storage costs.
*   **Agentic Debugging**: Taking a checkpoint before an agent performs a "risky" write (e.g., modifying code or data) to allow instant rollback if the agent fails.
*   **Pipeline Orchestration**: Using Coordination to trigger a "Reviewer Agent" automatically when a "Writer Agent" saves a file to a specific prefix.
### 4. Developer Friction Points
*   **Snapshot Requirement**: `createForks` and `checkpoint` fail if snapshots aren't explicitly enabled on the bucket (`tigris buckets create <name> --enable-snapshots`).
*   **Silent Partial Failures**: If a bucket is created but IAM key generation fails (due to quota), the function returns the bucket but `credentials` will be `undefined`. Users must check for this.
*   **Naming Collisions**: Reusing a `prefix` in `createForks` without cleaning up previous runs will cause naming conflicts.
### 5. Evaluation Ideas
*   **Isolated Workspace**: Implement a script that creates a workspace with a 1-day TTL, uploads a "hello.txt" using the scoped credentials, and then tears it down.
*   **Parallel Eval Runner**: Fork a "corpus" bucket for 3 agents, each performing a unique write, and verify that the source bucket remains unchanged.
*   **Rollback Mechanism**: Simulate a failed agent run by modifying a bucket, then use a previously taken checkpoint to restore the "known-good" state into a new fork.
*   **Event-Driven Pipeline**: Configure coordination to watch a specific prefix and verify the webhook configuration (mocking the trigger).
*   **Resilient Setup**: Write a robust initialization function that enables snapshots on a bucket if they aren't already enabled before taking a checkpoint.
### 6. Sources
1.  [Tigris Agent Kit Documentation](https://www.tigrisdata.com/docs/ai/agent-kit/): Main documentation for the library.
2.  [Introducing Agent Kit (Blog)](https://www.tigrisdata.com/blog/agent-kit/): High-level overview and design philosophy.
3.  [Tigris llms.txt](https://www.tigrisdata.com/llms.txt): Technical summary of Tigris storage and AI integrations.
4.  [Tigris CLI Reference](https://www.tigrisdata.com/docs/cli/): Instructions for bucket management and snapshot configuration.