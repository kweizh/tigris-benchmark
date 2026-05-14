Agents require isolated, reproducible environments with limited lifetimes. The `createWorkspace` function provisions per-agent buckets with TTL and scoped credentials, but IAM quota limits can sometimes cause silent partial failures where the bucket is created without credentials.

You need to write a TypeScript script that creates a workspace named "agent-eval-01" with a 1-day TTL and "Editor" credentials in a Node.js environment. Your script must explicitly verify that the `credentials` object is present in the response before using them to simulate a file upload.

**Constraints:**
- You MUST use the `@tigrisdata/agent-kit` library.
- You MUST handle the silent partial failure by throwing an error with the exact message "IAM credentials missing" if the `credentials` object is undefined.