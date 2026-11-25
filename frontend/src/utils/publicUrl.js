export function publicUrl(path) {
  const base = import.meta.env.BASE_URL.replace(/\/$/, '');
  return `${window.location.origin}${base}${path.startsWith('/') ? path : `/${path}`}`;
}
