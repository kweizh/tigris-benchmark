Ephemeral resources like Workspaces and Forks must be explicitly torn down after an evaluation or agent run completes. Failing to do so leads to naming collisions on subsequent runs and clutters the storage environment.

You need to implement a teardown utility function that accepts both a `Workspace` object and a `ForkSet` object in an evaluation script. Ensure both `teardownWorkspace` and `teardownForks` are called to completely remove the isolated test resources.

**Constraints:**
- You MUST ensure both teardown operations are executed independently (e.g., using `Promise.allSettled` or separate try/catch blocks) so that if one fails, the other still runs.
- You MUST log any teardown errors to `console.error` without crashing the main process.