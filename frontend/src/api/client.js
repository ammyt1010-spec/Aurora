const isLocalBrowser = ['localhost', '127.0.0.1'].includes(window.location.hostname);
const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL;

function pointsToLocalhost(value) {
  if (!value) return false;

  try {
    return ['localhost', '127.0.0.1'].includes(new URL(value, window.location.origin).hostname);
  } catch {
    return false;
  }
}

// Un valor localhost en .env solo sirve al navegar localmente. Si el frontend
// se publica (por ejemplo, mediante Cloudflare Tunnel), la API viaja por el
// proxy del mismo origen para no intentar acceder al equipo de cada visitante.
export const API_BASE_URL = (
  !isLocalBrowser && pointsToLocalhost(configuredApiBaseUrl)
    ? '/api/v1'
    : configuredApiBaseUrl || '/api/v1'
).replace(/\/$/, '');
const TOKEN_STORAGE_KEY = 'colmena_token';

// Raíz del backend (sin el prefijo /api/v1) — usada por endpoints que viven
// fuera del versionado, como GET /health.
export const API_ROOT_URL = API_BASE_URL.replace(/\/api\/v1\/?$/, '');

export function getStoredToken() {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token) {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearStoredToken() {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.message || `Error de red (${status})`);
    this.status = status;
    this.errorCode = body?.error_code || null;
    this.body = body;
  }
}

/**
 * Cliente HTTP centralizado (harness frontend §48): adjunta Bearer token,
 * base URL, parseo JSON y errores tipados. Toda llamada a la API de Colmena
 * debe pasar por aquí — nunca `fetch` directo desde una página/componente.
 */
export async function apiRequest(path, { method = 'GET', body, headers, skipAuth = false } = {}) {
  const finalHeaders = {
    'Content-Type': 'application/json',
    ...headers,
  };

  if (!skipAuth) {
    const token = getStoredToken();
    if (token) {
      finalHeaders.Authorization = `Bearer ${token}`;
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: finalHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (response.status === 204) {
    return null;
  }

  let payload = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, payload);
  }

  return payload;
}
