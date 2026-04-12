import React, { createContext, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api.js";

const Ctx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  async function refresh() {
    if (!getToken()) {
      setUser(null);
      setReady(true);
      return;
    }
    try {
      const me = await api("/api/v1/auth/me");
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setReady(true);
    }
  }

  useEffect(() => {
    refresh();
    const onLogout = () => setUser(null);
    window.addEventListener("resumeiq:logout", onLogout);
    return () => window.removeEventListener("resumeiq:logout", onLogout);
  }, []);

  async function login(email, password, name, register) {
    const path = register ? "/api/v1/auth/register" : "/api/v1/auth/login";
    const body = register ? { email, password, name } : { email, password, name: "" };
    const res = await api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (register) return res;
    setToken(res.access_token);
    await refresh();
    return { ok: true };
  }

  async function verifyOtp(email, otp) {
    const res = await api("/api/v1/auth/verify-otp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, otp }),
    });
    setToken(res.access_token);
    await refresh();
  }

  async function resendOtp(email) {
    return api("/api/v1/auth/resend-otp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
  }

  async function forgotPassword(email) {
    return api("/api/v1/auth/forgot-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
  }

  async function resetPassword(email, otp, newPassword) {
    const res = await api("/api/v1/auth/reset-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, otp, new_password: newPassword }),
    });
    setToken(res.access_token);
    await refresh();
    return res;
  }

  function logout() {
    setToken(null);
    setUser(null);
  }

  return (
    <Ctx.Provider
      value={{ user, ready, login, verifyOtp, resendOtp, forgotPassword, resetPassword, logout, refresh }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useAuth() {
  return useContext(Ctx);
}
