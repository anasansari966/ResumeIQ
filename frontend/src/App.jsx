import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import useAuth from "./hooks/useAuth";
import { isResumeOnboardingDone } from "./onboarding";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import Dashboard from "./pages/Dashboard";
import ResumeBuilderPage from "./pages/ResumeBuilderPage";
import ResumeEditorPage from "./pages/ResumeEditorPage";
import ResumeOnboardingPage from "./pages/ResumeOnboardingPage";
import JobsPage from "./pages/JobsPage";
import ApplicationsPage from "./pages/ApplicationsPage";
import SubscriptionPage from "./pages/SubscriptionPage";
import ProfilePage from "./pages/ProfilePage";
import NotFoundPage from "./pages/NotFoundPage";

function LoadingScreen() {
  return (
    <div className="app-canvas flex min-h-screen items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <p className="font-display text-xl font-bold text-slate-900">
          Resume<span className="text-teal-700">IQ</span>
        </p>
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-teal-100 border-t-teal-700" />
      </div>
    </div>
  );
}

function RootRedirect() {
  const token = localStorage.getItem("access_token");
  const { user, isLoading } = useAuth();

  if (!token) return <Navigate to="/login" replace />;
  if (isLoading) return <LoadingScreen />;
  return <Navigate to={isResumeOnboardingDone(user?.id) ? "/dashboard" : "/resume/onboarding"} replace />;
}

function ProtectedRoute() {
  const { isLoading } = useAuth();
  const token = localStorage.getItem("access_token");

  if (isLoading) return <LoadingScreen />;
  if (!token) return <Navigate to="/login" replace />;
  return <Outlet />;
}

function OnboardingGate() {
  const { user, isLoading } = useAuth();

  if (isLoading) return <LoadingScreen />;
  if (!isResumeOnboardingDone(user?.id)) {
    return <Navigate to="/resume/onboarding" replace />;
  }
  return <Outlet />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/resume/onboarding" element={<ResumeOnboardingPage />} />

          <Route element={<OnboardingGate />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/resume/new" element={<ResumeBuilderPage />} />
            <Route path="/resume/:id/edit" element={<ResumeEditorPage />} />
            <Route path="/jobs" element={<JobsPage />} />
            <Route path="/applications" element={<ApplicationsPage />} />
            <Route path="/subscription" element={<SubscriptionPage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
