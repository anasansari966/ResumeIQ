import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff, Lock, Mail, User } from "lucide-react";
import api from "../api";
import AuthShell from "../components/AuthShell";
import OTPInput from "../components/OTPInput";
import { useToast } from "../components/Toast";

function validEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function passwordStrength(password) {
  let score = 0;
  if (password.length >= 8) score += 1;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score += 1;
  if (/\d/.test(password) && /[^A-Za-z0-9]/.test(password)) score += 1;

  if (score <= 1) return { label: "Weak", color: "bg-red-500", text: "text-red-600" };
  if (score === 2) return { label: "Medium", color: "bg-amber-500", text: "text-amber-600" };
  return { label: "Strong", color: "bg-emerald-500", text: "text-emerald-600" };
}

export default function RegisterPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});

  const [otpModalOpen, setOtpModalOpen] = useState(false);
  const [otp, setOtp] = useState("");
  const [otpLoading, setOtpLoading] = useState(false);
  const [resendIn, setResendIn] = useState(60);

  const navigate = useNavigate();
  const { showToast } = useToast();

  const strength = useMemo(() => passwordStrength(password), [password]);

  useEffect(() => {
    if (!otpModalOpen || resendIn <= 0) return undefined;
    const timer = window.setInterval(() => setResendIn((prev) => prev - 1), 1000);
    return () => window.clearInterval(timer);
  }, [otpModalOpen, resendIn]);

  const validate = () => {
    const nextErrors = {};
    if (!fullName.trim()) nextErrors.fullName = "Full name is required.";
    if (!email.trim()) nextErrors.email = "Email is required.";
    else if (!validEmail(email)) nextErrors.email = "Enter a valid email address.";
    if (!password) nextErrors.password = "Password is required.";
    if (password.length < 8) nextErrors.password = "Password must be at least 8 characters.";
    if (!confirmPassword) nextErrors.confirmPassword = "Confirm your password.";
    if (confirmPassword !== password) nextErrors.confirmPassword = "Passwords do not match.";
    if (!agreeTerms) nextErrors.terms = "You must accept terms and conditions.";
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleRegister = async (event) => {
    event.preventDefault();
    if (!validate()) return;

    setLoading(true);
    try {
      await api.post("/auth/register", {
        name: fullName.trim(),
        email: email.trim().toLowerCase(),
        password,
      });
      setOtpModalOpen(true);
      setResendIn(60);
      showToast({ type: "success", message: "OTP sent to your email. Please verify to continue." });
    } catch (error) {
      showToast({ type: "error", message: error.response?.data?.detail || "Registration failed." });
    } finally {
      setLoading(false);
    }
  };

  const verifyOtp = async () => {
    if (otp.length !== 6) {
      showToast({ type: "warning", message: "Enter the 6-digit OTP." });
      return;
    }

    setOtpLoading(true);
    try {
      await api.post("/auth/verify-otp", {
        email: email.trim().toLowerCase(),
        otp,
      });
      sessionStorage.setItem("auth_flash_success", "Account verified. Please sign in.");
      navigate("/login", { replace: true });
    } catch (error) {
      showToast({ type: "error", message: error.response?.data?.detail || "Invalid OTP." });
    } finally {
      setOtpLoading(false);
    }
  };

  const resendOtp = async () => {
    if (resendIn > 0) return;
    try {
      await api.post("/auth/resend-otp", {
        email: email.trim().toLowerCase(),
      });
      setResendIn(60);
      showToast({ type: "success", message: "OTP resent." });
    } catch (error) {
      showToast({ type: "error", message: error.response?.data?.detail || "Could not resend OTP." });
    }
  };

  return (
    <AuthShell
      headline="Create your account and launch your next career move."
      subcopy="Build resumes, measure ATS score, and track job applications in one place."
    >
      <div className="surface-card border-slate-200/90 shadow-[0_20px_50px_rgba(15,23,42,0.08)]">
        <div className="mb-6">
          <h2 className="font-display text-2xl font-bold text-slate-900">Create account</h2>
          <p className="mt-1.5 text-sm text-slate-500">Start building your professional profile.</p>
        </div>

        <form className="space-y-4" onSubmit={handleRegister}>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Full Name</label>
            <div className="relative">
              <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                className="input-base pl-10"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                placeholder="Jane Doe"
              />
            </div>
            {errors.fullName ? <p className="mt-1 text-xs text-red-500">{errors.fullName}</p> : null}
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Email</label>
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="email"
                className="input-base pl-10"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
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
                className="input-base pl-10 pr-10"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Create password"
              />
              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700"
                onClick={() => setShowPassword((prev) => !prev)}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <div className="mt-2 flex items-center gap-2">
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
                <div
                  className={`h-full ${strength.color} ${
                    strength.label === "Weak" ? "w-1/3" : strength.label === "Medium" ? "w-2/3" : "w-full"
                  }`}
                />
              </div>
              <span className={`text-xs font-medium ${strength.text}`}>{strength.label}</span>
            </div>
            {errors.password ? <p className="mt-1 text-xs text-red-500">{errors.password}</p> : null}
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Confirm Password</label>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type={showConfirmPassword ? "text" : "password"}
                className="input-base pl-10 pr-10"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                placeholder="Re-enter password"
              />
              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700"
                onClick={() => setShowConfirmPassword((prev) => !prev)}
              >
                {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {errors.confirmPassword ? <p className="mt-1 text-xs text-red-500">{errors.confirmPassword}</p> : null}
          </div>

          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={agreeTerms}
              onChange={(event) => setAgreeTerms(event.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-teal-700 focus:ring-teal-500"
            />
            I agree to the terms and conditions
          </label>
          {errors.terms ? <p className="-mt-2 text-xs text-red-500">{errors.terms}</p> : null}

          <button type="submit" className="btn-primary w-full py-3" disabled={loading}>
            {loading ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-600">
          Already have an account?{" "}
          <Link to="/login" className="font-semibold text-teal-700 hover:text-teal-800">
            Sign in
          </Link>
        </p>
      </div>

      {otpModalOpen ? (
        <div className="fixed inset-0 z-[110] flex items-center justify-center p-4">
          <button type="button" className="absolute inset-0 bg-[#0b1324]/50 backdrop-blur-sm" onClick={() => setOtpModalOpen(false)} />
          <div className="relative z-10 w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-lg">
            <h3 className="font-display text-lg font-bold text-slate-900">Verify OTP</h3>
            <p className="mt-2 text-sm text-slate-600">Enter the 6-digit code sent to {email}.</p>

            <div className="mt-5">
              <OTPInput value={otp} onChange={setOtp} onComplete={setOtp} />
            </div>

            <div className="mt-4 flex items-center justify-between">
              <button
                type="button"
                onClick={resendOtp}
                disabled={resendIn > 0}
                className="text-sm font-medium text-teal-700 disabled:text-slate-400"
              >
                {resendIn > 0 ? `Resend OTP in ${resendIn}s` : "Resend OTP"}
              </button>
              <button type="button" className="btn-primary" onClick={verifyOtp} disabled={otpLoading}>
                {otpLoading ? "Verifying..." : "Verify"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </AuthShell>
  );
}
