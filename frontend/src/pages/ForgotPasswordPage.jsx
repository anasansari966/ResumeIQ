import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff, Lock, Mail } from "lucide-react";
import api from "../api";
import AuthShell from "../components/AuthShell";
import OTPInput from "../components/OTPInput";
import { useToast } from "../components/Toast";

function validEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

const STEP_LABELS = ["Email", "OTP", "New Password"];

export default function ForgotPasswordPage() {
  const [step, setStep] = useState(1);
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);

  const navigate = useNavigate();
  const { showToast } = useToast();

  const stepClass = useMemo(() => {
    if (step === 1) return "w-1/3";
    if (step === 2) return "w-2/3";
    return "w-full";
  }, [step]);

  const submitEmail = async (event) => {
    event.preventDefault();
    if (!email.trim() || !validEmail(email)) {
      showToast({ type: "warning", message: "Please enter a valid email." });
      return;
    }

    setLoading(true);
    try {
      await api.post("/auth/forgot-password", {
        email: email.trim().toLowerCase(),
      });
      setStep(2);
      showToast({ type: "success", message: "OTP sent to your email." });
    } catch (error) {
      showToast({ type: "error", message: error.response?.data?.detail || "Could not send reset OTP." });
    } finally {
      setLoading(false);
    }
  };

  const submitOtp = async (event) => {
    event.preventDefault();
    if (otp.length !== 6) {
      showToast({ type: "warning", message: "Enter the 6-digit OTP." });
      return;
    }
    setStep(3);
  };

  const submitNewPassword = async (event) => {
    event.preventDefault();
    if (newPassword.length < 8) {
      showToast({ type: "warning", message: "Password should be at least 8 characters." });
      return;
    }
    if (newPassword !== confirmPassword) {
      showToast({ type: "warning", message: "Passwords do not match." });
      return;
    }

    setLoading(true);
    try {
      await api.post("/auth/reset-password", {
        email: email.trim().toLowerCase(),
        otp,
        new_password: newPassword,
      });
      sessionStorage.setItem("auth_flash_success", "Password reset successfully. Please sign in.");
      navigate("/login", { replace: true });
    } catch (error) {
      showToast({ type: "error", message: error.response?.data?.detail || "Could not reset password." });
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      headline="Reset access and get back to your career workspace."
      subcopy="Verify your email, set a new password, and continue where you left off."
    >
      <div className="surface-card border-slate-200/90 shadow-[0_20px_50px_rgba(15,23,42,0.08)]">
        <h2 className="font-display text-2xl font-bold text-slate-900">Reset your password</h2>
        <p className="mt-1.5 text-sm text-slate-500">Follow the three quick steps below.</p>

        <div className="mt-6">
          <div className="mb-3 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-500">
            {STEP_LABELS.map((label, idx) => (
              <span key={label} className={idx + 1 <= step ? "text-teal-700" : ""}>
                {idx + 1}. {label}
              </span>
            ))}
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-200">
            <div className={`h-full bg-teal-600 transition-all ${stepClass}`} />
          </div>
        </div>

        {step === 1 ? (
          <form className="mt-6 space-y-4" onSubmit={submitEmail}>
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
                />
              </div>
            </div>
            <button type="submit" className="btn-primary w-full py-3" disabled={loading}>
              {loading ? "Sending OTP..." : "Send OTP"}
            </button>
          </form>
        ) : null}

        {step === 2 ? (
          <form className="mt-6 space-y-4" onSubmit={submitOtp}>
            <p className="text-sm text-slate-600">Enter OTP sent to {email}</p>
            <OTPInput value={otp} onChange={setOtp} onComplete={setOtp} />
            <div className="flex gap-3">
              <button type="button" className="btn-secondary flex-1" onClick={() => setStep(1)}>
                Back
              </button>
              <button type="submit" className="btn-primary flex-1">
                Verify OTP
              </button>
            </div>
          </form>
        ) : null}

        {step === 3 ? (
          <form className="mt-6 space-y-4" onSubmit={submitNewPassword}>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">New Password</label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  type={showPass ? "text" : "password"}
                  className="input-base pl-10 pr-10"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  placeholder="Enter new password"
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500"
                  onClick={() => setShowPass((prev) => !prev)}
                >
                  {showPass ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">Confirm Password</label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  type={showConfirm ? "text" : "password"}
                  className="input-base pl-10 pr-10"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  placeholder="Confirm password"
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500"
                  onClick={() => setShowConfirm((prev) => !prev)}
                >
                  {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <div className="flex gap-3">
              <button type="button" className="btn-secondary flex-1" onClick={() => setStep(2)}>
                Back
              </button>
              <button type="submit" className="btn-primary flex-1" disabled={loading}>
                {loading ? "Resetting..." : "Reset Password"}
              </button>
            </div>
          </form>
        ) : null}

        <p className="mt-6 text-center text-sm text-slate-600">
          Remembered your password?{" "}
          <Link to="/login" className="font-semibold text-teal-700 hover:text-teal-800">
            Sign in
          </Link>
        </p>
      </div>
    </AuthShell>
  );
}
