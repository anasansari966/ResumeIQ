import { useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth.jsx";
import { VISUALS } from "../theme/visuals.js";

export default function LoginPage() {
  const { user, login, verifyOtp, resendOtp, forgotPassword, resetPassword } = useAuth();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [register, setRegister] = useState(false);
  const [otpMode, setOtpMode] = useState(false);
  const [forgotMode, setForgotMode] = useState(false);
  const [resetMode, setResetMode] = useState(false);
  const [otp, setOtp] = useState("");
  const [otpHint, setOtpHint] = useState("");
  const [resetCode, setResetCode] = useState("");
  const [resetHint, setResetHint] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const nextFromState = location.state?.from
    ? `${location.state.from.pathname || "/"}${location.state.from.search || ""}${location.state.from.hash || ""}`
    : "";
  const nextFromQuery = new URLSearchParams(location.search).get("next") || "";
  const redirectTo = (() => {
    const next = nextFromState || nextFromQuery || "/";
    if (!next.startsWith("/") || next.startsWith("/login")) return "/";
    return next;
  })();

  if (user) return <Navigate to={redirectTo} replace />;

  function showSignIn() {
    setRegister(false);
    setForgotMode(false);
    setResetMode(false);
    setOtpMode(false);
    setPassword("");
    setOtp("");
    setOtpHint("");
    setResetCode("");
    setResetHint("");
    setNewPassword("");
    setConfirmPassword("");
    setErr("");
  }

  function showRegister() {
    setRegister(true);
    setForgotMode(false);
    setResetMode(false);
    setOtpMode(false);
    setPassword("");
    setOtp("");
    setOtpHint("");
    setResetCode("");
    setResetHint("");
    setNewPassword("");
    setConfirmPassword("");
    setErr("");
  }

  function openForgotPassword() {
    setRegister(false);
    setForgotMode(true);
    setResetMode(false);
    setOtpMode(false);
    setPassword("");
    setOtp("");
    setOtpHint("");
    setResetCode("");
    setResetHint("");
    setNewPassword("");
    setConfirmPassword("");
    setErr("");
  }

  async function onSubmit(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      const res = await login(email, password, name, register);
      if (register) {
        setOtpMode(true);
        setOtpHint(res?.dev_otp ? `Dev OTP: ${res.dev_otp}` : "OTP sent to your email.");
      }
    } catch (ex) {
      setErr(ex.message || "Failed");
    } finally {
      setLoading(false);
    }
  }

  async function onVerifyOtp(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await verifyOtp(email, otp);
    } catch (ex) {
      setErr(ex.message || "OTP verification failed");
    } finally {
      setLoading(false);
    }
  }

  async function onResend() {
    setErr("");
    try {
      const res = await resendOtp(email);
      setOtpHint(res?.dev_otp ? `Dev OTP: ${res.dev_otp}` : "OTP re-sent to your email.");
    } catch (ex) {
      setErr(ex.message || "Failed to resend OTP");
    }
  }

  async function onForgotPasswordRequest(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      const res = await forgotPassword(email);
      setResetMode(true);
      setResetHint(
        res?.dev_otp
          ? `Dev reset code: ${res.dev_otp}`
          : res?.message || "If an account exists for that email, a password reset code has been sent.",
      );
    } catch (ex) {
      setErr(ex.message || "Failed to send reset code");
    } finally {
      setLoading(false);
    }
  }

  async function onResetPassword(e) {
    e.preventDefault();
    setErr("");
    if (newPassword.length < 6) {
      setErr("New password must be at least 6 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setErr("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await resetPassword(email, resetCode, newPassword);
    } catch (ex) {
      setErr(ex.message || "Password reset failed");
    } finally {
      setLoading(false);
    }
  }

  async function onResendReset() {
    setErr("");
    try {
      const res = await forgotPassword(email);
      setResetMode(true);
      setResetHint(
        res?.dev_otp
          ? `Dev reset code: ${res.dev_otp}`
          : res?.message || "If an account exists for that email, a password reset code has been sent.",
      );
    } catch (ex) {
      setErr(ex.message || "Failed to resend reset code");
    }
  }

  const fieldLabel = "text-slate-300 text-sm font-medium";
  const fieldInput =
    "mt-1.5 w-full rounded-xl border border-white/10 bg-slate-950/40 px-3.5 py-3 text-sm text-slate-100 placeholder:text-slate-500 shadow-inner shadow-black/20 transition focus:border-cyan-400/55 focus:outline-none focus:ring-2 focus:ring-cyan-500/25";
  const forgotPasswordCard = (
    <div className="glass-auth animate-fade-in-scale w-full max-w-md p-8 sm:p-10 motion-reduce:animate-none">
      <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-400">Reset access</p>
      <h1 className="font-display mt-3 text-3xl font-bold tracking-tight text-white sm:text-4xl">
        {resetMode ? "Set a new password" : "Forgot your password?"}
      </h1>
      <p className="mt-2 text-sm text-slate-400">
        {resetMode
          ? "Enter the reset code from your email and choose a new password."
          : "Enter your email and we will send a password reset code."}
      </p>
      {resetHint && (
        <p className="mt-4 rounded-xl border border-cyan-500/25 bg-cyan-950/25 px-3 py-2 text-xs text-cyan-200/95">
          {resetHint}
        </p>
      )}
      <form onSubmit={resetMode ? onResetPassword : onForgotPasswordRequest} className="mt-6 space-y-4">
        <label className="block">
          <span className={fieldLabel}>Email</span>
          <input
            type="email"
            required
            className={fieldInput}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        {resetMode && (
          <>
            <label className="block">
              <span className={fieldLabel}>Reset code</span>
              <input className={fieldInput} value={resetCode} onChange={(e) => setResetCode(e.target.value)} required />
            </label>
            <label className="block">
              <span className={fieldLabel}>New password</span>
              <input
                type="password"
                minLength={6}
                className={fieldInput}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
              />
            </label>
            <label className="block">
              <span className={fieldLabel}>Confirm new password</span>
              <input
                type="password"
                minLength={6}
                className={fieldInput}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
            </label>
          </>
        )}
        {err && <p className="text-sm text-red-400">{err}</p>}
        <button type="submit" disabled={loading} className="primary-btn mt-2 w-full py-3.5 text-base font-semibold">
          {loading ? "Please wait…" : resetMode ? "Reset password" : "Send reset code"}
        </button>
        {resetMode && (
          <button type="button" onClick={onResendReset} className="ghost-btn w-full py-3">
            Resend reset code
          </button>
        )}
        <button type="button" onClick={showSignIn} className="ghost-btn w-full py-3">
          Back to sign in
        </button>
      </form>
    </div>
  );

  return (
    <div className="auth-shell relative min-h-screen bg-[#060912]">
      {/* Full-bleed ambient layer */}
      <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
        <img
          src={VISUALS.loginHero}
          alt=""
          className="h-full w-full scale-110 object-cover opacity-[0.22] animate-kenburns motion-reduce:animate-none motion-reduce:scale-100 motion-reduce:opacity-25"
        />
        <div className="absolute inset-0 bg-gradient-to-br from-slate-950 via-[#0a1022]/95 to-indigo-950/98" />
        <div className="absolute inset-0 bg-[radial-gradient(100%_60%_at_50%_-15%,rgba(34,211,238,0.14),transparent_55%)]" />
        <div className="absolute -left-24 top-1/4 h-72 w-72 rounded-full bg-cyan-500/10 blur-[100px] animate-orbit motion-reduce:animate-none" />
        <div className="absolute -right-20 bottom-1/4 h-80 w-80 rounded-full bg-violet-500/10 blur-[110px] animate-orbit motion-reduce:animate-none [animation-delay:-5s]" />
      </div>

      <div className="relative z-10 flex min-h-screen flex-col lg:flex-row">
        {/* Left rail — desktop only */}
        <aside className="relative hidden w-[44%] max-w-2xl overflow-hidden lg:flex lg:flex-col lg:justify-end">
          <img
            src={VISUALS.loginHero}
            alt=""
            className="absolute inset-0 h-full w-full object-cover opacity-90 animate-bg-drift motion-reduce:animate-none"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/65 to-indigo-950/40" />
          <div className="relative z-10 p-12 xl:p-16 animate-stagger-1">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-300/90">ResumeIQ</p>
            <h2 className="font-display mt-4 max-w-md text-4xl font-bold leading-tight tracking-tight text-white xl:text-5xl">
              Your resume, amplified. Your next role, closer.
            </h2>
            <p className="mt-4 max-w-sm text-sm leading-relaxed text-slate-300/90">
              ATS-aware refinement, tailored documents, and job discovery — without the noise.
            </p>
          </div>
        </aside>

        {/* Form column */}
        <div className="flex flex-1 flex-col items-center justify-center p-6 sm:p-10">
          {otpMode ? (
            <div className="glass-auth animate-fade-in-scale w-full max-w-md p-8 sm:p-10 motion-reduce:animate-none">
              <p className="text-xs font-semibold uppercase tracking-widest text-cyan-400">Verify</p>
              <h1 className="font-display mt-2 text-2xl font-bold text-white sm:text-3xl">Check your inbox</h1>
              <p className="mt-2 text-sm text-slate-400">Enter the OTP sent to {email}.</p>
              {otpHint && (
                <p className="mt-3 rounded-xl border border-cyan-500/25 bg-cyan-950/25 px-3 py-2 text-xs text-cyan-200/95">
                  {otpHint}
                </p>
              )}
              <form onSubmit={onVerifyOtp} className="mt-6 space-y-4">
                <label className="block">
                  <span className={fieldLabel}>OTP code</span>
                  <input className={fieldInput} value={otp} onChange={(e) => setOtp(e.target.value)} required />
                </label>
                {err && <p className="animate-stagger-1 text-sm text-red-400">{err}</p>}
                <button type="submit" disabled={loading} className="primary-btn w-full py-3 font-semibold tracking-wide">
                  {loading ? "Verifying…" : "Verify & continue"}
                </button>
                <button type="button" onClick={onResend} className="ghost-btn w-full py-3">
                  Resend OTP
                </button>
              </form>
            </div>
          ) : forgotMode ? (
            forgotPasswordCard
          ) : (
            <div className="glass-auth animate-fade-in-scale w-full max-w-md p-8 sm:p-10 motion-reduce:animate-none">
              <div className="mb-8 text-center lg:text-left">
                <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-400">ResumeIQ</p>
                <h1 className="font-display mt-3 text-3xl font-bold tracking-tight text-white sm:text-4xl">
                  Career co-pilot
                </h1>
                <p className="mt-2 text-sm text-slate-400">Resume AI · ATS insight · Matched roles</p>
              </div>

              <div className="mb-8 flex gap-1.5 rounded-2xl border border-white/10 bg-slate-950/50 p-1.5 shadow-inner">
                <button
                  type="button"
                  className={`flex-1 rounded-xl py-3 text-sm font-semibold transition-all duration-300 ${
                    !register
                      ? "bg-gradient-to-r from-cyan-500 to-indigo-600 text-white shadow-lg shadow-cyan-900/40"
                      : "text-slate-400 hover:text-white"
                  }`}
                  onClick={showSignIn}
                >
                  Sign in
                </button>
                <button
                  type="button"
                  className={`flex-1 rounded-xl py-3 text-sm font-semibold transition-all duration-300 ${
                    register
                      ? "bg-gradient-to-r from-cyan-500 to-indigo-600 text-white shadow-lg shadow-cyan-900/40"
                      : "text-slate-400 hover:text-white"
                  }`}
                  onClick={showRegister}
                >
                  Create account
                </button>
              </div>

              <form onSubmit={onSubmit} className="space-y-4">
                {register && (
                  <label className="block animate-stagger-1">
                    <span className={fieldLabel}>Name</span>
                    <input className={fieldInput} value={name} onChange={(e) => setName(e.target.value)} />
                  </label>
                )}
                <label className="block">
                  <span className={fieldLabel}>Email</span>
                  <input
                    type="email"
                    required
                    className={fieldInput}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </label>
                <label className="block">
                  <span className={fieldLabel}>Password</span>
                  <input
                    type="password"
                    required
                    minLength={6}
                    className={fieldInput}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </label>
                {!register && (
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={openForgotPassword}
                      className="text-sm font-medium text-cyan-300 underline decoration-cyan-500/30 underline-offset-2 hover:text-cyan-200"
                    >
                      Forgot password?
                    </button>
                  </div>
                )}
                {err && <p className="text-sm text-red-400">{err}</p>}
                <button type="submit" disabled={loading} className="primary-btn mt-2 w-full py-3.5 text-base font-semibold">
                  {loading ? "Please wait…" : register ? "Create account" : "Sign in"}
                </button>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
