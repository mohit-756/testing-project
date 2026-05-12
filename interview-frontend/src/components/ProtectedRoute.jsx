import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/useAuth";

export default function ProtectedRoute({ role }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading)
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950">
        <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );

  if (!user) {
    return (
      <Navigate to="/login" state={{ from: `${location.pathname}${location.search}` }} replace />
    );
  }

  if (role && user.role !== role) {
    return (
      <Navigate to={user.role === "hr" ? "/hr" : "/candidate"} replace />
    );
  }

  return <Outlet />;
}
