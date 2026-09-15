import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { AlertCircle, CheckCircle2, Info, TriangleAlert, X } from "lucide-react";

const ToastContext = createContext({
  showToast: () => {},
});

const TYPE_STYLES = {
  success: {
    icon: CheckCircle2,
    card: "border-emerald-200 bg-emerald-50 text-emerald-800",
  },
  error: {
    icon: AlertCircle,
    card: "border-red-200 bg-red-50 text-red-800",
  },
  warning: {
    icon: TriangleAlert,
    card: "border-amber-200 bg-amber-50 text-amber-800",
  },
  info: {
    icon: Info,
    card: "border-teal-200 bg-teal-50 text-teal-800",
  },
};

export default function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const showToast = useCallback(
    ({ message, type = "info", title = "" }) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
      setToasts((prev) => [...prev, { id, message, type, title }]);
      window.setTimeout(() => dismissToast(id), 3000);
    },
    [dismissToast],
  );

  const value = useMemo(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {typeof document !== "undefined"
        ? createPortal(
            <div className="pointer-events-none fixed right-4 top-4 z-[120] flex w-[min(92vw,360px)] flex-col gap-3">
              {toasts.map((toast) => {
                const style = TYPE_STYLES[toast.type] || TYPE_STYLES.info;
                const Icon = style.icon;
                return (
                  <div
                    key={toast.id}
                    className={`pointer-events-auto flex items-start gap-3 rounded-xl border px-4 py-3 shadow-md ${style.card}`}
                  >
                    <Icon className="mt-0.5 h-4 w-4 shrink-0" />
                    <div className="flex-1">
                      {toast.title ? <p className="text-sm font-semibold">{toast.title}</p> : null}
                      <p className="text-sm">{toast.message}</p>
                    </div>
                    <button
                      type="button"
                      className="rounded-md p-0.5 hover:bg-black/5"
                      onClick={() => dismissToast(toast.id)}
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                );
              })}
            </div>,
            document.body,
          )
        : null}
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
