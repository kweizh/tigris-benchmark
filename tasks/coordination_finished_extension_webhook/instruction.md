# Tigris Coordination: trigger only on `runs/*.finished` objects

## Background
The Tigris Agent Kit (`@tigrisdata/agent-kit`) provides a `setupCoordination` primitive that wires Tigris object notifications to a webhook URL with an optional SQL-like filter on the object `key`. Tigris webhooks POST a JSON payload (see https://www.tigrisdata.com/docs/buckets/object-notifications/) of the form `{ "events": [{ ..., "bucket": "...", "object": { "key": "...", "size": ..., "eTag": "..." } }] }` for every matching object event.

The goal of this task is to provision a Tigris bucket, install a coordination rule that triggers **only** for object keys that both **start with `runs/`** and **end with the `.finished` extension**, then upload three test objects and demonstrate that exactly the one matching object fires a webhook delivery.

The container is pre-wired with two services running in the background:

1. A tiny Node.js HTTP receiver listening on `http://localhost:8088/receive` that **appends each JSON POST body verbatim** as a single line to `/home/user/tigris-task/received.jsonl`.
2. A `cloudflared` quick-tunnel pointing at `http://localhost:8088`. The container's entrypoint waits for the tunnel to come up and writes the public HTTPS URL to `/home/user/tigris-task/tunnel.url` (one line, e.g. `https://random-words.trycloudflare.com`).

You must use that public URL as the webhook target (Tigris's notification system cannot reach the container's `localhost` directly).

## Requirements
Write and execute a TypeScript program `/home/user/tigris-task/run.ts` that performs the following steps in order using the Tigris SDKs and exits with code 0 on success:

1. Read `trial_id` from `/logs/artifacts/trial_id` and `.trim()` it.
2. Build the bucket name `harbor-coord-${trial_id}` (lowercase trial id). Note: S3 bucket names can only contain lowercase letters, numbers, dots, and hyphens. You must normalize the bucket name by converting it to lowercase and replacing any invalid characters (like underscores) with hyphens.
3. Read the public webhook base URL from `/home/user/tigris-task/tunnel.url` and append `/receive` to form the final `webhookUrl`. If the tunnel URL file is missing or empty, retry with backoff for up to 60 seconds before failing.
4. Use `createBucket` from `@tigrisdata/storage` to create the bucket. Snapshots are **not** required. If `createBucket` reports the bucket already exists, treat that as success.
5. Use `setupCoordination` from `@tigrisdata/agent-kit` to register a notification rule on the bucket with:
   - `webhookUrl` set to `${publicTunnel}/receive`.
   - `filter` set to a SQL-like expression that matches keys with prefix `runs/` and suffix `.finished`. The recommended filter is: `` WHERE `key` REGEXP "^runs/.*\\.finished$" `` (escape the backslash inside the JS/TS string).
6. Wait at least 5 seconds for the coordination rule to propagate.
7. Upload the following three objects to the bucket using `put` from `@tigrisdata/storage` (set `Content-Type: text/plain` for each):
   - `runs/run1.tmp` with body `not done yet` (must NOT fire the webhook).
   - `runs/run1.finished` with body `done` (MUST fire the webhook exactly once).
   - `other/run2.finished` with body `wrong prefix` (must NOT fire the webhook because the prefix does not match).
8. Wait up to 30 seconds for notifications to be delivered to the receiver.
9. Write a one-line summary to `/home/user/tigris-task/run.log` containing the bucket name and the resolved webhook URL, so the verifier can read back what was attempted.

Run the program with `tsx /home/user/tigris-task/run.ts`. Do not mock any Tigris service: real Tigris credentials are exposed via the environment.

## Implementation Guide
1. `cd /home/user/tigris-task`. The directory already has a `package.json`, a `tsconfig.json`, and a pre-populated `node_modules` with `@tigrisdata/storage`, `@tigrisdata/agent-kit`, and `tsx`.
2. Create `run.ts` (ESM, top-level await is fine). Sketch:
   ```typescript
   import { readFile, writeFile, stat } from "node:fs/promises";
   import { createBucket, put } from "@tigrisdata/storage";
   import { setupCoordination } from "@tigrisdata/agent-kit";

   const trialId = (await readFile("/logs/artifacts/trial_id", "utf-8")).trim();
   const bucket = `harbor-coord-${trialId}`;

   // Poll for tunnel.url for up to 60s
   async function readTunnel(): Promise<string> {
     for (let i = 0; i < 60; i++) {
       try {
         const raw = (await readFile("/home/user/tigris-task/tunnel.url", "utf-8")).trim();
         if (raw) return raw;
       } catch {}
       await new Promise((r) => setTimeout(r, 1000));
     }
     throw new Error("tunnel.url not ready");
   }
   const base = await readTunnel();
   const webhookUrl = `${base.replace(/\/$/, "")}/receive`;

   const created = await createBucket(bucket);
   if (created.error && !/exist/i.test(String(created.error.message))) throw created.error;

   const coord = await setupCoordination(bucket, {
     webhookUrl,
     filter: 'WHERE `key` REGEXP "^runs/.*\\.finished$"',
   });
   if (coord.error) throw coord.error;

   await new Promise((r) => setTimeout(r, 5000));

   const uploads: Array<[string, string]> = [
     ["runs/run1.tmp", "not done yet"],
     ["runs/run1.finished", "done"],
     ["other/run2.finished", "wrong prefix"],
   ];
   for (const [key, body] of uploads) {
     const r = await put(key, body, { config: { bucket }, contentType: "text/plain" });
     if (r.error) throw r.error;
   }

   await new Promise((r) => setTimeout(r, 30000));

   await writeFile(
     "/home/user/tigris-task/run.log",
     `bucket=${bucket}\nwebhookUrl=${webhookUrl}\n`,
   );
   ```
3. Run with `tsx run.ts` from `/home/user/tigris-task`.
4. Inspect `/home/user/tigris-task/received.jsonl` to debug: it should contain a JSON line with `events[0].object.key === "runs/run1.finished"` and nothing else.

## Constraints
- Project path: /home/user/tigris-task
- Source file: /home/user/tigris-task/run.ts
- Log file: /home/user/tigris-task/run.log
- Tunnel URL file (pre-populated by the entrypoint): /home/user/tigris-task/tunnel.url
- Received notifications file (pre-created empty, appended to by the receiver): /home/user/tigris-task/received.jsonl
- Bucket name: `harbor-coord-${trial_id}` (read `${trial_id}` from `/logs/artifacts/trial_id`). Note: S3 bucket names can only contain lowercase letters, numbers, dots, and hyphens. You must normalize the bucket name by converting it to lowercase and replacing any invalid characters (like underscores) with hyphens.
- Use the **real** Tigris service via `@tigrisdata/storage` and `@tigrisdata/agent-kit`. Do not mock the webhook delivery — Tigris must actually POST to the tunnel.
- Do not hardcode credentials. The SDKs read them from `TIGRIS_STORAGE_ACCESS_KEY_ID`, `TIGRIS_STORAGE_SECRET_ACCESS_KEY`, `TIGRIS_STORAGE_ENDPOINT`.
- Do not stop, kill, or restart the pre-running receiver (`node ... receiver.js`) or the `cloudflared` tunnel process.
- The notification filter must encode **both** the `runs/` prefix and the `.finished` suffix. A filter that matches every key or only one of the two constraints will cause the verifier to fail (extra or missing notifications).

## Integrations
- Tigris Data (real `https://t3.storage.dev` endpoint via `@tigrisdata/storage` + `@tigrisdata/agent-kit`).
- Cloudflare quick-tunnel (`cloudflared`) is used purely to expose the local receiver to Tigris's notification system; you only need to read the URL it produced.
