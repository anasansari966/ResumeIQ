/** Human-readable template title: file base name without Word extensions. */
export function templateFileTitle(name) {
  let s = String(name ?? "").trim();
  let prev;
  const ext = /\.(docx|dotx|doc)$/i;
  do {
    prev = s;
    s = s.replace(ext, "").trim();
  } while (s !== prev);
  return s || String(name ?? "").trim();
}
