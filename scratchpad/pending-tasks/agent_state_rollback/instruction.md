When an agent pipeline fails or corrupts data, a previously taken checkpoint can be used to restore the "known-good" state into a completely new fork. This allows developers to debug the failed run without losing the original state or impacting other agents.

You need to write a rollback function that takes an existing `snapshotId` and restores the state of the "agent-data" bucket into a new testing environment. Set the new fork name to "investigation-fork" and return the newly generated bucket's configuration object.

**Constraints:**
- You MUST use the `restore` API from `@tigrisdata/agent-kit`.
- Do NOT perform any mutating operations on the original "agent-data" bucket.