/**
 * CORS Proxy — Cloudflare Worker
 *
 * Usage:  GET https://<worker>/https://target.com/path
 *         POST https://<worker>/https://target.com/path  (body forwarded)
 *
 * The target URL is everything after the first slash following the worker host.
 * Query strings on the target URL are preserved.
 */

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD',
  'Access-Control-Allow-Headers': '*',
  'Access-Control-Max-Age': '86400',
};

// Headers we should NOT forward to the target (hop-by-hop or CF-specific)
const HOP_BY_HOP = new Set([
  'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
  'te', 'trailers', 'transfer-encoding', 'upgrade',
  'cf-connecting-ip', 'cf-ipcountry', 'cf-ray', 'cf-visitor',
  'x-forwarded-for', 'x-forwarded-proto', 'x-real-ip',
]);

// Response headers we should NOT forward back to the browser
const STRIP_RESPONSE = new Set([
  'content-security-policy', 'content-security-policy-report-only',
  'x-frame-options',
  'strict-transport-security',
  'cf-ray', 'cf-cache-status', 'cf-request-id',
  'set-cookie',  // cookies from target site would be confusing
]);

export default {
  async fetch(request, env) {
    // Preflight — must pass before token check so browser can learn the allowed headers
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    // Token guard — reject if no secret configured or token doesn't match
    const token = env.PROXY_TOKEN;
    if (token && request.headers.get('x-proxy-token') !== token) {
      return new Response('Forbidden', { status: 403, headers: CORS_HEADERS });
    }

    const incoming = new URL(request.url);

    // Target URL is the full path (minus leading slash) + query string
    const rawTarget = incoming.pathname.slice(1) + incoming.search;

    if (!rawTarget || rawTarget === '/') {
      return new Response(
        'CORS Proxy\n\nUsage: GET /https://example.com/path\n',
        { status: 200, headers: { ...CORS_HEADERS, 'content-type': 'text/plain' } }
      );
    }

    // Validate target URL
    let targetUrl;
    try {
      targetUrl = new URL(rawTarget);
    } catch {
      return new Response('Invalid target URL', { status: 400, headers: CORS_HEADERS });
    }

    if (!['http:', 'https:'].includes(targetUrl.protocol)) {
      return new Response('Only http/https targets allowed', { status: 400, headers: CORS_HEADERS });
    }

    // Build forwarded headers (strip hop-by-hop, keep the rest)
    const forwardHeaders = new Headers();
    for (const [key, value] of request.headers.entries()) {
      if (!HOP_BY_HOP.has(key.toLowerCase())) {
        forwardHeaders.set(key, value);
      }
    }

    // Spoof a realistic browser User-Agent if none was sent
    if (!forwardHeaders.has('user-agent')) {
      forwardHeaders.set(
        'user-agent',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
      );
    }

    // Remove headers that would identify us as a proxy or leak the token
    forwardHeaders.delete('origin');
    forwardHeaders.delete('referer');
    forwardHeaders.delete('x-proxy-token');

    // Forward the body for POST/PUT/PATCH
    const hasBody = ['POST', 'PUT', 'PATCH'].includes(request.method);
    const body = hasBody ? request.body : null;

    let response;
    try {
      response = await fetch(targetUrl.toString(), {
        method: request.method,
        headers: forwardHeaders,
        body,
        redirect: 'follow',
      });
    } catch (err) {
      return new Response(`Proxy fetch failed: ${err.message}`, {
        status: 502,
        headers: CORS_HEADERS,
      });
    }

    // Build response headers: strip problematic ones, add CORS
    const respHeaders = new Headers();
    for (const [key, value] of response.headers.entries()) {
      if (!STRIP_RESPONSE.has(key.toLowerCase())) {
        respHeaders.set(key, value);
      }
    }
    for (const [key, value] of Object.entries(CORS_HEADERS)) {
      respHeaders.set(key, value);
    }

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: respHeaders,
    });
  },
};
