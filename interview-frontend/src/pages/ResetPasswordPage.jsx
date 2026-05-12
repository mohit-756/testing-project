import { useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Lock, Loader2, CheckCircle2, AlertCircle, Eye, EyeOff } from "lucide-react";
import { authApi } from "../services/api";

export default function ResetPasswordPage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [showPw, setShowPw] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (newPassword.length < 6) { setError("Password must be at least 6 characters"); return; }
    if (newPassword !== confirmPassword) { setError("Passwords do not match"); return; }
    setLoading(true);
    try {
      await authApi.resetPassword(token, newPassword);
      setSuccess(true);
      setTimeout(() => navigate("/login"), 3000);
    } catch (err) {
      setError(err.message || "Failed to reset password");
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 p-8 text-center">
          <CheckCircle2 size={48} className="mx-auto text-emerald-500 mb-4" />
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Password reset!</h2>
          <p className="text-slate-500 dark:text-slate-400 mb-6">Redirecting to login...</p>
          <Link to="/login" className="text-blue-600 dark:text-blue-400 font-bold hover:underline">Go to login now</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 p-8">
        <Link to="/login" className="flex items-center gap-2 text-slate-500 hover:text-blue-600 mb-6 font-medium">
          <ArrowLeft size={16} /> Back to login
        </Link>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-1">Reset password</h2>
        <p className="text-slate-500 dark:text-slate-400 mb-6 text-sm">Enter your new password below.</p>
        {error && <div className="bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 p-3 rounded-xl text-sm mb-4 flex items-center gap-2"><AlertCircle size={14} />{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="relative">
            <Lock className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5" />
<input type={showPw ? "text" : "password"} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="New password (min 6 chars)" required className="w-full pl-12 pr-12 py-3.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none dark:text-white hover:border-blue-300 dark:hover:border-blue-600 hover:bg-slate-100 dark:hover:bg-slate-750 transition-all" />

            <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="Confirm new password" required className="w-full pl-12 pr-4 py-3.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none dark:text-white hover:border-blue-300 dark:hover:border-blue-600 hover:bg-slate-100 dark:hover:bg-slate-750 transition-all" />
          </div>
          <button type="submit" disabled={loading} className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3.5 rounded-xl transition-all disabled:opacity-70 flex items-center justify-center gap-2">
            {loading ? <Loader2 size={18} className="animate-spin" /> : "Reset Password"}
          </button>
        </form>
      </div>
    </div>
  );
}
