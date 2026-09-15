import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Eye, EyeOff, Lock, Mail } from "lucide-react";
import api from "../api";
import useAuth from "../hooks/useAuth";
import AuthShell from "../components/AuthShell";
import { useToast } from "../components/Toast";

function validEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

export default function LoginPage() {
  const [email, setEmail] = useState(localStorage.getItem("remember_email") || "");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(Boolean(localStorage.getItem("remember_email")));
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});

  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const { showToast } = useToast();

  const nextPath = useMemo(() => {
    const qp = new URLSearchParams(location.search).get("next");
    return qp || "/";
  }, [location.search]);

  useEffect(() => {
    const flash = sessionStorage.getItem("auth_flash_success");
    if (flash) {
      showToast({ type: "success", message: flash });
      sessionStorage.removeItem("auth_flash_success");
    }
  }, [showToast]);

  const validate = () => {
    const nextErrors = {};
    if (!email.trim()) nextErrors.email = "Email is required.";
    else if (!validEmail(email)) nextErrors.email = "Enter a valid email address.";
    if (!password.trim()) nextErrors.password = "Password is required.";
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!validate()) return;

    setLoading(true);
    try {
      const response = await api.post("/auth/login", {
        email: email.trim().toLowerCase(),
        password,
      });
      await login({ accessToken: response.data?.access_token || "", refreshToken: response.data?.refresh_token || "" });
      if (remember) localStorage.setItem("remember_email", email.trim());
      else localStorage.removeItem("remember_email");
      navigate(nextPath, { replace: true });
    } catch (error) {
      const message = error.response?.data?.detail || "Login failed. Please try again.";
      showToast({ type: "error", message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell>
      <div className="surface-card border-slate-200/90 shadow-[0_20px_50px_rgba(15,23,42,0.08)]">
        <div className="mb-7">
          <h2 className="font-display text-2xl font-bold text-slate-900">Welcome back</h2>
          <p className="mt-1.5 text-sm text-slate-500">Sign in to open your ResumeIQ workspace.</p>
        </div>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Email</label>
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="input-base pl-10"
                placeholder="you@example.com"
                autoComplete="email"
              />
            </div>
            {errors.email ? <p className="mt-1 text-xs text-red-500">{errors.email}</p> : null}
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Password</label>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="input-base pl-10 pr-10"
                placeholder="Enter your password"
                autoComplete="current-password"
              />
              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700"
                onClick={() => setShowPassword((prev) => !prev)}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {errors.password ? <p className="mt-1 text-xs text-red-500">{errors.password}</p> : null}
          </div>

          <div className="flex items-center justify-between gap-3 pt-1">
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={remember}
                onChange={(event) => setRemember(event.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-teal-700 focus:ring-teal-500"
              />
              Remember me
            </label>
            <Link to="/forgot-password" className="text-sm font-semibold text-teal-700 hover:text-teal-800">
              Forgot password?
            </Link>
          </div>

          <button type="submit" className="btn-primary w-full py-3" disabled={loading}>
            {loading ? (
              <span className="flex items-center gap-2">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-teal-100 border-t-white" />
                Signing in...
              </span>
            ) : (
              "Sign in"
            )}
          </button>
        </form>

        <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-600">
          <p className="font-semibold text-slate-800">Demo access</p>
          <p className="mt-1">admin@resumeiq.dev / Admin@12345</p>
          <p>user@resumeiq.dev / User@12345</p>
        </div>

        <p className="mt-6 text-center text-sm text-slate-600">
          Don&apos;t have an account?{" "}
          <Link to="/register" className="font-semibold text-teal-700 hover:text-teal-800">
            Create one
          </Link>
        </p>
      </div>
    </AuthShell>
  );
}
