FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl wget ca-certificates git python3 python3-pip python3-pytest bash && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g tsx@4.19.2 typescript@5.6.3 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install cloudflared (used for the quick-tunnel that exposes the local receiver to Tigris).
RUN ARCH="$(dpkg --print-architecture)" && \
    case "$ARCH" in \
        amd64) CF_ARCH=amd64 ;; \
        arm64) CF_ARCH=arm64 ;; \
        armhf) CF_ARCH=arm ;; \
        *) echo "Unsupported arch: $ARCH" >&2; exit 1 ;; \
    esac && \
    curl -fsSL -o /tmp/cloudflared.deb \
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${CF_ARCH}.deb" && \
    apt-get update -y && \
    apt-get install -y --no-install-recommends /tmp/cloudflared.deb && \
    rm -f /tmp/cloudflared.deb && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="any-task-builder"
LABEL Description="Tigris coordination/webhook task: Node 24, @tigrisdata/storage + @tigrisdata/agent-kit, cloudflared quick-tunnel, and a local HTTP notification receiver pre-wired."

RUN mkdir -p /home/user/tigris-task && \
    cd /home/user/tigris-task && \
    cat > package.json <<'EOF'
{
  "name": "tigris-coord-task",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "start": "tsx run.ts"
  },
  "dependencies": {
    "@tigrisdata/storage": "^3.0.0",
    "@tigrisdata/agent-kit": "^0.1.0"
  },
  "devDependencies": {
    "tsx": "^4.19.2",
    "typescript": "^5.6.3",
    "@types/node": "^22.7.5"
  }
}
EOF

RUN cd /home/user/tigris-task && \
    cat > tsconfig.json <<'EOF'
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "Bundler",
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": false,
    "outDir": "dist"
  },
  "include": ["*.ts"]
}
EOF

RUN cd /home/user/tigris-task && npm install --no-audit --no-fund

# Local HTTP receiver that appends every JSON POST body to /home/user/tigris-task/received.jsonl.
RUN mkdir -p /usr/local/lib/tigris-receiver && \
    cat > /usr/local/lib/tigris-receiver/receiver.js <<'EOF'
const http = require('http');
const fs = require('fs');
const path = require('path');

const OUTPUT = '/home/user/tigris-task/received.jsonl';
const PORT = parseInt(process.env.RECEIVER_PORT || '8088', 10);

fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
try { fs.closeSync(fs.openSync(OUTPUT, 'a')); } catch (_) {}

const server = http.createServer((req, res) => {
  const chunks = [];
  req.on('data', (c) => chunks.push(c));
  req.on('end', () => {
    const raw = Buffer.concat(chunks).toString('utf-8').trim();
    if (req.method === 'POST' && raw) {
      try {
        JSON.parse(raw);
        fs.appendFileSync(OUTPUT, raw + '\n');
      } catch (_e) {
        fs.appendFileSync(OUTPUT, JSON.stringify({ _malformed: raw }) + '\n');
      }
    }
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end('{"ok":true}');
  });
  req.on('error', () => {
    try { res.writeHead(500); res.end(); } catch (_) {}
  });
});

server.listen(PORT, '0.0.0.0', () => {
  console.log('[receiver] listening on 0.0.0.0:' + PORT + ' -> ' + OUTPUT);
});
EOF

# Entrypoint that starts the receiver + cloudflared quick-tunnel and waits for the public URL.
RUN cat > /usr/local/bin/start-tigris-services.sh <<'EOF'
#!/usr/bin/env bash
mkdir -p /home/user/tigris-task
: > /home/user/tigris-task/received.jsonl
rm -f /home/user/tigris-task/tunnel.url

# Start the local HTTP receiver.
node /usr/local/lib/tigris-receiver/receiver.js >/tmp/receiver.log 2>&1 &

# Start the cloudflared quick-tunnel pointing at the receiver.
: > /tmp/tunnel.log
cloudflared tunnel --url http://localhost:8088 --no-autoupdate >/tmp/tunnel.log 2>&1 &

# Wait up to 120s for the public URL to appear in cloudflared's log.
for i in $(seq 1 120); do
  URL=$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' /tmp/tunnel.log 2>/dev/null | head -1)
  if [ -n "$URL" ]; then
    echo "$URL" > /home/user/tigris-task/tunnel.url
    break
  fi
  sleep 1
done

trap : TERM INT
sleep infinity & wait
EOF

RUN chmod +x /usr/local/bin/start-tigris-services.sh

# Container contents:
#   - Ubuntu 24.04 base
#   - Node.js v24 + npm
#   - global: tsx, typescript
#   - cloudflared (Cloudflare quick-tunnel client)
#   - /home/user/tigris-task: project pre-initialized with @tigrisdata/storage + @tigrisdata/agent-kit
#   - /usr/local/lib/tigris-receiver/receiver.js: HTTP receiver appending payloads to /home/user/tigris-task/received.jsonl
#   - /usr/local/bin/start-tigris-services.sh: container entrypoint that launches the receiver and cloudflared,
#     then writes the public tunnel URL to /home/user/tigris-task/tunnel.url

CMD ["/usr/local/bin/start-tigris-services.sh"]
