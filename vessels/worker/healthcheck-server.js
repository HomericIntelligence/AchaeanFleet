// Minimal health server for the worker vessel — no external dependencies.
// Responds {"status":"ok"} on GET /health and keeps the container alive.
// Reads AGENT_PORT from env (default 23001).
'use strict';

const http = require('http');
const port = parseInt(process.env.AGENT_PORT || '23001', 10);

http.createServer((req, res) => {
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
