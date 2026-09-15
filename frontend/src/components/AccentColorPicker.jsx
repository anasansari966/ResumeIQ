import { ACCENT_COLORS, normalizeAccentHex } from "../theme/accentColors";

export default function AccentColorPicker({ value, onChange, className = "" }) {
  const current = normalizeAccentHex(value);

  return (
    <div className={className}>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Accent color</p>
      <div className="flex flex-wrap items-center gap-2">
        {ACCENT_COLORS.map((color) => {
          const active = current === color.hex.toLowerCase();
          return (
            <button
              key={color.id}
              type="button"
              title={color.label}
              aria-label={`Accent ${color.label}`}
              onClick={() => onChange?.(color.hex)}
              className={`relative h-8 w-8 rounded-xl border-2 transition ${
                active ? "border-slate-900 scale-105" : "border-white shadow-sm hover:scale-105"
              }`}
              style={{ backgroundColor: color.hex }}
            >
              {active ? (
                <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white drop-shadow">
                  ✓
                </span>
              ) : null}
            </button>
          );
        })}
        <label className="ml-1 inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-600">
          Custom
          <input
            type="color"
            value={current}
            onChange={(event) => onChange?.(event.target.value)}
            className="h-6 w-8 cursor-pointer rounded border-0 bg-transparent p-0"
          />
        </label>
      </div>
    </div>
  );
}
