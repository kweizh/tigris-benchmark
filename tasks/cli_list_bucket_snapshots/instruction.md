# List Bucket Snapshots with the Tigris CLI

## Background
The Tigris CLI (`@tigrisdata/cli`) gives you a `tigris snapshots list <bucket>` command that prints every point-in-time snapshot of a snapshot-enabled bucket. Each snapshot has a unique numeric `version` (a UNIX nanosecond-precision timestamp) that identifies it across the Tigris control plane.

For this task an operator has pre-populated a snapshot-enabled bucket named `harbor-history-${trial_id}` (where `${trial_id}` is the content of `/logs/artifacts/trial_id`) with several snapshots, but the bucket has to be prepared at task start (the Docker build did not have credentials). A helper script `/home/user/snapshot-list/setup.sh` is already on disk — it reads the admin Tigris credentials from the environment, creates the bucket with snapshots enabled, and takes a fixed sequence of named snapshots. You must run that script first, then list the snapshots with the CLI and persist their IDs (versions) to a text file in chronological order.

## Requirements
1. Run the helper `bash /home/user/snapshot-list/setup.sh` to create the bucket and pre-populate it with snapshots. The script is idempotent and must complete successfully (exit status 0).
2. Use the Tigris CLI to list every snapshot of the bucket. Derive the bucket name as `harbor-history-${trial_id}` (substitute the actual trial id from `/logs/artifacts/trial_id`). Note: S3 bucket names can only contain lowercase letters, numbers, dots, and hyphens. You must normalize the bucket name by converting it to lowercase and replacing any invalid characters (like underscores) with hyphens. Use `tigris snapshots list <bucket_name> --format json` so you can parse the output reliably.
3. Extract the `version` field of every snapshot and write the values to `/home/user/snapshot-list/snapshots.txt`, one snapshot version per line, in **chronological order (oldest first)**. The Tigris API returns snapshots in reverse-chronological order by default — you must reverse them.
4. The file `/home/user/snapshot-list/snapshots.txt` must end with a trailing newline, must not contain blank lines, must not contain any header, JSON, or whitespace around the IDs.
5. Capture all stdout and stderr from your commands to `/home/user/snapshot-list/output.log` for debugging.

## Implementation Guide
1. Change into the project directory: `cd /home/user/snapshot-list`.
2. Execute the setup script and capture its output: `bash setup.sh >>output.log 2>&1`.
3. Configure the Tigris CLI to use the admin credentials provided by the environment if it has not been configured yet (the helper script already does this):
   ```bash
   tigris configure --access-key "$TIGRIS_STORAGE_ACCESS_KEY_ID" --access-secret "$TIGRIS_STORAGE_SECRET_ACCESS_KEY" >>output.log 2>&1
   ```
4. List the snapshots and produce the file. Example using `jq` (already installed):
   ```bash
   tigris snapshots list <bucket_name> --format json \
     | jq -r '.snapshots | reverse | .[].version' >snapshots.txt
   ```
   Other approaches are fine as long as the resulting `snapshots.txt` has the IDs one per line in chronological order.
5. Verify your output with `cat snapshots.txt` — every line must be a numeric snapshot version, with the oldest snapshot at the top and the most recent at the bottom.

## Constraints
- Project path: `/home/user/snapshot-list`
- Log file: `/home/user/snapshot-list/output.log`
- Bucket name MUST be derived from `/logs/artifacts/trial_id` as `harbor-history-${trial_id}`. Note: S3 bucket names can only contain lowercase letters, numbers, dots, and hyphens. You must normalize the bucket name by converting it to lowercase and replacing any invalid characters (like underscores) with hyphens.
- Output file (fixed): `/home/user/snapshot-list/snapshots.txt`
- Do not edit `/home/user/snapshot-list/setup.sh` — you may only execute it.
- Use the real Tigris CLI (`tigris snapshots list`) against the live Tigris service — do not mock or stub the output.
- The admin credentials are available as `TIGRIS_STORAGE_ACCESS_KEY_ID` and `TIGRIS_STORAGE_SECRET_ACCESS_KEY` environment variables.

## Integrations
- Tigris (real `@tigrisdata/cli` and the live Tigris control plane; admin credentials supplied via `TIGRIS_STORAGE_ACCESS_KEY_ID` and `TIGRIS_STORAGE_SECRET_ACCESS_KEY`).