import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/useAuth";
import {
  Video,
  Mail,
  Lock,
  User,
  Briefcase,
  ArrowRight,
  CheckCircle2,
  Eye,
  EyeOff,
} from "lucide-react";
import { cn } from "../utils/utils";

export default function SignupPage() {
  const navigate = useNavigate();
  const { signup } = useAuth();
  const [role, setRole] = useState("candidate");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await signup({ role, name, email, password });
      setSuccess(true);
      setTimeout(() => navigate("/login"), 2000);
    } catch (submitError) {
      setError(submitError?.message || "Signup failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center p-4 font-sans">
      <div className="max-w-md w-full auth-card-animate">
        {/* Branding */}
        <div className="flex justify-center items-center space-x-2.5 mb-10">
          <div className="bg-blue-600 p-2.5 rounded-xl shadow-lg shadow-blue-200 dark:shadow-blue-900/30">
            <Video className="text-white w-6 h-6" />
          </div>
          <span className="text-2xl font-bold font-display tracking-tight dark:text-white">
            Interview<span className="text-blue-600">Bot</span>
          </span>
        </div>

        <div className="bg-white dark:bg-slate-900 rounded-3xl p-8 sm:p-10 shadow-xl border border-slate-200 dark:border-slate-800">
          <div className="mb-8">
            <h2 className="text-[1.7rem] font-bold text-slate-900 dark:text-white">
              Create account
            </h2>
            <p className="text-slate-500 dark:text-slate-400 mt-1.5 text-[0.95rem]">
              Join the next generation of hiring.
            </p>
          </div>

          {success ? (
            <div className="text-center py-8">
              <div className="relative w-20 h-20 mx-auto mb-5">
                <div className="absolute inset-0 bg-emerald-400 rounded-full blur-xl opacity-20 animate-pulse"></div>
                <div className="relative w-20 h-20 bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 rounded-full flex items-center justify-center">
                  <CheckCircle2 size={36} />
                </div>
              </div>
              <h3 className="text-xl font-bold text-slate-900 dark:text-white">
                Account Created!
              </h3>
              <p className="text-slate-500 dark:text-slate-400 mt-2">
                Redirecting you to login...
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              {error && (
                <div className="bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 p-4 rounded-xl text-sm border border-red-100 dark:border-red-900/30 flex items-start gap-3">
                  <span className="text-red-400 mt-0.5">&#x26A0;</span>
                  <span>{error}</span>
                </div>
              )}

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300 ml-1">
                  I am a...
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setRole("candidate")}
                    className={cn(
                      "flex items-center justify-center space-x-2 py-3 border rounded-xl transition-all text-sm font-medium",
                      role === "candidate"
                        ? "bg-blue-50 border-blue-200 text-blue-600 dark:bg-blue-900/20 dark:border-blue-800 dark:text-blue-400 shadow-sm"
                        : "bg-transparent border-slate-200 dark:border-slate-700 text-slate-500 hover:border-slate-300 dark:hover:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                    )}
                  >
                    <User size={18} />
                    <span>Candidate</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setRole("hr")}
                    className={cn(
                      "flex items-center justify-center space-x-2 py-3 border rounded-xl transition-all text-sm font-medium",
                      role === "hr"
                        ? "bg-blue-50 border-blue-200 text-blue-600 dark:bg-blue-900/20 dark:border-blue-800 dark:text-blue-400 shadow-sm"
                        : "bg-transparent border-slate-200 dark:border-slate-700 text-slate-500 hover:border-slate-300 dark:hover:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                    )}
                  >
                    <Briefcase size={18} />
                    <span>Recruiter</span>
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300 ml-1">
                  Full Name
                </label>
                <div className="relative group">
                  <User className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5 group-focus-within:text-blue-500 transition-colors" />
                  <input
                    id="name"
                    name="name"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full pl-12 pr-4 py-3.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all dark:text-white placeholder:text-slate-400 hover:border-blue-300 dark:hover:border-blue-600 hover:bg-slate-100 dark:hover:bg-slate-750"
                    placeholder="John Doe"
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300 ml-1">
                  Email Address
                </label>
                <div className="relative group">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5 group-focus-within:text-blue-500 transition-colors" />
                  <input
                    id="email"
                    name="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full pl-12 pr-4 py-3.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all dark:text-white placeholder:text-slate-400 hover:border-blue-300 dark:hover:border-blue-600 hover:bg-slate-100 dark:hover:bg-slate-750"
                    placeholder="john@example.com"
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300 ml-1">
                  Password
                </label>
                <div className="relative group">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5 group-focus-within:text-blue-500 transition-colors" />
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full pl-12 pr-12 py-3.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all dark:text-white placeholder:text-slate-400 hover:border-blue-300 dark:hover:border-blue-600 hover:bg-slate-100 dark:hover:bg-slate-750"
                    placeholder="••••••••"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white font-bold py-3.5 rounded-xl transition-all shadow-lg shadow-blue-200 dark:shadow-blue-900/30 flex items-center justify-center space-x-2 group disabled:opacity-70 disabled:cursor-wait"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Creating account...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    Sign Up
                    <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
                  </span>
                )}
              </button>
            </form>
          )}

          <p className="mt-8 text-center text-slate-500 dark:text-slate-400 text-sm">
            Already have an account?{" "}
            <Link
              to="/login"
              className="text-blue-600 dark:text-blue-400 font-bold hover:underline"
            >
              Sign In
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
