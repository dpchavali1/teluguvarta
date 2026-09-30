// Next passes dynamic path params still percent-encoded: a base64 cursor's `=`
// arrives as %3D, and a Telugu story slug arrives as %E0%B0... . The API
// helpers encode again, so an undecoded param reaches the API double-encoded
// and 404s (or, for a cursor, silently serves page one). Returns null for a
// malformed escape so the page can 404.
export function pathParam(raw: string): string | null {
  try {
    return decodeURIComponent(raw);
  } catch {
    return null;
  }
}
