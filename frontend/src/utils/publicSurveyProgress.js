// Tab-scoped only: never send a battery participant identifier to the server.
// Closing the tab discards credentials and answers. Storage may be unavailable.
const MAX_AGE_MS = 12 * 60 * 60 * 1000;
export function readProgress(key, { expires = true } = {}) {
  try {
    const saved = JSON.parse(sessionStorage.getItem(key));
    if (!saved) return {};
    if (
      !Number.isFinite(saved.savedAt) ||
      (expires && !saved.completed && Date.now() - saved.savedAt > MAX_AGE_MS)
    ) {
      // Purge credentials/answers, but require an explicit restart rather than
      // silently issuing a second session after a long interruption.
      const expired = { expired: true, savedAt: Date.now() };
      sessionStorage.setItem(key, JSON.stringify(expired));
      return expired;
    }
    return saved;
  } catch {
    return {};
  }
}
export function writeProgress(key, value) {
  try {
    sessionStorage.setItem(
      key,
      JSON.stringify({ ...value, savedAt: Date.now() }),
    );
  } catch {
    /* private browsing */
  }
}
