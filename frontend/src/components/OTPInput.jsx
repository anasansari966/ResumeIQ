import { useEffect, useMemo, useRef, useState } from "react";

export default function OTPInput({ onComplete, value = "", onChange }) {
  const [digits, setDigits] = useState(() => value.split("").slice(0, 6));
  const refs = useRef([]);

  useEffect(() => {
    const incoming = value.split("").slice(0, 6);
    if (incoming.join("") !== digits.join("")) {
      setDigits(incoming);
    }
  }, [value]);

  const currentValue = useMemo(() => digits.join(""), [digits]);

  useEffect(() => {
    onChange?.(currentValue);
    if (currentValue.length === 6 && !currentValue.includes("")) {
      onComplete?.(currentValue);
    }
  }, [currentValue, onChange, onComplete]);

  const updateDigit = (index, raw) => {
    const nextChar = raw.replace(/\D/g, "").slice(-1);
    const next = [...digits];
    next[index] = nextChar;
    setDigits(next);
    if (nextChar && index < 5) {
      refs.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (index, event) => {
    if (event.key === "Backspace" && !digits[index] && index > 0) {
      refs.current[index - 1]?.focus();
    }
  };

  const handlePaste = (event) => {
    event.preventDefault();
    const pasted = event.clipboardData
      .getData("text")
      .replace(/\D/g, "")
      .slice(0, 6)
      .split("");
    if (!pasted.length) return;

    const next = Array.from({ length: 6 }).map((_, idx) => pasted[idx] || "");
    setDigits(next);
    const focusIndex = Math.min(pasted.length, 6) - 1;
    refs.current[Math.max(focusIndex, 0)]?.focus();
  };

  return (
    <div className="flex items-center justify-center gap-2" onPaste={handlePaste}>
      {Array.from({ length: 6 }).map((_, index) => (
        <input
          key={index}
          ref={(el) => {
            refs.current[index] = el;
          }}
          value={digits[index] || ""}
          onChange={(event) => updateDigit(index, event.target.value)}
          onKeyDown={(event) => handleKeyDown(index, event)}
          inputMode="numeric"
          maxLength={1}
          className="h-11 w-11 rounded-lg border border-gray-200 text-center text-lg font-semibold text-gray-900 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-100"
        />
      ))}
    </div>
  );
}
