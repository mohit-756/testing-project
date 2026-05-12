import { useState, useEffect, useRef } from "react";
import {
  Lock, Moon, Sun, Shield, LogOut, Camera,
  CheckCircle2, Eye, EyeOff, Save, Monitor, Smartphone,
  ToggleLeft, AlertCircle, Loader2, User, HelpCircle,
  Minus, Plus, ExternalLink
} from "lucide-react";
import { useAuth } from "../context/useAuth";
import { authApi } from "../services/api";
import { cn } from "../utils/utils";

// LinkedIn icon component
function LinkedinIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
    </svg>
  );
}

// GitHub icon component
function GithubIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
    </svg>
  );
}

// ── Theme hook ─────────────────────────────────────────────────────────────
function useTheme() {
  const [theme, setTheme] = useState(() => {
    if (typeof window === "undefined") return "light";
    return document.documentElement.classList.contains("dark") ? "dark" : "light";
  });
  const toggle = (t) => {
    const root = document.documentElement;
    if (t === "dark") { root.classList.add("dark"); setTheme("dark"); localStorage.setItem("theme", "dark"); }
    else { root.classList.remove("dark"); setTheme("light"); localStorage.setItem("theme", "light"); }
  };
  return { theme, toggle };
}

// ── Toast ──────────────────────────────────────────────────────────────────
function Toast({ msg, type, onClose }) {
  useEffect(() => { const t = setTimeout(onClose, 3500); return () => clearTimeout(t); }, [onClose]);
  if (!msg) return null;
  return (
    <div className={cn(
      "fixed bottom-6 right-6 z-50 flex items-center gap-3 px-5 py-3.5 rounded-2xl shadow-2xl border text-sm font-bold animate-in slide-in-from-bottom-4 duration-300",
      type === "success" ? "bg-emerald-600 border-emerald-500 text-white" : "bg-red-600 border-red-500 text-white"
    )}>
      {type === "success" ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
      {msg}
    </div>
  );
}

// ── Toggle switch ─────────────────────────────────────────────────────────
function ToggleSwitch({ checked, onChange, label, sub }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-slate-100 dark:border-slate-800 last:border-0">
      <div>
        <p className="text-sm font-bold text-slate-800 dark:text-white">{label}</p>
        {sub && <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{sub}</p>}
      </div>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={cn(
          "relative w-11 h-6 rounded-full transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2",
          checked ? "bg-blue-600" : "bg-slate-200 dark:bg-slate-700"
        )}
      >
        <span className={cn(
          "absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-300",
          checked ? "translate-x-5" : "translate-x-0"
        )} />
      </button>
    </div>
  );
}

// ── Password field ────────────────────────────────────────────────────────
function PasswordField({ label, value, onChange, placeholder }) {
  const [show, setShow] = useState(false);
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-black text-slate-500 dark:text-slate-400 uppercase tracking-wider">{label}</label>
      <div className="relative">
        <input
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full pr-11 pl-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white transition-all"
        />
        <button type="button" onClick={() => setShow((s) => !s)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors">
          {show ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </div>
    </div>
  );
}

// ── Section wrapper ───────────────────────────────────────────────────────
function Section({ title, sub, children, icon: Icon }) {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
      <div className="px-8 py-5 border-b border-slate-100 dark:border-slate-800 flex items-center gap-3">
        {Icon && <div className="w-8 h-8 bg-blue-50 dark:bg-blue-900/30 rounded-xl flex items-center justify-center text-blue-600 dark:text-blue-400"><Icon size={16} /></div>}
        <div>
          <h3 className="text-base font-bold text-slate-900 dark:text-white">{title}</h3>
          {sub && <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{sub}</p>}
        </div>
      </div>
      <div className="px-8 py-6">{children}</div>
    </div>
  );
}

export default function SettingsPage() {
  const { user, logout, refreshSession } = useAuth();
  const { theme, toggle: toggleTheme } = useTheme();
  const fileInputRef = useRef(null);

  // Profile state
  const [name, setName] = useState(user?.name || "");
  const [email, setEmail] = useState(user?.email || "");
  const [linkedinUrl, setLinkedinUrl] = useState(user?.linkedin_url || "");
  const [githubUrl, setGithubUrl] = useState(user?.github_url || "");
  const [savingProfile, setSavingProfile] = useState(false);

  // Password state
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [savingPw, setSavingPw] = useState(false);

  // Notifications state
  const [notifs, setNotifs] = useState({
    emailOnSchedule: true,
    emailOnReview: true,
    emailOnShortlist: false,
    browserAlerts: true,
    weeklyDigest: false,
  });

  // Appearance state
  const [fontSize, setFontSize] = useState("normal");
  const [compactMode, setCompactMode] = useState(false);

  // Toast
  const [toast, setToast] = useState({ msg: "", type: "success" });

  const showToast = (msg, type = "success") => setToast({ msg, type });

  // Sync user data when auth loads
  useEffect(() => {
    if (user) {
      setName(user.name || "");
      setEmail(user.email || "");
      setLinkedinUrl(user.linkedin_url || "");
      setGithubUrl(user.github_url || "");
    }
  }, [user]);

  // Load saved preferences from localStorage then API
  useEffect(() => {
    try {
      const saved = localStorage.getItem("interviewbot_notifs");
      if (saved) setNotifs(JSON.parse(saved));
      const savedFs = localStorage.getItem("interviewbot_fontsize");
      if (savedFs) setFontSize(savedFs);
      const savedCompact = localStorage.getItem("interviewbot_compact");
      if (savedCompact) setCompactMode(savedCompact === "true");
    } catch {
      // Ignore malformed local preference data.
    }
    authApi.getPreferences().then((res) => {
      if (res?.preferences && Object.keys(res.preferences).length > 0) {
        const p = res.preferences;
        if (p.notifs) setNotifs(p.notifs);
        if (p.fontSize) { setFontSize(p.fontSize); handleFontSize(p.fontSize); }
        if (typeof p.compactMode === "boolean") setCompactMode(p.compactMode);
        if (p.theme) toggleTheme(p.theme);
      }
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Profile save — calls PUT /api/auth/profile (we add a simple endpoint)
  async function handleSaveProfile(e) {
    e.preventDefault();
    if (!name.trim()) { showToast("Name cannot be empty", "error"); return; }
    setSavingProfile(true);
    try {
      await authApi.updateProfile(name.trim(), {
        linkedin_url: linkedinUrl.trim() || null,
        github_url: githubUrl.trim() || null,
      });
      await refreshSession();
      showToast("Profile updated successfully!");
    } catch {
      showToast("Failed to update profile", "error");
    } finally {
      setSavingProfile(false);
    }
  }

  // Password change
  async function handleChangePassword(e) {
    e.preventDefault();
    if (!currentPw || !newPw || !confirmPw) { showToast("All password fields are required", "error"); return; }
    if (newPw.length < 6) { showToast("New password must be at least 6 characters", "error"); return; }
    if (newPw !== confirmPw) { showToast("New passwords do not match", "error"); return; }
    setSavingPw(true);
    try {
      await authApi.changePassword(currentPw, newPw);
      setCurrentPw(""); setNewPw(""); setConfirmPw("");
      showToast("Password changed successfully!");
    } catch (err) {
      showToast(err.message || "Failed to change password", "error");
    } finally {
      setSavingPw(false);
    }
  }

  // Notification prefs — stored locally (extend to backend if needed)
  function handleNotifChange(key, value) {
    const next = { ...notifs, [key]: value };
    setNotifs(next);
    localStorage.setItem("interviewbot_notifs", JSON.stringify(next));
    authApi.savePreferences({ notifs: next, fontSize, compactMode, theme }).catch(() => {});
    showToast("Notification preference saved");
  }

  // Appearance
  function handleFontSize(size) {
    setFontSize(size);
    localStorage.setItem("interviewbot_fontsize", size);
    const root = document.documentElement;
    root.style.fontSize = size === "small" ? "14px" : size === "large" ? "17px" : "16px";
    authApi.savePreferences({ notifs, fontSize: size, compactMode, theme }).catch(() => {});
    showToast("Font size updated");
  }
  function handleCompact(val) {
    setCompactMode(val);
    localStorage.setItem("interviewbot_compact", String(val));
    authApi.savePreferences({ notifs, fontSize, compactMode: val, theme }).catch(() => {});
    showToast("Layout preference saved");
  }

  const tabs = [
    { id: "profile", label: "Profile", icon: User },
    { id: "security", label: "Security", icon: Lock },
    { id: "appearance", label: "Appearance", icon: Monitor },
    { id: "faq", label: "Help & FAQ", icon: HelpCircle },
  ];
  const [activeTab, setActiveTab] = useState("profile");
  const [openIndex, setOpenIndex] = useState(null);

  const isHR = user?.role === "hr";

  const staticFAQs = isHR ? [
    { question: "How do I create a new job description?", answer: "Go to JD Management → Click 'Add JD' or 'Create Job'. Fill in the job title, description, required skills (with weights 1-10), and interview settings. Save to publish." },
    { question: "How do I edit or update an existing job?", answer: "Go to JD Management, find the job you want to edit, and click the edit icon. Modify the details and save changes. Note: Changes won't affect ongoing interviews." },
    { question: "How do I set skill requirements and weights?", answer: "When creating/editing a JD, add skills and set weights (1-10). Higher weight = more important for the role. The AI uses these weights to calculate resume match scores." },
    { question: "How do I view and filter candidate applications?", answer: "Go to Candidates page. Use filters to narrow down by job, status, score range, or date. You can also search by name or email." },
    { question: "How do I review resumes and AI scores?", answer: "Click on any candidate to view their profile. You'll see their resume, AI-generated match score, skill breakdown, and application status." },
    { question: "How do I accept or reject candidates?", answer: "Go to Pipeline or Candidates. Select a candidate and choose 'Accept' or 'Reject'. You can add notes explaining your decision." },
    { question: "How do I schedule interviews for candidates?", answer: "Go to Candidates, find the candidate, and click the calendar icon. Select a date/time and send the interview invitation. The candidate receives an email." },
    { question: "How do I review completed interviews?", answer: "Go to Interview Reviews. Click on a completed interview to see AI scores, answer transcriptions, proctoring logs, and candidate performance." },
    { question: "How do I view proctoring logs and activity?", answer: "In Interview Reviews, click on a completed session. The proctoring tab shows tab switches, video/mic status, time per question, and any suspicious events." },
    { question: "How do I make hire/no-hire decisions?", answer: "In Interview Reviews, select a candidate and click 'Hire' or 'No Hire'. Add your notes and finalize the decision. This updates the candidate's status in Pipeline." },
    { question: "How do I move candidates through stages?", answer: "In Pipeline, drag and drop candidates between stages (Applied → Screening → Interview → Offer → Hired). Or click the candidate and select a new stage." },
    { question: "How do I use the kanban board?", answer: "Pipeline shows candidates in columns by stage. Drag cards to move candidates. Click a card to view details or change status." },
    { question: "What analytics are available?", answer: "Reports page shows hiring metrics: application counts, interview completion rates, selection rates, time-to-hire, and source effectiveness." },
    { question: "How do I generate reports?", answer: "Go to Reports. Select the report type, date range, and filters. Click 'Generate' or 'Export' to download data as CSV." },
    { question: "What metrics can be tracked?", answer: "Track: total applications, interview rates, offer acceptance rate, candidate sources, average scores, and pipeline conversion funnel." },
  ] : [
    { question: "How do I upload my resume?", answer: "Go to your Dashboard, click the upload button, and select your resume file (PDF or DOCX). The AI will analyze it and give you a match score for each job." },
    { question: "How does resume scoring work?", answer: "We analyze your resume against the job description skills and requirements. Your score shows how well your skills match the position. Higher scores = better match." },
    { question: "When will I get interview results?", answer: "After completing your interview, HR reviews your answers and scores. The decision appears in your Dashboard under 'My Results'. This usually takes 1-3 business days." },
    { question: "Can I retake an interview?", answer: "Each job usually allows one interview attempt. Check your Dashboard - if an interview is marked 'Ready' or 'In Progress', you can start or resume it." },
    { question: "How do I practice for interviews?", answer: "Go to your Dashboard and look for practice session options. You can practice with sample questions to improve your confidence before the real interview." },
    { question: "What do my scores mean?", answer: "Resume Score: How well your skills match the job. Interview Score: Your response quality during the interview. Final Score: Combined HR review. Scores above 65% are typically strong." },
    { question: "How do I change my applied job?", answer: "On your Dashboard, use the job selector dropdown to switch between jobs you've applied to. Each job has its own resume and interview process." },
    { question: "My resume won't upload - what should I do?", answer: "Make sure it's a PDF or DOCX file under 5MB. If it still fails, try a different file format or contact support." },
  ];

  return (
    <div className="space-y-8 pb-12">
      {/* Toast */}
      <Toast msg={toast.msg} type={toast.type} onClose={() => setToast({ msg: "", type: "success" })} />

      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white font-display">Settings</h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1">Manage your account, security, appearance, and get help.</p>
      </div>

      <div className="flex flex-col lg:flex-row gap-8">
        {/* Sidebar */}
        <aside className="lg:w-56 flex-shrink-0">
          {/* Avatar card */}
          <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm p-6 mb-4 text-center">
            <div className="relative inline-block mb-4">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-2xl font-black mx-auto shadow-lg">
                {(user?.name?.[0] || "U").toUpperCase()}
              </div>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="absolute -bottom-1 -right-1 w-7 h-7 bg-blue-600 text-white rounded-xl flex items-center justify-center shadow-md hover:bg-blue-700 transition-colors"
              >
                <Camera size={13} />
              </button>
                <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  try {
                    await authApi.uploadAvatar(file);
                    showToast("Avatar updated!");
                    await refreshSession();
                  } catch {
                    showToast("Failed to upload avatar", "error");
                  }
                }} />
            </div>
            <p className="font-bold text-slate-900 dark:text-white text-sm truncate">{user?.name || "User"}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{user?.email}</p>
            <span className="mt-2 inline-block px-2.5 py-0.5 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 text-[10px] font-black uppercase tracking-wider rounded-full capitalize">{user?.role || "user"}</span>
          </div>

          {/* Nav */}
          <nav className="space-y-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-4 py-3 rounded-2xl text-sm font-bold transition-all",
                  activeTab === tab.id
                    ? "bg-blue-600 text-white shadow-lg shadow-blue-100 dark:shadow-none"
                    : "text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-800 dark:hover:text-white"
                )}
              >
                <tab.icon size={16} />
                {tab.label}
              </button>
            ))}
            <div className="pt-2 mt-2 border-t border-slate-100 dark:border-slate-800">
              <button
                type="button"
                onClick={logout}
                className="w-full flex items-center gap-3 px-4 py-3 rounded-2xl text-sm font-bold text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-all"
              >
                <LogOut size={16} />
                Sign Out
              </button>
            </div>
          </nav>
        </aside>

        {/* Content */}
        <div className="flex-1 space-y-6 min-w-0">

          {/* ── PROFILE TAB ─────────────────────────────────────────── */}
          {activeTab === "profile" && (
            <form onSubmit={handleSaveProfile} className="space-y-6">
              <Section title="Personal Information" sub="Update your display name and email" icon={User}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  <div className="space-y-1.5">
                    <label className="text-xs font-black text-slate-500 dark:text-slate-400 uppercase tracking-wider">Full Name</label>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Your name"
                      className="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white transition-all"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-black text-slate-500 dark:text-slate-400 uppercase tracking-wider">Email Address</label>
                    <input
                      type="email"
                      value={email}
                      disabled
                      className="w-full px-4 py-3 bg-slate-100 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-400 dark:text-slate-500 cursor-not-allowed"
                    />
                    <p className="text-[11px] text-slate-400">Email cannot be changed after signup</p>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-black text-slate-500 dark:text-slate-400 uppercase tracking-wider">Role</label>
                    <input
                      type="text"
                      value={user?.role === "hr" ? "HR / Recruiter" : "Candidate"}
                      disabled
                      className="w-full px-4 py-3 bg-slate-100 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-400 dark:text-slate-500 cursor-not-allowed capitalize"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-black text-slate-500 dark:text-slate-400 uppercase tracking-wider">Account ID</label>
                    <input
                      type="text"
                      value={`#${user?.id || "—"}`}
                      disabled
                      className="w-full px-4 py-3 bg-slate-100 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-400 dark:text-slate-500 cursor-not-allowed font-mono"
                    />
                  </div>
                </div>

                <div className="mt-6 border-t border-slate-100 dark:border-slate-800 pt-6">
                  <h4 className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-4">Social Profiles</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <div className="space-y-1.5">
                      <label className="text-xs font-black text-slate-500 dark:text-slate-400 uppercase tracking-wider">LinkedIn Profile</label>
                      <div className="relative">
                        <LinkedinIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-blue-600" />
                        <input
                          type="url"
                          value={linkedinUrl}
                          onChange={(e) => setLinkedinUrl(e.target.value)}
                          placeholder="https://linkedin.com/in/yourprofile"
                          className="w-full pl-11 pr-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white transition-all"
                        />
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-black text-slate-500 dark:text-slate-400 uppercase tracking-wider">GitHub Profile</label>
                      <div className="relative">
                        <GithubIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-700 dark:text-slate-300" />
                        <input
                          type="url"
                          value={githubUrl}
                          onChange={(e) => setGithubUrl(e.target.value)}
                          placeholder="https://github.com/yourusername"
                          className="w-full pl-11 pr-4 py-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 text-sm dark:text-white transition-all"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                <div className="pt-2 flex justify-end">
                  <button
                    type="submit"
                    disabled={savingProfile}
                    className="flex items-center gap-2 px-7 py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-2xl shadow-lg shadow-blue-200 dark:shadow-none transition-all disabled:opacity-60"
                  >
                    {savingProfile ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                    {savingProfile ? "Saving…" : "Save Profile"}
                  </button>
                </div>
              </Section>
            </form>
          )}

          {/* ── SECURITY TAB ────────────────────────────────────────── */}
          {activeTab === "security" && (
            <div className="space-y-6">
              <form onSubmit={handleChangePassword}>
                <Section title="Change Password" sub="Use a strong password of at least 6 characters" icon={Lock}>
                  <div className="space-y-4 max-w-md">
                    <PasswordField label="Current Password" value={currentPw} onChange={setCurrentPw} placeholder="Enter current password" />
                    <PasswordField label="New Password" value={newPw} onChange={setNewPw} placeholder="At least 6 characters" />
                    <PasswordField label="Confirm New Password" value={confirmPw} onChange={setConfirmPw} placeholder="Repeat new password" />

                    {/* Password strength indicator */}
                    {newPw.length > 0 && (
                      <div className="space-y-1">
                        <div className="flex gap-1">
                          {[1, 2, 3, 4].map((i) => {
                            const strength = newPw.length < 6 ? 1 : newPw.length < 10 ? 2 : /[A-Z]/.test(newPw) && /[0-9]/.test(newPw) ? 4 : 3;
                            return <div key={i} className={cn("h-1 flex-1 rounded-full transition-all", i <= strength ? strength >= 4 ? "bg-emerald-500" : strength >= 3 ? "bg-blue-500" : strength >= 2 ? "bg-amber-500" : "bg-red-400" : "bg-slate-200 dark:bg-slate-700")} />;
                          })}
                        </div>
                        <p className="text-[11px] text-slate-400">
                          {newPw.length < 6 ? "Too short" : newPw.length < 10 ? "Weak — add more characters" : /[A-Z]/.test(newPw) && /[0-9]/.test(newPw) ? "Strong password ✓" : "Good — add uppercase & numbers for strong"}
                        </p>
                      </div>
                    )}

                    <div className="pt-2">
                      <button
                        type="submit"
                        disabled={savingPw}
                        className="flex items-center gap-2 px-7 py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-2xl shadow-lg shadow-blue-200 dark:shadow-none transition-all disabled:opacity-60"
                      >
                        {savingPw ? <Loader2 size={16} className="animate-spin" /> : <Shield size={16} />}
                        {savingPw ? "Updating…" : "Update Password"}
                      </button>
                    </div>
                  </div>
                </Section>
              </form>

              <Section title="Session Info" sub="Your current login session details" icon={Shield}>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  {[
                    { label: "Logged in as", value: user?.email || "—" },
                    { label: "Role", value: user?.role === "hr" ? "HR / Recruiter" : "Candidate" },
                    { label: "Session", value: "Active" },
                  ].map(({ label, value }) => (
                    <div key={label} className="bg-slate-50 dark:bg-slate-800 rounded-2xl p-4">
                      <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{label}</p>
                      <p className="text-sm font-bold text-slate-900 dark:text-white mt-1 truncate">{value}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-4">
                  <button
                    type="button"
                    onClick={logout}
                    className="flex items-center gap-2 px-5 py-2.5 border border-red-200 dark:border-red-800/50 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 font-bold rounded-xl text-sm transition-all"
                  >
                    <LogOut size={15} />Sign out everywhere
                  </button>
                </div>
              </Section>
            </div>
          )}

{/* ── APPEARANCE TAB ──────────────────────────────────────── */}
          {activeTab === "appearance" && (
            <div className="space-y-6">
              <Section title="Theme" sub="Choose how InterviewBot looks" icon={Monitor}>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { id: "light", label: "Light", icon: Sun, preview: "bg-white border-2" },
                    { id: "dark", label: "Dark", icon: Moon, preview: "bg-slate-900 border-2" },
                    { id: "system", label: "System", icon: Monitor, preview: "bg-gradient-to-br from-white to-slate-900 border-2" },
                  ].map((opt) => (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => { if (opt.id !== "system") toggleTheme(opt.id); else toggleTheme(window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"); }}
                      className={cn(
                        "flex flex-col items-center gap-3 p-4 rounded-2xl border-2 transition-all",
                        theme === opt.id ? "border-blue-600 bg-blue-50 dark:bg-blue-900/20" : "border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600"
                      )}
                    >
                      <div className={cn("w-full h-16 rounded-xl overflow-hidden border", opt.preview, theme === opt.id ? "border-blue-400" : "border-slate-200 dark:border-slate-700")}>
                        <div className={cn("w-full h-4 flex gap-1 items-center px-2", opt.id === "dark" ? "bg-slate-800" : "bg-slate-100")}>
                          {[1,2,3].map((i) => <div key={i} className={cn("w-2 h-2 rounded-full", opt.id === "dark" ? "bg-slate-600" : "bg-slate-300")} />)}
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <opt.icon size={14} className={theme === opt.id ? "text-blue-600" : "text-slate-500"} />
                        <span className={cn("text-sm font-bold", theme === opt.id ? "text-blue-600" : "text-slate-600 dark:text-slate-300")}>{opt.label}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </Section>

              <Section title="Font Size" sub="Adjust text size across the interface" icon={Monitor}>
                <div className="flex gap-3">
                  {[
                    { id: "small", label: "Small", sample: "text-xs" },
                    { id: "normal", label: "Normal", sample: "text-sm" },
                    { id: "large", label: "Large", sample: "text-base" },
                  ].map((opt) => (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => handleFontSize(opt.id)}
                      className={cn(
                        "flex-1 py-4 rounded-2xl border-2 text-center transition-all",
                        fontSize === opt.id ? "border-blue-600 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400" : "border-slate-200 dark:border-slate-700 hover:border-slate-300 text-slate-600 dark:text-slate-300"
                      )}
                    >
                      <span className={cn("font-bold block", opt.sample)}>Aa</span>
                      <span className="text-xs font-bold mt-1 block">{opt.label}</span>
                    </button>
                  ))}
                </div>
              </Section>

              <Section title="Layout" sub="Customize information density" icon={Smartphone}>
                <ToggleSwitch checked={compactMode} onChange={handleCompact} label="Compact Mode" sub="Reduce padding and spacing for more information density" />
              </Section>
            </div>
          )}

          {/* ── HELP & FAQ TAB ──────────────────────────────────────── */}
          {activeTab === "faq" && (
            <div className="space-y-6">
              <Section title="Frequently Asked Questions" sub="Common questions and helpful guides" icon={HelpCircle}>
                <div className="space-y-3">
                  {staticFAQs.map((faq, index) => (
                    <FAQItem
                      key={index}
                      question={faq.question}
                      answer={faq.answer}
                      isOpen={openIndex === index}
                      onToggle={() => setOpenIndex(openIndex === index ? null : index)}
                    />
                  ))}
                </div>
              </Section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function FAQItem({ question, answer, onToggle, isOpen }) {
  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
      >
        <span className="font-medium text-slate-900 dark:text-white">{question}</span>
        {isOpen ? <Minus size={18} className="text-slate-500" /> : <Plus size={18} className="text-slate-500" />}
      </button>
      {isOpen && answer && (
        <div className="px-4 pb-4 text-sm text-slate-600 dark:text-slate-400 leading-relaxed border-t border-slate-100 dark:border-slate-800 pt-3 mt-2">
          {answer}
        </div>
      )}
    </div>
  );
}
