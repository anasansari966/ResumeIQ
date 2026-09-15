import { Link } from "react-router-dom";
import { Home } from "lucide-react";

export default function NotFoundPage() {
  return (
    <div className="app-canvas flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm sm:p-10">
        <div className="mx-auto mb-6 flex h-48 w-full max-w-md items-center justify-center">
          <svg viewBox="0 0 640 360" className="h-full w-full" role="img" aria-label="404 illustration">
            <defs>
              <linearGradient id="notFoundGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#0f766e" />
                <stop offset="100%" stopColor="#0d5f59" />
              </linearGradient>
            </defs>
            <rect x="40" y="40" width="560" height="280" rx="28" fill="#f0fdfa" />
            <circle cx="160" cy="180" r="70" fill="url(#notFoundGrad)" opacity="0.18" />
            <circle cx="480" cy="180" r="70" fill="url(#notFoundGrad)" opacity="0.18" />
            <text x="320" y="210" textAnchor="middle" fill="#0f172a" fontSize="120" fontWeight="800">
              404
            </text>
          </svg>
        </div>

        <h1 className="font-display text-3xl font-bold text-slate-900">Page not found</h1>
        <p className="mx-auto mt-3 max-w-lg text-sm text-slate-500 sm:text-base">
          The page you are looking for does not exist or may have been moved.
        </p>

        <div className="mt-8">
          <Link to="/dashboard" className="btn-primary inline-flex items-center gap-2">
            <Home className="h-4 w-4" />
            Go to Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
