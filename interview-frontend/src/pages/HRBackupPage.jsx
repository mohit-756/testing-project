import { useCallback, useState } from "react";
import { ArrowLeft, Download, AlertCircle, CheckCircle2, Database, Package, RefreshCw, HardDrive, FileArchive, Clock } from "lucide-react";
import { Link } from "react-router-dom";
import { hrApi } from "../services/api";

function StatRow({ label, value }) {
  return (
    <div className="flex justify-between items-center py-2.5 border-b border-slate-100 dark:border-slate-800 last:border-0">
      <span className="text-sm text-slate-500 dark:text-slate-400">{label}</span>
      <span className="text-sm font-bold text-slate-900 dark:text-white">{value}</span>
    </div>
  );
}

export default function HRBackupPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [backupBlob, setBackupBlob] = useState(null);
  const [backupDate, setBackupDate] = useState(null);
  const [backupSize, setBackupSize] = useState(null);
  const [step, setStep] = useState("idle"); // idle | creating | ready

  const handleCreateBackup = useCallback(async () => {
    setLoading(true); setError(""); setMessage(""); setStep("creating");
    setBackupBlob(null); setBackupDate(null); setBackupSize(null);
    try {
      const blob = await hrApi.localBackup();
      setBackupBlob(blob);
      setBackupDate(new Date());
      setBackupSize(blob.size);
      setMessage("Backup created successfully!");
      setStep("ready");
    } catch (e) {
      setError(e.message);
      setStep("idle");
    } finally {
      setLoading(false);
    }
  }, []);

  function handleDownload() {
    if (!backupBlob) { setError("No backup available."); return; }
    const url = URL.createObjectURL(backupBlob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `interviewbot_backup_${backupDate ? backupDate.toISOString().split("T")[0] : "now"}.zip`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function formatBytes(bytes) {
    if (!bytes) return "—";
    if (bytes > 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / 1024).toFixed(0)} KB`;
  }

  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link to="/hr" className="flex items-center gap-2 text-slate-500 hover:text-blue-600 transition-colors font-medium">
          <ArrowLeft size={20} /><span>Back</span>
        </Link>
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white font-display">Data Backup</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-0.5">Export your complete platform data as a secure zip archive.</p>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-8">
        {/* Left — Create backup */}
        <div className="space-y-5">
          {/* Main action card */}
          <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm p-8">
            <div className="flex items-start gap-4 mb-6">
              <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-2xl flex items-center justify-center flex-shrink-0">
                <Database size={24} className="text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-slate-900 dark:text-white">Create Backup</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Exports the full SQLite database plus all uploaded files.</p>
              </div>
            </div>

            {/* What's included */}
            <div className="bg-slate-50 dark:bg-slate-800 rounded-2xl p-4 mb-6 space-y-2">
              {[
                { icon: Database, label: "Full database (candidates, results, sessions, questions)" },
                { icon: FileArchive, label: "All uploaded resumes and proctoring snapshots" },
                { icon: Package, label: "manifest.json with record counts and timestamp" },
              ].map((item) => {
                const ItemIcon = item.icon;
                return (
                <div key={item.label} className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                  <ItemIcon size={14} className="text-blue-500 flex-shrink-0" />
                  {item.label}
                </div>
                );
              })}
            </div>

            {/* Alerts */}
            {error && (
              <div className="mb-4 p-4 bg-red-50 dark:bg-red-900/20 rounded-xl border border-red-100 dark:border-red-800">
                <p className="text-sm font-bold text-red-700 dark:text-red-400 flex items-start gap-2">
                  <AlertCircle size={16} className="flex-shrink-0 mt-0.5" />{error}
                </p>
              </div>
            )}
            {message && (
              <div className="mb-4 p-4 bg-emerald-50 dark:bg-emerald-900/20 rounded-xl border border-emerald-100 dark:border-emerald-800">
                <p className="text-sm font-bold text-emerald-700 dark:text-emerald-400 flex items-center gap-2">
                  <CheckCircle2 size={16} />{message}
                </p>
              </div>
            )}

            {/* Action buttons */}
            <div className="space-y-3">
              <button
                onClick={handleCreateBackup}
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 px-6 py-3.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-2xl shadow-lg shadow-blue-200 dark:shadow-none transition-all disabled:opacity-60"
              >
                {loading ? (
                  <><RefreshCw size={18} className="animate-spin" />Creating backup…</>
                ) : (
                  <><Database size={18} />{step === "ready" ? "Re-create Backup" : "Create Backup"}</>
                )}
              </button>

              {step === "ready" && backupBlob && (
                <button
                  onClick={handleDownload}
                  className="w-full flex items-center justify-center gap-2 px-6 py-3.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-2xl transition-all shadow-lg shadow-emerald-100 dark:shadow-none"
                >
                  <Download size={18} />
                  Download .zip ({formatBytes(backupSize)})
                </button>
              )}
            </div>
          </div>

          {/* Best practices */}
          <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm p-6">
            <h3 className="text-base font-bold text-slate-900 dark:text-white mb-4">Best Practices</h3>
            <ul className="space-y-3 text-sm text-slate-600 dark:text-slate-400">
              {[
                "Create backups before bulk candidate deletions or JD changes.",
                "Store backup files in a secure, access-controlled location.",
                "The zip includes the raw SQLite file — treat it as sensitive data.",
                "Schedule regular exports at the end of each interview batch.",
              ].map((tip) => (
                <li key={tip} className="flex items-start gap-2.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-blue-500 mt-2 flex-shrink-0" />
                  {tip}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Right — Status / Details */}
        {step === "ready" && backupBlob ? (
          <div className="space-y-5">
            {/* Archive details */}
            <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm p-6">
              <div className="flex items-center gap-3 mb-5">
                <div className="w-10 h-10 bg-emerald-100 dark:bg-emerald-900/30 rounded-2xl flex items-center justify-center">
                  <CheckCircle2 size={20} className="text-emerald-600 dark:text-emerald-400" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 dark:text-white">Backup Ready</h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">Archive generated successfully</p>
                </div>
              </div>
              <StatRow label="Format" value="ZIP Archive" />
              <StatRow label="File Size" value={formatBytes(backupSize)} />
              <StatRow label="Created" value={backupDate?.toLocaleString()} />
              <StatRow label="Contains" value="DB + Uploads" />
            </div>

            {/* Download prompt */}
            <div className="bg-gradient-to-br from-blue-600 to-indigo-700 rounded-3xl p-7 text-white">
              <HardDrive size={36} className="mb-4 opacity-80" />
              <h3 className="text-lg font-bold font-display mb-2">Ready to download</h3>
              <p className="text-blue-100 text-sm mb-5">Your backup is ready. Click below to save the archive to your machine.</p>
              <button
                onClick={handleDownload}
                className="w-full flex items-center justify-center gap-2 py-3.5 bg-white text-blue-600 font-black rounded-2xl hover:scale-[1.02] transition-all shadow-xl"
              >
                <Download size={18} />Download Backup
              </button>
            </div>

            {/* What's inside */}
            <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm p-6">
              <h3 className="font-bold text-slate-900 dark:text-white mb-4">Archive Contents</h3>
              <ul className="space-y-2.5">
                {[
                  { icon: Database, label: "database/interview_bot.db", sub: "Full SQLite database" },
                  { icon: FileArchive, label: "uploads/", sub: "Resumes & proctoring images" },
                  { icon: Package, label: "manifest.json", sub: "Record counts & metadata" },
                ].map((item) => {
                  const ItemIcon = item.icon;
                  return (
                  <li key={item.label} className="flex items-start gap-3">
                    <ItemIcon size={15} className="text-blue-500 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-bold text-slate-700 dark:text-slate-300 font-mono">{item.label}</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">{item.sub}</p>
                    </div>
                  </li>
                  );
                })}
              </ul>
            </div>
          </div>
        ) : (
          <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col items-center justify-center p-16 text-center">
            {loading ? (
              <>
                <RefreshCw size={48} className="animate-spin text-blue-500 mb-4" />
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">Creating backup…</h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">This may take a few seconds</p>
              </>
            ) : (
              <>
                <div className="w-20 h-20 bg-slate-100 dark:bg-slate-800 rounded-[28px] flex items-center justify-center mb-5">
                  <Database size={40} className="text-slate-300 dark:text-slate-600" />
                </div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">No backup yet</h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-2 max-w-xs">Click "Create Backup" to export your full platform data as a downloadable zip file.</p>
                <div className="flex items-center gap-2 mt-6 text-xs text-slate-400">
                  <Clock size={13} />
                  <span>Takes about 5-15 seconds</span>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
