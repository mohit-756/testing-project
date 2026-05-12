import { lazy, Suspense, Component } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import DashboardLayout from "./layout/DashboardLayout";
import { ToastProvider } from "./context/ToastContext";
import { useAuth } from "./context/useAuth";
import { ErrorBoundary } from "./components/ErrorBoundary";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import SettingsPage from "./pages/SettingsPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import HRDashboardPage from "./pages/HRDashboardPage";
import HRCandidatesPage from "./pages/HRCandidatesPage";
import HRJdManagementPage from "./pages/HRJdManagementPage";
import CandidateDashboardPage from "./pages/CandidateDashboardPage";
import Completed from "./pages/Completed";
import "./App.css";

const PreCheck = lazy(() => import("./pages/PreCheck"));
const Interview = lazy(() => import("./pages/Interview"));
const HRCandidateDetailPage = lazy(() => import("./pages/HRCandidateDetailPage"));
const HRInterviewListPage = lazy(() => import("./pages/HRInterviewListPage"));
const HRInterviewDetailPage = lazy(() => import("./pages/HRInterviewDetailPage"));
const HRScoreMatrixPage = lazy(() => import("./pages/HRScoreMatrixPage"));
const HRJdDetailPage = lazy(() => import("./pages/HRJdDetailPage"));
const HRAnalyticsPage = lazy(() => import("./pages/HRAnalyticsPage"));
const HRBackupPage = lazy(() => import("./pages/HRBackupPage"));
const HRPipelinePage = lazy(() => import("./pages/HRPipelinePage"));
const CandidateComparisonPage = lazy(() => import("./pages/CandidateComparisonPage"));
const CandidateSchedulePage = lazy(() => import("./pages/CandidateSchedulePage"));

function PageLoader() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950">
      <div className="text-center">
        <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
        <p className="text-sm text-slate-500 dark:text-slate-400">Loading page...</p>
      </div>
    </div>
  );
}

function HomeRedirect() {
  const { user, loading } = useAuth();
  const legacyInterviewMatch = window.location.pathname.match(/^\/interview\/([^/]+)\/?$/);
  if (legacyInterviewMatch) {
    return <Navigate to={`/interview/${legacyInterviewMatch[1]}${window.location.search || ""}`} replace />;
  }
  if (loading)
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950">
        <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === "hr" ? "/hr" : "/candidate"} replace />;
}

function PublicOnlyRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return null;
  if (user) {
    const next = new URLSearchParams(location.search).get("next");
    const safeNext = next && next.startsWith("/") && !next.startsWith("//") ? next : "";
    return <Navigate to={safeNext || (user.role === "hr" ? "/hr" : "/candidate")} replace />;
  }
  return children;
}

export default function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <Routes>
        <Route path="/login" element={<PublicOnlyRoute><LoginPage /></PublicOnlyRoute>} />
        <Route path="/signup" element={<PublicOnlyRoute><SignupPage /></PublicOnlyRoute>} />
        <Route path="/forgot-password" element={<PublicOnlyRoute><ForgotPasswordPage /></PublicOnlyRoute>} />
        <Route path="/reset-password/:token" element={<PublicOnlyRoute><ResetPasswordPage /></PublicOnlyRoute>} />

        <Route path="/interview/:resultId" element={<Suspense fallback={<PageLoader />}><PreCheck /></Suspense>} />
        <Route path="/interview/:resultId/live" element={<Suspense fallback={<PageLoader />}><Interview /></Suspense>} />
        <Route path="/interview/:resultId/completed" element={<Completed />} />

        <Route element={<ProtectedRoute role="hr" />}>
          <Route element={<DashboardLayout />}>
            <Route path="/hr" element={<HRDashboardPage />} />
            <Route path="/hr/jds" element={<HRJdManagementPage />} />
            <Route path="/hr/jds/:jdId" element={<Suspense fallback={<PageLoader />}><HRJdDetailPage /></Suspense>} />
            <Route path="/hr/candidates" element={<HRCandidatesPage />} />
            <Route path="/hr/pipeline" element={<Suspense fallback={<PageLoader />}><HRPipelinePage /></Suspense>} />
            <Route path="/hr/compare" element={<Suspense fallback={<PageLoader />}><CandidateComparisonPage /></Suspense>} />
            <Route path="/hr/candidates/:candidateUid" element={<Suspense fallback={<PageLoader />}><HRCandidateDetailPage /></Suspense>} />
            <Route path="/hr/interviews" element={<Suspense fallback={<PageLoader />}><HRInterviewListPage /></Suspense>} />
            <Route path="/hr/interviews/:id" element={<Suspense fallback={<PageLoader />}><HRInterviewDetailPage /></Suspense>} />
            <Route path="/hr/matrix" element={<Suspense fallback={<PageLoader />}><HRScoreMatrixPage /></Suspense>} />
            <Route path="/hr/analytics" element={<Suspense fallback={<PageLoader />}><HRAnalyticsPage /></Suspense>} />
<Route path="/hr/backup" element={<Suspense fallback={<PageLoader />}><HRBackupPage /></Suspense>} />
          </Route>
        </Route>

        <Route element={<ProtectedRoute role="candidate" />}>
          <Route element={<DashboardLayout />}>
            <Route path="/candidate" element={<CandidateDashboardPage />} />
            <Route path="/candidate/schedule" element={<Suspense fallback={<PageLoader />}><CandidateSchedulePage /></Suspense>} />
            <Route path="/interview/result" element={<Navigate to="/candidate" replace />} />
          </Route>
        </Route>

        <Route element={<ProtectedRoute />}>
          <Route element={<DashboardLayout />}>
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Route>

        <Route path="/" element={<HomeRedirect />} />
        <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </ToastProvider>
    </ErrorBoundary>
  );
}
