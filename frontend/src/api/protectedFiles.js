import { getStoredToken } from './client.js';

// Always fetch private files with Authorization. Never place JWTs in URLs.
export async function fetchProtectedBlob(url) {
  const token = getStoredToken();
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const response = await fetch(url, {
    headers,
    credentials: 'include',
    cache: 'no-store',
  });
  if (!response.ok) throw new Error(`No se pudo obtener el archivo (HTTP ${response.status}).`);
  return response.blob();
}

export async function downloadProtectedFile(url, filename) {
  const blob = await fetchProtectedBlob(url);
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
}
