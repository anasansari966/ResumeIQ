/** Accent swatches for live resume preview + PDF export. */
export const ACCENT_COLORS = [
  { id: "teal", label: "Teal", hex: "#0f766e" },
  { id: "navy", label: "Navy", hex: "#1e3a8a" },
  { id: "coral", label: "Coral", hex: "#e07a5f" },
  { id: "slate", label: "Slate", hex: "#475569" },
  { id: "emerald", label: "Emerald", hex: "#047857" },
  { id: "sky", label: "Sky", hex: "#0284c7" },
  { id: "wine", label: "Wine", hex: "#9f1239" },
  { id: "amber", label: "Amber", hex: "#b45309" },
];

export function normalizeAccentHex(value, fallback = "#0f766e") {
  const raw = String(value || "").trim();
  if (/^#[0-9a-fA-F]{6}$/.test(raw)) return raw.toLowerCase();
  if (/^[0-9a-fA-F]{6}$/.test(raw)) return `#${raw.toLowerCase()}`;
  const named = ACCENT_COLORS.find((c) => c.id === raw.toLowerCase() || c.hex.toLowerCase() === raw.toLowerCase());
  return named?.hex || fallback;
}

export function hexToRgb(hex) {
  const h = normalizeAccentHex(hex).slice(1);
  return {
    r: parseInt(h.slice(0, 2), 16),
    g: parseInt(h.slice(2, 4), 16),
    b: parseInt(h.slice(4, 6), 16),
  };
}

export function softAccent(hex, alpha = 0.14) {
  const { r, g, b } = hexToRgb(hex);
  return `rgba(${r},${g},${b},${alpha})`;
}
