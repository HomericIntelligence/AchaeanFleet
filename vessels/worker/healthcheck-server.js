// Minimal health server for the worker vessel — no external dependencies.
// Responds {"status":"ok"} on GET /health and keeps the container alive.
// Reads AGENT_PORT from env (default 23001).
'use strict';

const http = require('http');
const port = parseInt(process.env.AGENT_PORT || '23001', 10);

const server = http.createServer((req, res) => {
  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok' }));
  } else {
    res.writeHead(404);
    res.end();
  }
}).listen(port, '0.0.0.0', () => {
  process.stdout.write(`health server listening on :${port}\n`);
});

// Graceful shutdown on container stop signals (SIGTERM/SIGINT). Without
// these handlers Node exits via the default behaviour, which can leave
// in-flight /health responses unsent and forces the runtime to wait the
// full docker-stop grace period before SIGKILL. See issue #584.
function shutdown(signal) {
  process.stdout.write(`received ${signal}, closing health server\n`);
  server.close((err) => {
    if (err) {
      process.stderr.write(`health server close error: ${err.message}\n`);
      process.exit(1);
    }
    process.exit(0);
  });
  // Safety net: if close() does not return within 10s, force-exit so the
  // container doesn't sit waiting for SIGKILL.
  setTimeout(() => process.exit(0), 10000).unref();
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
