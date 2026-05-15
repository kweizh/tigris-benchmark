# Create a Snapshot-Enabled Tigris Bucket via CLI

## Background
Tigris is a globally distributed, S3-compatible object storage service. Snapshots and forks are opt-in features that must be enabled at bucket creation time — they cannot be turned on later. The Tigris CLI exposes the `--enable-snapshots` flag on `tigris buckets create` for exactly this purpose. In this task you will use the Tigris CLI to create a brand-new bucket with snapshots enabled in a single command.

## Requirements
- Use the Tigris CLI (`tigris`) to create exactly one new bucket on the real Tigris service (`https://t3.storage.dev`).
- The bucket name MUST be `harbor-snap-${trial_id}`, where `${trial_id}` is the contents of `/logs/artifacts/trial_id`. Note: S3 bucket names can only contain lowercase letters, numbers, dots, and hyphens. You must normalize the bucket name by converting it to lowercase and replacing any invalid characters (like underscores) with hyphens.
- Snapshots MUST be enabled on the bucket at creation time (in the same command — snapshots cannot be enabled later).
- Do NOT upload any objects to the bucket. Just create it.

## Implementation Guide
1. Read the trial id:
   ```bash
   TRIAL_ID="$(cat /logs/artifacts/trial_id)"
   BUCKET="harbor-snap-${TRIAL_ID}"
   ```
2. The Tigris CLI is already installed and the following environment variables are pre-populated for machine authentication (do NOT run `tigris login`, which would try to open a browser):
   - `TIGRIS_STORAGE_ACCESS_KEY_ID`
   - `TIGRIS_STORAGE_SECRET_ACCESS_KEY`
   - `TIGRIS_STORAGE_ENDPOINT` (set to `https://t3.storage.dev`)
3. Create the snapshot-enabled bucket in a single CLI invocation:
   ```bash
   tigris buckets create "$BUCKET" --enable-snapshots
   ```
4. (Optional) Confirm it landed by running `tigris buckets list --format json` and looking for the new bucket name.

## Constraints
- Project path: `/home/user/tigris-task`
- Do NOT hardcode credentials. Use only the env vars listed above.
- Do NOT call `tigris login` — credentials are picked up from the environment automatically.
- The bucket name MUST include the `trial_id` suffix derived from `/logs/artifacts/trial_id` so it is unique per run.
- Snapshots MUST be enabled in the same `tigris buckets create` command (they cannot be enabled on an existing bucket).

## Integrations
- Tigris (`https://t3.storage.dev`)