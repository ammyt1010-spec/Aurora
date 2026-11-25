/** Static AURORA build and same-origin API for a dedicated Funnel path. */
import { createServer, request as httpRequest } from 'node:http';
import { createReadStream, existsSync, statSync } from 'node:fs';
import { resolve, extname, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(fileURLToPath(new URL('../frontend/dist/', import.meta.url)));
const prefix = (process.env.AURORA_PUBLIC_BASE_PATH ?? '/aurora').replace(/\/$/, '');
const port = Number(process.env.AURORA_PUBLIC_PORT || 8090);
const apiPort = Number(process.env.AURORA_PUBLIC_API_PORT || 8004);
const mime = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.ico': 'image/x-icon', '.woff': 'font/woff', '.woff2': 'font/woff2',
  '.webp': 'image/webp', '.json': 'application/json; charset=utf-8',
  '.pdf': 'application/pdf',
};

if (!existsSync(resolve(root, 'index.html'))) {
  throw new Error(`Falta la compilación de AURORA en ${root}`);
}

function sendFile(res, file, method) {
  const stat = statSync(file);
  res.writeHead(200, {
    'Content-Type': mime[extname(file)] || 'application/octet-stream',
    'Content-Length': stat.size,
    'Cache-Control': extname(file) === '.html' ? 'no-cache' : 'public, max-age=3600',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
  });
  if (method === 'HEAD') res.end();
  else createReadStream(file).pipe(res);
}

createServer((req, res) => {
  let url;
  try { url = new URL(req.url, 'http://localhost'); }
  catch { res.writeHead(400).end(); return; }
  // Funnel versions may retain or strip --set-path. Accept both forms.
  const path = url.pathname === prefix ? '/' : url.pathname.startsWith(`${prefix}/`)
    ? url.pathname.slice(prefix.length) : url.pathname;
  if (path === '/api/v1' || path.startsWith('/api/v1/') || path === '/health' || path.startsWith('/health/')) {
    const headers = { ...req.headers, host: `127.0.0.1:${apiPort}`,
      'x-forwarded-proto': req.headers['x-forwarded-proto'] || (req.headers['cf-visitor'] ? 'https' : 'http'),
      'x-forwarded-host': req.headers['x-forwarded-host'] || req.headers.host,
    };
    delete headers.connection;
    const upstream = httpRequest({ hostname: '127.0.0.1', port: apiPort,
      method: req.method, path: path + url.search, headers }, upstreamRes => {
      const responseHeaders = { ...upstreamRes.headers };
      if (responseHeaders['set-cookie']) {
        responseHeaders['set-cookie'] = responseHeaders['set-cookie'].map(cookie =>
          cookie.replace(/Path=\/api\/v1(?=;|$)/i, `Path=${prefix}/api/v1`));
      }
      delete responseHeaders.connection;
      res.writeHead(upstreamRes.statusCode || 502, responseHeaders);
      upstreamRes.pipe(res);
    });
    upstream.on('error', () => { if (!res.headersSent) res.writeHead(502); res.end('API no disponible'); });
    req.pipe(upstream);
    return;
  }
  if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405).end(); return; }
  let decoded;
  try { decoded = decodeURIComponent(path); }
  catch { res.writeHead(400).end(); return; }
  const requested = resolve(root, `.${decoded}`);
  if (requested !== root && !requested.startsWith(root + sep)) {
    res.writeHead(403).end(); return;
  }
  const file = existsSync(requested) && statSync(requested).isFile()
    ? requested : extname(decoded) ? null : resolve(root, 'index.html');
  if (!file) { res.writeHead(404).end(); return; }
  sendFile(res, file, req.method);
}).listen(port, '127.0.0.1', () => {
  process.stdout.write(`AURORA public build listening on 127.0.0.1:${port}\n`);
});
