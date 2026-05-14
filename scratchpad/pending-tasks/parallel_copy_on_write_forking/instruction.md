Running multi-agent evaluations against large datasets requires instant copy-on-write clones via `createForks` to avoid duplicating storage costs. However, reusing a prefix in this function without cleaning up previous runs often causes naming collisions.

You need to fork a source bucket named "prod-corpus" into 3 distinct forks for parallel testing in an evaluation runner. To prevent naming collisions, generate a unique prefix using the current UNIX timestamp, and output the resulting bucket names of the 3 generated forks to `stdout`.

**Constraints:**
- You MUST request exactly 3 forks and grant them "ReadOnly" credentials.
- You MUST generate a dynamic prefix containing a timestamp to avoid naming conflicts from previous executions.