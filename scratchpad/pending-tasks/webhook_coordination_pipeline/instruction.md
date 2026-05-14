Agent pipelines can be orchestrated using event-driven triggers via bucket webhooks, avoiding the inefficiency of constant polling. Coordination can watch specific prefixes and automatically trigger downstream agents when new files arrive.

You need to use `setupCoordination` to configure an event trigger on the "output-bucket" in a Node.js orchestrator. Set the webhook URL to "https://api.myapp.com/webhook" so that it triggers a "Reviewer Agent" whenever a "Writer Agent" saves a file to the `results/` prefix.

**Constraints:**
- You MUST apply the exact filter: `WHERE \`key\` REGEXP "^results/"`.
- You MUST authenticate the webhook payload by passing the `WEBHOOK_SECRET` environment variable into the auth token configuration.